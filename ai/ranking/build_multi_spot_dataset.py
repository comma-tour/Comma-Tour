"""
여러 과밀 관광지를 한 번에 수집해 학습 데이터셋을 키우는 스크립트 (4순위 -> 확장판)

[2026-09 변경] 기존에는 TARGET_SPOTS에 관광지 이름을 하나하나 하드코딩해서
searchKeyword1로 관광지당 최대 50건까지만 받았다. 조사 결과 TarRlteTarService1에
keyword 없이 지역코드만으로 그 지역의 "모든" 중심관광지 + 연관후보를 가져오는
areaBasedList1이 있다는 게 확인됐고(원주시 한 곳만 800건), 이걸 쓰면 관광지 이름을
몰라도 자동으로 그 지역의 중심관광지 목록 자체를 발굴할 수 있다.

그래서 TARGET_SPOTS(관광지명) 대신 TARGET_REGIONS(지역코드)를 순회하며
matching.live_api_client.build_congested_spots_for_region()으로 지역 전체를 수집한다.

[2026-09 변경 2 - P1] 1차 심사 범위가 부산 해운대구 단일 지역으로 확정되어(계획서 2.6절),
기본 활성 지역을 원주시에서 해운대구로 교체했다. 원주시는 최초 검증 대상으로 이미
학습쌍을 확보했으므로(기존 data/processed/training_pairs_real_multi.json 산출물을
training_pairs_wonju_backup.json 등으로 먼저 백업해둘 것 - 이 스크립트를 그대로
재실행하면 같은 파일명에 덮어써진다), 6.4절 확장 로드맵의 검증·비교용 보조 데이터셋으로
남겨두고 지금은 해운대구 데이터로 새로 수집한다.

[쿼터 주의] 지역 하나당 중심관광지가 수십~백여 개, 후보가 수백~수천 건 나올 수 있어
개발계정 일일 한도(TarRlteTarService1/KorService2 각 1,000건)를 금방 넘길 수 있다.
해운대구(중심관광지 14곳, 후보 586건 추정)는 하루 한도 안에서 충분히 수집 가능한 규모로
확인되어 기본값으로 켜 두었다. 다른 지역을 추가하려면 TARGET_REGIONS에 주석 해제하되,
하루 쿼터로 감당 가능한지 먼저 가늠할 것 (참고: preview_area_spots.py로 사전 규모 확인 가능).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from matching.kakao_mobility_client import fill_travel_times
from matching.live_api_client import RELATED_SPOT_DATA_MAX_YM, build_congested_spots_for_region
from ranking.dataset_builder import build_training_pairs

TARGET_REGIONS = [
    ("26", "26350", "해운대구"),  # 부산 해운대구 - 1차 심사 범위 (중심관광지 14곳, 후보 586건 추정)
    # ("51", "51130", "원주시"),      # 강원 원주시 - 최초 검증 대상, 기존 산출물은 보조 데이터셋으로 보존
    # ("11", "11110", "종로구"),      # 서울 종로구 (중심관광지 64곳, 후보 1,451건) - 대회 이후 확장 후보
    # ("50", "50130", "서귀포시"),    # 제주 서귀포시 (중심관광지 135곳, 후보 4,713건) - 대회 이후 확장 후보
]


def build_multi_spot_dataset(output_path: str) -> None:
    """TARGET_REGIONS를 순회하며 지역별로 지역기반 자동 수집을 실행한다."""
    all_rows: list[dict] = []
    total_spots = 0

    for area_cd, signgu_cd, label in TARGET_REGIONS:
        print(f"\n{'#' * 60}\n### {label} ({area_cd}/{signgu_cd}) 지역 전체 수집 시작\n{'#' * 60}")
        try:
            spot_results = build_congested_spots_for_region(area_cd, signgu_cd, base_ym=RELATED_SPOT_DATA_MAX_YM)
        except Exception as e:  # noqa: BLE001 - 한 지역 실패가 나머지 지역 수집을 막지 않도록 (requests 예외 포함 전부)
            print(f"[건너뜀] '{label}' 지역 수집 실패: {e}")
            continue

        for congested, candidates in spot_results:
            ambiguous_by_name = {c.rlte_tats_nm: c.is_region_ambiguous for c in candidates}

            # [6순위] 후보 목록에 카카오모빌리티 실제 이동시간을 채운다. 실패한 쌍은
            # travel_time_minutes=None으로 남고, build_training_pairs()가 Haversine 기반
            # 추정치로 대체한다 (ranking/features.py의 estimate_travel_time_minutes_fallback).
            candidates = fill_travel_times(congested, candidates)

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
