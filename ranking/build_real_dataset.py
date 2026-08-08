"""
실 데이터로 학습셋 구성 + 모델 비교 드라이버 (4순위)

matching/live_api_client.py(실제 API 호출) → ranking/dataset_builder.py(feature+pseudo-label) →
ranking/model_comparison.py(모델 비교)로 이어지는 전체 파이프라인을 한 번에 실행한다.

mock 버전(ranking/dataset_builder.py의 __main__)과 다른 점은 데이터 소스만 실제 API로 바뀐 것이고,
나머지 로직(CandidateFeatures 계산, pseudo-label, 모델 비교)은 모두 동일한 코드를 그대로 재사용한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from matching.live_api_client import build_real_congested_spot_with_candidates
from ranking.dataset_builder import build_training_pairs


def build_and_save_real_dataset(
    area_cd: str, signgu_cd: str, tats_nm: str, output_path: str
) -> None:
    """실제 API로 과밀 관광지 + 후보를 가져와 feature/pseudo-label까지 계산하고 JSON으로 저장한다."""
    congested, candidates = build_real_congested_spot_with_candidates(area_cd, signgu_cd, tats_nm)

    ambiguous_by_name = {c.rlte_tats_nm: c.is_region_ambiguous for c in candidates}
    pairs = build_training_pairs(congested, candidates)

    data = [
        {
            "congested_tats_nm": p.congested_tats_nm,
            "candidate_rlte_tats_nm": p.candidate_rlte_tats_nm,
            "features": asdict(p.features),
            "pseudo_label": round(p.pseudo_label, 4),
            "is_region_ambiguous": ambiguous_by_name.get(p.candidate_rlte_tats_nm, False),
        }
        for p in pairs
    ]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    n_ambiguous = sum(1 for row in data if row["is_region_ambiguous"])
    print(f"저장 완료: {output_path} (총 {len(data)}건, 지역 매칭 애매 {n_ambiguous}건 포함)")
    print("모델 학습/비교 시 is_region_ambiguous=true인 행은 제외하고 돌려보는 것도 함께 검토할 것.")


if __name__ == "__main__":
    # 실행: python -m ranking.build_real_dataset  (ai/ 폴더 안에서)
    build_and_save_real_dataset(
        area_cd="51",
        signgu_cd="51130",
        tats_nm="간현관광지",
        output_path="data/processed/training_pairs_real.json",
    )

    print("\n이어서 모델 비교를 실행하려면:")
    print("  python -c \"from ranking.model_comparison import compare_models; "
          "[print(r) for r in compare_models('data/processed/training_pairs_real.json')]\"")
