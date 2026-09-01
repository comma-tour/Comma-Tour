"""
[조사 전용 - 프로덕션 파이프라인에 포함되지 않음]

목적 (확장 계획 ①③의 선행조사):
1. TarRlteTarService1에 "지역기반 목록 조회" 엔드포인트(추정 이름: areaBasedList1)가
   실제로 존재하는지 확인한다. 존재하면 area_cd/signgu_cd만으로 그 지역에 등록된
   중심관광지 목록 자체를 가져올 수 있어, ranking/build_multi_spot_dataset.py의
   TARGET_SPOTS 하드코딩을 없앨 수 있다.
2. searchKeyword1에 카테고리(관광지/음식/숙박) 필터 파라미터가 있는지 몇 가지 후보
   이름으로 시험 호출해본다 (문서를 못 구해서 추정치로 시험 - 실패해도 정상).

실행 방법 (ai/ 폴더 안에서, .env에 KORSERVICE_API_KEY 설정된 상태로):
    python -m matching.probe_tarrltetar_endpoints

이 스크립트가 출력하는 raw 응답/에러 메시지를 그대로 공유해주면, 그 결과를 보고
다음 단계(① 지역기반 자동 발굴 구현, ③ 카테고리별 조회 구현)를 진행할 수 있다.
"""

from __future__ import annotations

import json

from matching.live_api_client import BASE_TARRLTETAR, RELATED_SPOT_DATA_MAX_YM, _common_params, _get

# 테스트 대상: 이미 데이터가 있는 걸 알고 있는 강원 원주시 (간현관광지 base_ym=202504 기준 확인됨)
TEST_AREA_CD = "51"
TEST_SIGNGU_CD = "51130"
TEST_BASE_YM = RELATED_SPOT_DATA_MAX_YM


def _print_result(label: str, url: str, params: dict) -> None:
    print(f"\n{'=' * 60}\n[{label}]\nGET {url}\nparams={ {k: v for k, v in params.items() if k != 'serviceKey'} }")
    try:
        data = _get(url, params)
        body = data.get("response", {}).get("body", {})
        total_count = body.get("totalCount")
        print(f"결과: 성공. totalCount={total_count}")
        print(f"원문(앞 1000자): {json.dumps(data, ensure_ascii=False)[:1000]}")
    except Exception as e:  # noqa: BLE001 - 조사용 스크립트라 모든 실패를 그대로 보여준다
        print(f"결과: 실패. {e}")


def probe_area_based_list() -> None:
    """[조사 ①] 지역기반(키워드 없이) 목록 조회 엔드포인트가 존재하는지 확인."""
    # data.go.kr 상세설명에 언급된 "지역기반 관광지별 연관 관광지 정보 목록 조회"의
    # 실제 URL 경로명은 문서 확인 전이라 자주 쓰이는 명명 규칙(areaBasedList1)으로 추정해 시험한다.
    candidate_paths = ["areaBasedList1", "areaBasedList2", "areaBasedSyncList1"]
    for path in candidate_paths:
        params = _common_params(
            {
                "baseYm": TEST_BASE_YM,
                "areaCd": TEST_AREA_CD,
                "signguCd": TEST_SIGNGU_CD,
                "numOfRows": 50,
                "pageNo": 1,
            }
        )
        _print_result(f"지역기반 목록 조회 시도: {path}", f"{BASE_TARRLTETAR}/{path}", params)


def probe_category_filter() -> None:
    """[조사 ③] searchKeyword1에 카테고리 필터 파라미터가 있는지 몇 가지 이름으로 시험."""
    base_params = {
        "baseYm": TEST_BASE_YM,
        "areaCd": TEST_AREA_CD,
        "signguCd": TEST_SIGNGU_CD,
        "keyword": "간현관광지",
        "numOfRows": 50,
        "pageNo": 1,
    }

    # 필터 없이 기본 호출 (베이스라인 - totalCount 확인용)
    _print_result("카테고리 필터 없음 (베이스라인)", f"{BASE_TARRLTETAR}/searchKeyword1", _common_params(base_params))

    # 흔히 쓰이는 카테고리 파라미터 이름 후보들을 하나씩 추가해 응답이 달라지는지 확인
    category_param_candidates = [
        {"cateCd": "12"},  # KorService2 contentTypeId=12(관광지) 체계 재사용 가정
        {"rlteCtgryLclsNm": "음식"},
        {"cate1": "A01"},
    ]
    for extra in category_param_candidates:
        params = dict(base_params)
        params.update(extra)
        _print_result(f"카테고리 필터 시도: {extra}", f"{BASE_TARRLTETAR}/searchKeyword1", _common_params(params))


if __name__ == "__main__":
    print("=== ① 지역기반 목록 조회 엔드포인트 존재 확인 ===")
    probe_area_based_list()
    print("\n\n=== ③ 카테고리 필터 파라미터 존재 확인 ===")
    probe_category_filter()
