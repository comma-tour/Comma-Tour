"""
여러 과밀 관광지를 한 번에 수집해 학습 데이터셋을 키우는 스크립트 (4순위)

관광지 1곳의 후보들만으로는 그 관광지에만 맞는 패턴을 학습할 위험이 있어,
서로 다른 지역·카테고리의 과밀 관광지 여러 곳을 모아 일반화 가능성을 확인한다.

지역코드는 OT 자료의 "한국관광공사_OpenAPI_관광지_시군구_코드정보_v1.0.xlsx"에서 실제 값을 확인해 사용:
    - 서울 종로구: areaCd=11, signguCd=11110
    - 부산 해운대구: areaCd=26, signguCd=26350
    - 제주 서귀포시: areaCd=50, signguCd=50130
    - 강원 원주시: areaCd=51, signguCd=51130 (간현관광지로 이미 검증 완료)

관광지명이 KorService2/TarRlteTarService1에 정확히 등록된 이름과 다르면 실패할 수 있으니,
TARGET_SPOTS 리스트를 실행해보고 실패하는 이름은 국문 관광정보 서비스에서 정확한 명칭을 확인해 조정할 것.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from matching.live_api_client import build_real_congested_spot_with_candidates
from ranking.dataset_builder import build_training_pairs

TARGET_SPOTS = [
    ("51", "51130", "간현관광지"),  # 강원 원주시 - 검증 완료 (25건 확보)
    ("11", "11110", "경복궁"),  # 서울 종로구
    ("26", "26350", "해운대해수욕장"),  # 부산 해운대구
    ("50", "50130", "성산일출봉"),  # 제주 서귀포시
]


def build_multi_spot_dataset(output_path: str) -> None:
    """TARGET_SPOTS를 순회하며 각각 실 데이터를 수집하고, 실패한 관광지는 건너뛰고 계속 진행한다."""
    all_rows: list[dict] = []

    for area_cd, signgu_cd, tats_nm in TARGET_SPOTS:
        print(f"\n=== {tats_nm} ({area_cd}/{signgu_cd}) 수집 시작 ===")
        try:
            congested, candidates = build_real_congested_spot_with_candidates(area_cd, signgu_cd, tats_nm)
        except Exception as e:  # noqa: BLE001 - 한 관광지 실패가 나머지 수집을 막지 않도록
            print(f"[건너뜀] '{tats_nm}' 수집 실패: {e}")
            continue

        if not candidates:
            print(f"[건너뜀] '{tats_nm}' 연관관광지 후보 0건 - 데이터셋에서 제외")
            continue

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
        print(f"'{tats_nm}' 완료: 후보 {len(candidates)}건 추가 (누적 {len(all_rows)}건)")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)

    n_ambiguous = sum(1 for row in all_rows if row["is_region_ambiguous"])
    n_spots = len({row["congested_tats_nm"] for row in all_rows})
    print(f"\n저장 완료: {output_path}")
    print(f"총 {len(all_rows)}건 ({n_spots}개 관광지 기준), 지역 매칭 애매 {n_ambiguous}건 포함")


if __name__ == "__main__":
    # 실행: python -m ranking.build_multi_spot_dataset  (ai/ 폴더 안에서)
    build_multi_spot_dataset("data/processed/training_pairs_real_multi.json")

    print("\n이어서 모델 비교를 실행하려면:")
    print("  python -c \"from ranking.model_comparison import compare_models; "
          "[print(r) for r in compare_models('data/processed/training_pairs_real_multi.json')]\"")
