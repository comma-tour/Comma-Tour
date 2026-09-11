"""
임베딩 기반 의미 유사도 모듈 (4장 4.4-1 핵심 엔진)

1순위 목표: 로컬에서 돌릴 한국어 지원 문장 임베딩 모델을 선정하고 테스트 환경을 구축한다.
2순위에서 소개문구 → 벡터 변환 함수 / 코사인 유사도 계산 함수를 완성한다 (아래는 골격).

[중요 정정] 4장 4.4절 설계 문서는 "KorService2의 detailIntro2 소개문구"를 임베딩 대상으로 명시했으나,
실제 API 매뉴얼 확인 결과 detailIntro2는 휴무일/개장시간/주차시설 등 구조화된 운영정보만 반환하며
자유 서술형 소개문구가 아니다. 실제 소개문구는 detailCommon2 오퍼레이션의 overview 필드에 있다.
따라서 임베딩 입력 소스는 "KorService2 detailCommon2.overview"로 정정한다 (은진님 백엔드 배치 수집 대상도 동일하게 확인 필요).

모델 후보 (sentence-transformers 계열, 한국어 지원):
    - jhgan/ko-sroberta-multitask       (KorNLI/KorSTS 파인튜닝, 검증된 베이스라인)
    - BM-K/KoSimCSE-roberta             (대조학습 기반)
    - intfloat/multilingual-e5-base     (다국어, 검색 특화)
    - BAAI/bge-m3                       (선택, 다국어·긴 문서에 강하지만 무거움)

.env의 EMBEDDING_MODEL_NAME 값으로 기본 모델을 지정한다.
비교 평가는 CANDIDATE_MODELS를 순회하는 compare_models()를 사용할 것 (평가셋: matching/eval_set.py).
"""

from __future__ import annotations

import os
import time

import numpy as np
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jhgan/ko-sroberta-multitask")

CANDIDATE_MODELS = [
    "jhgan/ko-sroberta-multitask",
    "BM-K/KoSimCSE-roberta",
    "intfloat/multilingual-e5-base",
    # "BAAI/bge-m3",  # 속도 여유 있을 때만 주석 해제
]

_models: dict[str, object] = {}  # model_name -> loaded SentenceTransformer (모델별 캐시)


def load_embedding_model(model_name: str = DEFAULT_MODEL_NAME):
    """
    sentence-transformers 모델을 로드한다 (모델별로 최초 1회만 로딩 후 재사용).
    여러 모델을 번갈아 비교해야 하므로 모델명 기준으로 캐시한다 (단일 전역 변수 캐시는 compare_models에서 부적절).

    1순위 체크포인트: 이 함수가 에러 없이 모델을 로드하고,
    아래 __main__ 테스트가 정상 동작하면 환경 구축이 끝난 것으로 본다.
    """
    if model_name not in _models:
        from sentence_transformers import SentenceTransformer

        _models[model_name] = SentenceTransformer(model_name)
    return _models[model_name]


def embed_texts(texts: list[str], model_name: str = DEFAULT_MODEL_NAME) -> np.ndarray:
    """
    소개문구(KorService2 detailCommon2.overview) 리스트를 벡터로 변환한다.

    Args:
        texts: 소개문구(overview) 문자열 리스트
        model_name: 사용할 임베딩 모델 이름

    Returns:
        (len(texts), embedding_dim) 형태의 numpy 배열
    """
    model = load_embedding_model(model_name)
    return model.encode(texts, normalize_embeddings=True)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    두 관광지 소개문구 임베딩 간 코사인 유사도를 계산한다.
    embed_texts에서 normalize_embeddings=True로 정규화했다면 내적만으로 계산 가능.
    """
    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))


def pairwise_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    관광지 N개의 임베딩 행렬(N, dim)로부터 N x N 코사인 유사도 행렬을 계산한다.
    (정규화된 임베딩이라는 전제 하에 행렬곱으로 처리, 3순위 feature 생성 시 재사용)
    """
    return embeddings @ embeddings.T


def _pair_avg_similarity(pairs: list[tuple[str, str]], sentence_to_vec: dict[str, np.ndarray]) -> float:
    """문장 쌍 리스트에 대한 평균 코사인 유사도 (임베딩은 이미 계산된 것을 재사용)"""
    sims = [cosine_similarity(sentence_to_vec[a], sentence_to_vec[b]) for a, b in pairs]
    return float(np.mean(sims))


def evaluate_model(model_name: str) -> dict:
    """
    단일 모델에 대해 matching/eval_set.py의 평가셋(유사 10쌍/비유사 10쌍)으로 성능을 측정한다.

    측정 항목:
        - load_seconds: 모델 로딩 소요 시간
        - embed_seconds: 평가셋 20문장 임베딩 소요 시간
        - dim: 임베딩 차원 수
        - similar_avg / dissimilar_avg: 유사 쌍 / 비유사 쌍 평균 코사인 유사도
        - gap: similar_avg - dissimilar_avg (클수록 좋은 모델)
    """
    from matching.eval_set import get_all_sentences, get_dissimilar_pairs, get_similar_pairs

    t0 = time.perf_counter()
    load_embedding_model(model_name)
    load_seconds = time.perf_counter() - t0

    sentences = get_all_sentences()
    t1 = time.perf_counter()
    vectors = embed_texts(sentences, model_name=model_name)
    embed_seconds = time.perf_counter() - t1

    sentence_to_vec = {s: v for s, v in zip(sentences, vectors)}
    similar_avg = _pair_avg_similarity(get_similar_pairs(), sentence_to_vec)
    dissimilar_avg = _pair_avg_similarity(get_dissimilar_pairs(), sentence_to_vec)

    return {
        "model_name": model_name,
        "dim": int(vectors.shape[1]),
        "load_seconds": round(load_seconds, 2),
        "embed_seconds": round(embed_seconds, 3),
        "similar_avg": round(similar_avg, 4),
        "dissimilar_avg": round(dissimilar_avg, 4),
        "gap": round(similar_avg - dissimilar_avg, 4),
    }


def compare_models(model_names: list[str] = CANDIDATE_MODELS) -> list[dict]:
    """
    후보 모델들을 순회하며 evaluate_model()을 실행하고, 결과를 gap 내림차순으로 정렬해 반환한다.
    개별 모델 로딩 실패(디스크/네트워크 문제 등)는 건너뛰고 나머지 모델은 계속 진행한다.
    """
    results = []
    for name in model_names:
        print(f"[compare_models] {name} 평가 중...")
        try:
            result = evaluate_model(name)
            results.append(result)
            print(f"  -> gap={result['gap']}, similar_avg={result['similar_avg']}, "
                  f"dissimilar_avg={result['dissimilar_avg']}, dim={result['dim']}, "
                  f"load={result['load_seconds']}s, embed={result['embed_seconds']}s")
        except Exception as e:  # noqa: BLE001 - 모델별 실패를 다음 모델 평가로 넘기기 위해 광범위하게 처리
            print(f"  -> 실패: {e}")
    results.sort(key=lambda r: r["gap"], reverse=True)
    return results


def format_results_as_markdown(results: list[dict]) -> str:
    """
    compare_models() 결과를 ai/docs/embedding_model_comparison.md에 붙여넣을 수 있는
    마크다운 표 형태의 문자열로 변환한다.
    """
    header = "| 모델 | 차원 | 로딩(s) | 임베딩(s) | 유사쌍 평균 | 비유사쌍 평균 | gap |\n"
    header += "|---|---|---|---|---|---|---|\n"
    rows = ""
    for r in results:
        rows += (
            f"| {r['model_name']} | {r['dim']} | {r['load_seconds']} | {r['embed_seconds']} | "
            f"{r['similar_avg']} | {r['dissimilar_avg']} | **{r['gap']}** |\n"
        )
    return header + rows


if __name__ == "__main__":
    # 3순위(스크립트) 실행: 관광 도메인 평가셋(matching/eval_set.py)으로 후보 모델 전체 비교
    # 실행: python -m matching.embedding  (ai/ 폴더 안에서)
    results = compare_models()

    print("\n=== 비교 결과 (gap 내림차순) ===")
    print(format_results_as_markdown(results))
    print("위 표를 ai/docs/embedding_model_comparison.md에 붙여넣고 최종 모델과 선정 이유를 기록할 것.")
