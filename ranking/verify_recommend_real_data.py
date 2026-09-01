"""
[검증 전용 - 프로덕션 파이프라인에 포함되지 않음]

목적: ranking/recommend.py의 __main__ 데모는 mock_tarrltetar의 가짜 데이터로만 인터페이스를
확인한다. 이 스크립트는 실제 API에서 가져온 "진짜" 과밀 관광지 + 후보로 recommend()를 호출해서,
방금 학습한 모델이 실제 데이터에서도 상식적인 추천을 만들어내는지 확인한다.

기본값은 간현관광지(강원 원주시)로 검증한다 - build_multi_spot_dataset.py가 학습에 쓴
지역(TARGET_REGIONS)에 포함된 실제 검증된 관광지라 결과 없음/매칭 실패 위험이 낮다.

실행 방법 (ai/ 폴더 안에서, 사전에 python -m ranking.train_final_model 실행 필요):
    python -m ranking.verify_recommend_real_data
    python -m ranking.verify_recommend_real_data 51 51130 간현관광지   (다른 관광지로 검증하고 싶을 때)
"""

from __future__ import annotations

import json
import sys

from matching.live_api_client import RELATED_SPOT_DATA_MAX_YM, build_real_congested_spot_with_candidates
from ranking.recommend import recommend

DEFAULT_AREA_CD = "51"
DEFAULT_SIGNGU_CD = "51130"
DEFAULT_TATS_NM = "간현관광지"


def main() -> None:
    if len(sys.argv) >= 4:
        area_cd, signgu_cd, tats_nm = sys.argv[1], sys.argv[2], sys.argv[3]
    else:
        area_cd, signgu_cd, tats_nm = DEFAULT_AREA_CD, DEFAULT_SIGNGU_CD, DEFAULT_TATS_NM

    print(f"=== 실제 API로 '{tats_nm}'({area_cd}/{signgu_cd}) 데이터 조회 중 ===")
    congested, candidates = build_real_congested_spot_with_candidates(
        area_cd, signgu_cd, tats_nm, base_ym=RELATED_SPOT_DATA_MAX_YM
    )

    if not candidates:
        raise SystemExit(f"'{tats_nm}'의 후보가 0건이라 추천을 검증할 수 없습니다.")

    print(f"\n실제 조회된 과밀 관광지: {congested.tats_nm} (cnctrRate7dAvg={congested.cnctr_rate_7d_avg})")
    print(f"실제 조회된 후보 수: {len(candidates)}건\n")

    result = recommend(congested, candidates, top_k=5, debug=True)
    print("=== 학습된 모델의 추천 결과 (실 데이터 기준) ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
