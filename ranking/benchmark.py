"""
응답 속도 벤치마크 (5순위: 백엔드 통합 준비)

recommend()를 실제 서비스에 붙이기 전에, "서버 시작 시 1회만 드는 비용"(모델 로딩)과
"요청마다 매번 드는 비용"(임베딩 계산 + LightGBM 예측)을 분리해서 측정한다.
후자가 느리면 배치 단계에서 미리 임베딩을 계산해 캐싱하는 구조로 바꿔야 한다는 신호다.
"""

from __future__ import annotations

import time

from matching.mock_tarrltetar import get_mock_congested_spot_with_candidates
from ranking.recommend import _compute_features, _load_model_bundle


def benchmark(n_repeats: int = 5) -> None:
    congested, candidates = get_mock_congested_spot_with_candidates()

    # 1. 모델 로딩 시간 (서버 시작 시 1회만 발생)
    t0 = time.perf_counter()
    _load_model_bundle()
    model_load_sec = time.perf_counter() - t0
    print(f"[모델 로딩] {model_load_sec:.3f}초 (서버 시작 시 1회만)")

    # 2. 임베딩 모델 최초 로딩 시간 (matching/embedding.py 내부에서 lazy 로딩, 첫 호출 때 포함됨)
    t0 = time.perf_counter()
    _compute_features(congested, candidates)
    first_call_sec = time.perf_counter() - t0
    print(f"[요청 1회차 - 임베딩 모델 로딩 포함] {first_call_sec:.3f}초 (후보 {len(candidates)}개)")

    # 3. 이후 요청들 (임베딩 모델은 이미 캐시됨) - 순수하게 "요청당 비용"에 가까움
    durations = []
    for i in range(n_repeats):
        t0 = time.perf_counter()
        _compute_features(congested, candidates)
        durations.append(time.perf_counter() - t0)

    avg_sec = sum(durations) / len(durations)
    print(f"[요청 2회차부터 평균 ({n_repeats}회)] {avg_sec:.3f}초 (후보 {len(candidates)}개)")
    print(f"  -> 후보 1개당 약 {avg_sec / len(candidates) * 1000:.1f}ms")

    print(
        "\n판단 기준: 요청당 비용이 수백 ms 이내면 실시간 계산도 괜찮음.\n"
        "후보가 수십~수백 개로 늘거나 요청당 비용이 초 단위로 나오면,\n"
        "배치 단계에서 overview 임베딩을 미리 계산해 DB에 캐싱하고,\n"
        "요청 시점에는 캐싱된 벡터로 코사인 유사도만 계산하는 구조로 바꿀 것."
    )


if __name__ == "__main__":
    # 실행: python -m ranking.benchmark  (ai/ 폴더 안에서, 사전에 python -m ranking.train_final_model 실행 필요)
    benchmark()
