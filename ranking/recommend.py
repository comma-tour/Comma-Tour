"""
AI 모듈 최종 진입점 (5순위: 은진님 백엔드 통합용)

docs/recommend_endpoint_spec_draft.md에서 확정한 입출력 스펙과 동일한 형태로 결과를 반환하는
순수 함수 recommend()를 제공한다. 은진님 배치 계층이 DB에서 조회한 결과를 CongestedSpot/Candidate로
변환해 이 함수에 넘기면 되고, 이 모듈은 DB에 직접 접근하지 않는다 (2순위에서 확정한 경계).

사용 예:
    from matching.mock_tarrltetar import get_mock_congested_spot_with_candidates
    from ranking.recommend import recommend

    congested, candidates = get_mock_congested_spot_with_candidates()
    result = recommend(congested, candidates, top_k=5)
"""

from __future__ import annotations

import os

import joblib
import numpy as np

from matching.mock_tarrltetar import Candidate, CongestedSpot
from matching.similarity_matching import rank_candidates_by_similarity
from ranking.features import (
    CandidateFeatures,
    category_match_score,
    cnctr_rate_gap,
    coord_distance_km,
    normalize_rlte_rank,
)
from ranking.train_final_model import MODEL_PATH

_model_bundle = None  # lazy-loaded (model, feature_columns, model_type)


def _load_model_bundle() -> dict:
    global _model_bundle
    if _model_bundle is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"{MODEL_PATH}가 없습니다. 먼저 python -m ranking.train_final_model 을 실행해 모델을 학습/저장할 것."
            )
        _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle


def _compute_features(congested: CongestedSpot, candidates: list[Candidate]) -> list[CandidateFeatures]:
    """모든 후보의 CandidateFeatures를 계산한다 (임베딩 유사도는 배치로 한 번에 처리)."""
    similarity_ranked = rank_candidates_by_similarity(congested, candidates)
    similarity_by_name = {r.candidate.rlte_tats_nm: r.similarity for r in similarity_ranked}

    features_list = []
    for c in candidates:
        features_list.append(
            CandidateFeatures(
                rlte_rank_norm=normalize_rlte_rank(c.rlte_rank),
                category_match=category_match_score(congested.content_type_id, c.rlte_ctgry_lcls_nm),
                embedding_similarity=similarity_by_name[c.rlte_tats_nm],
                cnctr_rate_gap=cnctr_rate_gap(congested.cnctr_rate_7d_avg, c.cnctr_rate_7d_avg),
                coord_distance=coord_distance_km(congested.mapx, congested.mapy, c.mapx, c.mapy),
            )
        )
    return features_list


def recommend(
    congested: CongestedSpot, candidates: list[Candidate], top_k: int = 5, debug: bool = False
) -> dict:
    """
    과밀 관광지 1곳 + 연관관광지 후보 목록을 받아, 학습된 모델로 점수를 매기고 상위 top_k개를 반환한다.

    Args:
        congested: 과밀 관광지 (은진님 배치 계층이 DB에서 조회해 조립한 객체)
        candidates: 연관관광지 후보 목록
        top_k: 반환할 개수 (기본 5, 최대 20으로 클램프 - docs/5순위_통합가이드.md에서 확정)
        debug: True면 각 후보의 scoreBreakdown(개별 feature 값)도 함께 반환

    Returns:
        docs/recommend_endpoint_spec_draft.md의 응답 스펙과 동일한 구조의 dict
    """
    top_k = max(1, min(top_k, 20))  # topK 상한 확정치 (5순위 스펙 확정, 08.18)

    bundle = _load_model_bundle()
    model, feature_columns = bundle["model"], bundle["feature_columns"]

    features_list = _compute_features(congested, candidates)
    X = np.array([[getattr(f, col) for col in feature_columns] for f in features_list])
    scores = model.predict(X)

    ranked = sorted(zip(candidates, features_list, scores), key=lambda t: t[2], reverse=True)[:top_k]

    recommendations = []
    for candidate, features, score in ranked:
        entry = {
            "rlteTatsNm": candidate.rlte_tats_nm,
            "rlteRank": candidate.rlte_rank,
            "rlteCtgryLclsNm": candidate.rlte_ctgry_lcls_nm,
            "rlteCtgryMclsNm": candidate.rlte_ctgry_mcls_nm,
            "rlteCtgrySclsNm": candidate.rlte_ctgry_scls_nm,
            "cnctrRate7dAvg": round(candidate.cnctr_rate_7d_avg, 2),
            "mapx": candidate.mapx,
            "mapy": candidate.mapy,
            "score": round(float(score), 4),
        }
        if debug:
            entry["scoreBreakdown"] = {
                "rlteRankNorm": round(features.rlte_rank_norm, 4),
                "categoryMatch": features.category_match,
                "embeddingSimilarity": round(features.embedding_similarity, 4),
                "cnctrRateGap": round(features.cnctr_rate_gap, 2),
                "coordDistance": round(features.coord_distance, 2),
            }
        recommendations.append(entry)

    return {
        "congestedSpot": {
            "tAtsNm": congested.tats_nm,
            "cnctrRate7dAvg": round(congested.cnctr_rate_7d_avg, 2),
        },
        "recommendations": recommendations,
    }


if __name__ == "__main__":
    # 데모: mock 데이터로 인터페이스가 정상 동작하는지 확인 (실제 서비스에선 실 데이터로 호출)
    # 실행: python -m ranking.recommend  (ai/ 폴더 안에서, 사전에 python -m ranking.train_final_model 실행 필요)
    import json

    from matching.mock_tarrltetar import get_mock_congested_spot_with_candidates

    congested, candidates = get_mock_congested_spot_with_candidates()
    result = recommend(congested, candidates, top_k=5, debug=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
