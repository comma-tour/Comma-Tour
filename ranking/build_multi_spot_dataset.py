"""
여러 과밀 관광지를 한 번에 수집해 학습 데이터셋을 키우는 스크립트 (4순위 -> 확장판)

[2026-09 변경] 기존에는 TARGET_SPOTS에 관광지 이름을 하나하나 하드코딩해서
searchKeyword1로 관광지당 최대 50건까지만 받았다. 조사 결과 TarRlteTarService1에
keyword 없이 지역코드만으로 그 지역의 "모든" 중심관광지 + 연관후보를 가져오는
areaBasedList1이 있다는 게 확인됐고(원주시 한 곳만 800건), 이걸 쓰면 관광지 이름을
몰라도 자동으로 그 지역의 중심관광지 목록 자체를 발굴할 수 있다.

그래서 TARGET_SPOTS(관광지명) 대신 TARGET_REGIONS(지역코드)를 순회하며
matching.live_api_client.build_congested_spots_for_region()으로 지역 전체를 수집한다.

[쿼터 주의] 지역 하나당 중심관광지가 수십~백여 개, 후보가 수백~수천 건 나올 수 있어
개발계정 일일 한도(TarRlteTarService1/KorService2 각 1,000건)를 금방 넘길 수 있다.
그래서 기본값은 원주시 1곳만 켜져 있다 - 다른 지역을 추가하려면 TARGET_REGIONS에
주석 해제하되, 하루 쿼터로 감당 가능한지 먼저 가늠할 것 (참고: preview_area_spots.py로
사전 규모 확인 가능).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from matching.live_api_client import RELATED_SPOT_DATA_MAX_YM, build_congested_spots_for_region
from ranking.dataset_builder import build_training_pairs

TARGET_REGIONS = [
    ("51", "51130", "원주시"),  # 강원 원주시 - 1차 검증 대상 (중심관광지 27곳, 후보 800건)
    # ("11", "11110", "종로구"),      # 서울 종로구 (중심관광지 64곳, 후보 1,451건) - 쿼터 확인 후 활성화
    # ("26", "26350", "해운대구"),    # 부산 해운대구 (중심관광지 14곳, 후보 586건) - 쿼터 확인 후 활성화
    # ("50", "50130", "서귀포시"),    # 제주 서귀포시 (중심관광지 135곳, 후보 4,713건) - 쿼터 확인 후 활성화
]


def build_multi_spot_dataset(output_path: str) -> None:
    """TARGET_REGIONS를 순회하며 지역별로 지역기반 자동 수집을 실행한다."""
    all_rows: list[dict] = []
    total_spots = 0

    for area_cd, signgu_cd, label in TARGET_REGIONS:
        print(f"\n{'#' * 60}\n### {label} ({area_cd}/{signgu_cd}) 지역 전체 수집 시작\n{'#' * 60}")
        try:
            spot_results = build_congested_spots_for_region(area_cd, signgu_cd, base_ym=RELATED_SPOT_DATA_MAX_YM)
        except Exception as e:  # noqa: BLE001 - 한 지역 실패가 나머지 지역 수집을 막지 않도록
            print(f"[건너뜀] '{label}' 지역 수집 실패: {e}")
            continue

        for congested, candidates in spot_results:
            ambiguous_by_name = {c.rlte_tats_nm: c.is_region_ambiguous for c in candidates}
            pairs = build_training_pairs(congested, candidates)

            for p in pairs:
                all_rows.append(
                    {
                        "congested_tats_nm": p.congested_tats_nm,
                        "candidate_rlte_tats_nm": p.candidate_rlte_tats_nm,
                        "features": asdict(p.features),
                        "pseudo_label": round(p.pseudo_label, 4),
                        "is_region_ambiguous": ambiguous_by_name.get(p.candidate_rlte_tats_nm, False),
                    }
                )
            total_spots += 1

        print(f"\n'{label}' 지역 완료: 중심관광지 {len(spot_results)}곳, 누적 학습쌍 {len(all_rows)}건")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)

    n_ambiguous = sum(1 for row in all_rows if row["is_region_ambiguous"])
    print(f"\n저장 완료: {output_path}")
    print(f"총 {len(all_rows)}건 ({total_spots}개 관광지 기준), 지역 매칭 애매 {n_ambiguous}건 포함")


if __name__ == "__main__":
    # 실행: python -m ranking.build_multi_spot_dataset  (ai/ 폴더 안에서)
    build_multi_spot_dataset("data/processed/training_pairs_real_multi.json")

    print("\n이어서 모델 비교를 실행하려면:")
    print("  python -c \"from ranking.model_comparison import compare_models; "
          "[print(r) for r in compare_models('data/processed/training_pairs_real_multi.json')]\"")
