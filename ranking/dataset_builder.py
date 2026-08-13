"""
학습용 관광지-후보 쌍 데이터셋 조립 (3순위 마지막 작업)

matching/mock_tarrltetar.py(과밀 관광지 + 후보), matching/similarity_matching.py(임베딩 유사도),
ranking/features.py(feature 계산 + pseudo-label)를 모두 조합해 하나의 학습용 데이터셋을 만든다.

4순위(LightGBM 랭킹 모델 학습)는 이 모듈이 만든 데이터셋을 입력으로 받아 진행할 예정이다.
지금은 mock 데이터 8쌍뿐이라 실제 학습에는 부족하지만, 파이프라인이 끝까지 동작하는지 검증하는 목적이다.
실제 데이터 확보 후에는 matching/mock_tarrltetar.py의 데이터 소스만 실제 DB 조회로 바꾸면
이 모듈은 수정 없이 그대로 재사용 가능하다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from matching.mock_tarrltetar import Candidate, CongestedSpot, get_mock_congested_spot_with_candidates
from matching.similarity_matching import rank_candidates_by_similarity
from ranking.features import (
    CandidateFeatures,
    category_match_score,
    cnctr_rate_gap,
    compute_pseudo_label,
    coord_distance_km,
    normalize_rlte_rank,
)


@dataclass
class TrainingPair:
    """관광지-후보 쌍 1건의 학습 데이터 (feature + pseudo-label)"""

    congested_tats_nm: str
    candidate_rlte_tats_nm: str
    features: CandidateFeatures
    pseudo_label: float


def build_training_pairs(
    congested: CongestedSpot, candidates: list[Candidate]
) -> list[TrainingPair]:
    """
    과밀 관광지 1곳 + 후보 N개로부터 학습용 (관광지, 후보) 쌍 데이터셋을 조립한다.
    pseudo_label 내림차순으로 정렬해 반환한다.
    """
    similarity_ranked = rank_candidates_by_similarity(congested, candidates)
    similarity_by_name = {r.candidate.rlte_tats_nm: r.similarity for r in similarity_ranked}

    pairs: list[TrainingPair] = []
    for c in candidates:
        features = CandidateFeatures(
            rlte_rank_norm=normalize_rlte_rank(c.rlte_rank),
            category_match=category_match_score(congested.content_type_id, c.rlte_ctgry_lcls_nm),
            embedding_similarity=similarity_by_name[c.rlte_tats_nm],
            cnctr_rate_gap=cnctr_rate_gap(congested.cnctr_rate_7d_avg, c.cnctr_rate_7d_avg),
            coord_distance=coord_distance_km(congested.mapx, congested.mapy, c.mapx, c.mapy),
        )
        pseudo_label = compute_pseudo_label(features)
        pairs.append(
            TrainingPair(
                congested_tats_nm=congested.tats_nm,
                candidate_rlte_tats_nm=c.rlte_tats_nm,
                features=features,
                pseudo_label=pseudo_label,
            )
        )

    pairs.sort(key=lambda p: p.pseudo_label, reverse=True)
    return pairs


def save_training_pairs(pairs: list[TrainingPair], path: str) -> None:
    """학습 데이터셋을 JSON으로 저장한다 (4순위 LightGBM 학습 입력으로 재사용)."""
    data = [
        {
            "congested_tats_nm": p.congested_tats_nm,
            "candidate_rlte_tats_nm": p.candidate_rlte_tats_nm,
            "features": asdict(p.features),
            "pseudo_label": round(p.pseudo_label, 4),
        }
        for p in pairs
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 종단(end-to-end) 데모: mock 데이터로 feature 계산 + pseudo-label까지 전체 파이프라인 실행
    # 실행: python -m ranking.dataset_builder  (ai/ 폴더 안에서)
    congested, candidates = get_mock_congested_spot_with_candidates()
    pairs = build_training_pairs(congested, candidates)

    print(f"과밀 관광지: {congested.tats_nm}\n")
    header = f"{'순위':<4}{'후보':<14}{'pseudo_label':<14}{'rankNorm':<10}{'catMatch':<10}{'embSim':<10}{'cnctrGap':<10}{'distKm':<8}"
    print(header)
    for i, p in enumerate(pairs, start=1):
        f = p.features
        print(
            f"{i:<4}{p.candidate_rlte_tats_nm:<14}{p.pseudo_label:<14.4f}"
            f"{f.rlte_rank_norm:<10.2f}{f.category_match:<10.1f}{f.embedding_similarity:<10.4f}"
            f"{f.cnctr_rate_gap:<10.1f}{f.coord_distance:<8.1f}"
        )

    output_path = "data/processed/training_pairs_mock.json"
    save_training_pairs(pairs, output_path)
    print(f"\n저장 완료: {output_path}")
    print(
        "\n확인 포인트: 임베딩 유사도만으로 정렬했을 때(2순위 결과)와 순서가 달라졌는지 확인할 것.\n"
        "카테고리 일치도(관광지 vs 음식/쇼핑/숙박)와 cnctrRate 격차(붐빔 정도)가 추가로 반영되어\n"
        "단순 임베딩 유사도 순위와는 다른 최종 순위가 나와야 pseudo-label 설계가 의미 있다는 근거가 됩니다."
    )
