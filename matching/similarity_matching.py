"""
임베딩 유사도 매칭 모듈 (4장 4.4-1 핵심 엔진의 실행 진입점)

2순위 목표: matching/embedding.py의 embed_texts/cosine_similarity를 조합해,
과밀 관광지 1곳과 TarRlteTarService1 후보 N개 간 유사도를 계산하고 순위를 매기는 함수를 완성한다.
은진님 백엔드 모듈(배치 수집/DB 조회)과는 별개로, mock 데이터만으로 독립 실행 가능해야 한다.

3순위(feature 생성)에서는 이 모듈의 rank_candidates_by_similarity() 결과 중 similarity 값을
"임베딩 코사인 유사도" feature로 그대로 재사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from matching.embedding import cosine_similarity, embed_texts
from matching.mock_tarrltetar import Candidate, CongestedSpot


@dataclass
class RankedCandidate:
    """유사도 순위가 매겨진 후보 1건"""

    candidate: Candidate
    similarity: float  # 과밀 관광지 overview와의 코사인 유사도 (-1 ~ 1, 클수록 유사)


def rank_candidates_by_similarity(
    congested: CongestedSpot, candidates: list[Candidate]
) -> list[RankedCandidate]:
    """
    과밀 관광지 1곳의 overview와, 연관관광지 후보 N개의 overview 간 코사인 유사도를 계산해
    유사도 내림차순으로 정렬한 리스트를 반환한다.

    임베딩은 (과밀 관광지 1개 + 후보 N개) 전체를 한 번에 배치로 변환해 모델 호출 횟수를 최소화한다.
    """
    texts = [congested.overview] + [c.overview for c in candidates]
    vectors = embed_texts(texts)

    congested_vec = vectors[0]
    candidate_vecs = vectors[1:]

    ranked = [
        RankedCandidate(candidate=c, similarity=cosine_similarity(congested_vec, v))
        for c, v in zip(candidates, candidate_vecs)
    ]
    ranked.sort(key=lambda r: r.similarity, reverse=True)
    return ranked


if __name__ == "__main__":
    # 종단(end-to-end) 데모: mock 과밀 관광지 + mock 연관관광지 후보로 임베딩 유사도 순위 확인
    # 실행: python -m matching.similarity_matching  (ai/ 폴더 안에서)
    from matching.mock_tarrltetar import get_mock_congested_spot_with_candidates

    congested, candidates = get_mock_congested_spot_with_candidates()
    ranked = rank_candidates_by_similarity(congested, candidates)

    print(f"과밀 관광지: {congested.tats_nm}")
    print(f"  overview: {congested.overview}\n")
    print("임베딩 유사도 순위 (rlteRank와 비교):")
    print(f"{'순위':<4}{'연관관광지명':<14}{'임베딩유사도':<12}{'rlteRank':<10}{'카테고리(중분류)'}")
    for i, r in enumerate(ranked, start=1):
        c = r.candidate
        print(f"{i:<4}{c.rlte_tats_nm:<14}{r.similarity:<12.4f}{c.rlte_rank:<10}{c.rlte_ctgry_mcls_nm}")

    print(
        "\n확인 포인트: rlteRank는 낮지만(=연관순위 상위) 실제 내용이 다른 후보와, "
        "rlteRank는 높지만(=연관순위 하위) 내용이 실제로 유사한 후보가 뒤바뀌어 나오는지 확인할 것.\n"
        "이 차이가 바로 임베딩 유사도가 rlteRank와 별개로 독립 신호를 제공한다는 근거입니다."
    )
