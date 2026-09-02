"""
실제 API 데이터 수집 모듈 (4순위: 실 데이터 확보)

API 키 승인 완료 후, mock_tarrltetar.py / mock_korservice.py를 대체해 실제 데이터를 가져온다.
반환 스키마(CongestedSpot, Candidate)는 mock 모듈과 동일하게 유지해, matching/ranking의 나머지
코드(similarity_matching.py, features.py, dataset_builder.py, model_comparison.py)는 수정 없이 재사용한다.

[중요 - ID 매칭 이슈]
TarRlteTarService1의 tAtsCd/rlteTatsCd와 KorService2의 contentid는 서로 다른 코드 체계다.
따라서 연관관광지 후보를 KorService2에서 다시 조회하려면 관광지명(제목)으로 검색해야 하고,
동명이인 관광지가 있으면 매칭이 틀릴 수 있다. search_korservice_by_keyword()에서
검색 결과가 여러 건이면 경고를 출력하고 첫 번째 결과를 사용한다 (완벽하지 않음, 실행 결과를 반드시 확인할 것).

[주의] 이 모듈은 로컬 네트워크(apis.data.go.kr)가 필요해 개발 샌드박스에서 테스트되지 않았다.
실행 중 에러가 나면 실제 응답 구조(XML/JSON 필드명)가 매뉴얼과 다를 수 있으니 raw 응답을 같이 확인할 것.

이 모듈은 AI 모듈이 4순위 실 데이터로 모델을 검증하기 위한 임시 데이터 수집 스크립트다.
5순위(백엔드 통합) 시점에는 은진님의 배치 수집 계층이 이 역할을 대신하며, AI 모듈은 순수 함수로
남고 이 모듈은 더 이상 프로덕션 경로에 포함되지 않는다 (2순위에서 확정한 DB 접근 경계 참고).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from matching.mock_tarrltetar import Candidate, CongestedSpot

load_dotenv()

SERVICE_KEY = os.getenv("KORSERVICE_API_KEY")
MOBILE_APP = "CommaTour"

BASE_KORSERVICE = "https://apis.data.go.kr/B551011/KorService2"
BASE_TARRLTETAR = "https://apis.data.go.kr/B551011/TarRlteTarService1"
BASE_CNCTRRATE = "https://apis.data.go.kr/B551011/TatsCnctrRateService"

# [쿼터 보호용 디스크 캐시] 이전에는 korservice_cache/cnctr_cache가 build_congested_spots_for_region()
# 안에서 매 실행마다 빈 dict로 새로 만들어져서, 스크립트를 재실행할 때마다 이미 성공했던 조회까지
# 전부 API에 다시 태웠다. 429(트래픽 한도)로 몇 번 재시도-실패를 반복하다 보니 하루 쿼터를
# 예상보다 훨씬 빨리 소진하는 원인이 됐다. 이제 조회 결과를 디스크에 저장해뒀다가 다음 실행에서
# 그대로 재사용한다 - 같은 관광지명/contentId는 다시 조회하지 않는다.
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_KORSERVICE_CACHE_PATH = _CACHE_DIR / "korservice_search_cache.json"
_CNCTR_CACHE_PATH = _CACHE_DIR / "cnctr_rate_cache.json"
_OVERVIEW_CACHE_PATH = _CACHE_DIR / "overview_cache.json"


def _load_json_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        print(f"[경고] 캐시 파일 '{path}' 읽기 실패({e}) - 빈 캐시로 시작")
        return {}


def _save_json_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)  # 원자적 교체 - 저장 도중 죽어도 기존 캐시 파일은 손상되지 않음

REQUEST_INTERVAL_SEC = 0.5  # 트래픽 한도 보호용 최소 호출 간격
# [2단계 재시도 이후에도 429 발생] 0.2초 간격(초당 5건)으로도 429 Too Many Requests가 나서
# 0.5초(초당 2건)로 늘렸다. 이건 일일 총량(1,000건) 문제가 아니라 초당/분당 순간 요청 속도
# 제한으로 보인다 - 응답이 OpenAPI_ServiceResponse 게이트웨이 에러 스키마가 아니라 HTTP 429로
# 곧바로 왔기 때문.

# (P0-3, P1-이후 개선) signgu_cd -> KorService2 addr1 매칭 힌트 (좁은 것부터 넓은 순).
# 정식 법정동코드 매핑 테이블(OT 자료 "관광지 시군구 코드정보" 파일)을 아직 반영하지 않아
# 임시로 현재 다루는 지역만 수동 등록한다. 새 지역 추가 시 여기에 한 줄 추가할 것.
#
# [2단계로 바꾼 이유] 해운대해수욕장 실행 로그 확인 결과, 정답 매칭이 "해운대구"가 아니라
# "부산광역시"의 다른 구(예: 태종대=영도구, 국제시장=중구, 롯데프리미엄아울렛=기장군)에 있는
# 케이스가 많았다. "해운대구" 1단계만으로는 이런 후보가 전부 필터를 통과 못 해 그냥 첫 번째로
# 폴백되어, 오히려 애매 매칭 비율이 27%->32%로 늘었다(recommend() 8/17 실행 로그 참고).
# 1단계(해운대구)에서 못 찾으면 2단계(부산광역시)로 넓혀서, 최소한 완전 타지역(예: '태종대(횡성)')
# 오매칭은 걸러내도록 한다.
SIGNGU_REGION_HINTS: dict[str, list[str]] = {
    "26350": ["해운대구", "부산광역시"],  # 부산광역시 해운대구 (1차 심사 범위: 과밀 판별 대상)
    "51130": ["원주시", "강원"],  # 강원 원주시 (AI 모델 검증용, 6.4절 참고)
}


def _common_params(extra: dict) -> dict:
    """세 API 공통 파라미터. serviceKey는 requests가 자동으로 URL 인코딩하므로 디코딩 키를 그대로 사용."""
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": MOBILE_APP,
        "_type": "json",
    }
    params.update(extra)
    return params


def _get(url: str, params: dict, max_retries: int = 3) -> dict:
    """
    공통 GET 요청 + 에러 체크.
    data.go.kr 게이트웨이 레벨 에러(인증키 미등록 등)는 정상 응답과 다른 스키마(OpenAPI_ServiceResponse)로
    오는 경우가 있어 별도로 처리하고, 그 외 예상치 못한 구조는 원문을 그대로 보여줘서 디버깅할 수 있게 한다.

    [재시도] 두 가지 유형을 구분해서 재시도한다:
    1) 타임아웃/연결 오류(requests.exceptions.Timeout/ConnectionError) - 일시적 네트워크 문제
    2) HTTP 429 Too Many Requests - 초당/분당 순간 요청 속도 제한 (해운대구 벌크 수집 중 실제 발생 확인,
       REQUEST_INTERVAL_SEC를 늘려도 후보 수백 건을 연속 조회하면 여전히 발생할 수 있다)
    둘 다 지수 백오프(1초 -> 2초 -> 4초...)로 최대 max_retries회 재시도한다. 그 외 4xx(429 제외)/
    게이트웨이 에러는 재시도해도 똑같이 실패할 가능성이 높아 바로 예외를 올린다.
    """
    time.sleep(REQUEST_INTERVAL_SEC)

    attempt = 0
    while True:
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                raise requests.exceptions.HTTPError("429 Too Many Requests", response=resp)
            resp.raise_for_status()
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            attempt += 1
            if attempt > max_retries:
                raise
            wait_sec = 2 ** (attempt - 1)
            print(f"[재시도] 네트워크 오류({e.__class__.__name__}) - {wait_sec}초 후 재시도 ({attempt}/{max_retries})")
            time.sleep(wait_sec)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status != 429:
                raise
            attempt += 1
            if attempt > max_retries:
                raise
            wait_sec = 2 ** attempt  # 429는 조금 더 넉넉하게 (2,4,8...초)
            print(f"[재시도] 429 Too Many Requests - {wait_sec}초 후 재시도 ({attempt}/{max_retries})")
            time.sleep(wait_sec)

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"JSON 파싱 실패. 응답 원문(앞 500자): {resp.text[:500]}")

    # 게이트웨이 레벨 에러 (예: SERVICE_KEY_IS_NOT_REGISTERED_ERROR) - response.header가 아닌 별도 스키마로 옴
    if "OpenAPI_ServiceResponse" in data:
        header = data["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
        raise RuntimeError(f"게이트웨이 에러 응답: {header}")

    response = data.get("response")
    if response is None:
        raise RuntimeError(f"예상치 못한 응답 구조 (response 키 없음). 원문(앞 500자): {json.dumps(data, ensure_ascii=False)[:500]}")

    header = response.get("header", {})
    result_code = header.get("resultCode")
    if result_code not in ("0000", "00"):
        raise RuntimeError(f"API 에러 응답: {header}")

    return data


def _extract_items(data: dict) -> list[dict]:
    """response.body.items.item을 리스트로 정규화 (item이 1건이면 dict로 오는 경우가 있어 방어적으로 처리)."""
    items = data.get("response", {}).get("body", {}).get("items", "")
    if not items:
        return []
    item = items.get("item", [])
    if isinstance(item, dict):
        return [item]
    return item


def search_korservice_by_keyword(
    keyword: str, region_hints: list[str] | None = None
) -> tuple[dict | None, bool]:
    """
    KorService2.searchKeyword2로 관광지명을 검색해 contentid/contenttypeid/mapx/mapy를 가져온다.
    [ID 매칭 이슈] 결과가 여러 건이면 경고를 출력하고 첫 번째 결과를 사용한다 - 실행 결과를 반드시 확인할 것.
    1차 검색이 실패하고 이름에 "/"(지점명 구분자로 추정)가 있으면, "/" 앞부분만으로 한 번 더 시도한다.

    [지역 불일치 위험] TarRlteTarService1의 지역코드(areaCd/signguCd)와 KorService2의
    법정동코드(lDongRegnCd/lDongSignguCd)는 서로 다른 코드 체계라, 이 함수는 지역 필터 없이 전국에서
    이름만으로 검색한다. 그래서 동명이인(예: '베니키아호텔'이 원주가 아닌 여수/천안에도 있음)이 잘못
    매칭될 수 있다. 이 함수는 (결과, is_ambiguous) 튜플을 반환해 호출부가 애매한 매칭을 표시할 수 있게 한다.

    region_hints: (P0-3, 2단계로 개선) 좁은 것부터 넓은 순으로 지역명 리스트를 넘기면
    (예: ["해운대구", "부산광역시"]), 결과가 여러 건일 때 앞 힌트부터 순서대로 addr1에 포함되는지
    확인해 처음으로 일치하는 후보 집합을 사용한다. TarRlteTarService1이 조회 기준 시군구와
    무관하게 상위 시/도 전역에서 연관관광지를 반환하는 경우가 많아, 시군구 단일 힌트만으로는
    정답이 오히려 걸러져 첫 번째로 잘못 폴백되는 사례가 있었다(해운대해수욕장 실행 로그로 확인).
    어느 힌트로도 일치 항목이 없으면 기존처럼 첫 번째를 쓴다.

    Returns:
        (매칭된 item 또는 None, 검색 결과가 2건 이상이라 애매했는지 여부)
    """
    params = _common_params({"keyword": keyword, "numOfRows": 10, "pageNo": 1, "arrange": "C"})
    data = _get(f"{BASE_KORSERVICE}/searchKeyword2", params)
    items = _extract_items(data)

    if not items and "/" in keyword:
        base_name = keyword.split("/")[0].strip()
        print(f"[안내] '{keyword}' 검색 실패 - 지점명 제거 후 '{base_name}'로 재시도")
        params["keyword"] = base_name
        data = _get(f"{BASE_KORSERVICE}/searchKeyword2", params)
        items = _extract_items(data)

    if not items:
        print(f"[경고] KorService2에서 '{keyword}' 검색 결과 없음")
        return None, False

    is_ambiguous = len(items) > 1

    if is_ambiguous and region_hints:
        for hint in region_hints:
            region_matches = [it for it in items if hint in (it.get("addr1") or "")]
            if region_matches:
                if len(region_matches) < len(items):
                    print(
                        f"[안내] '{keyword}' 검색 결과 {len(items)}건 중 '{hint}' 포함 "
                        f"{len(region_matches)}건으로 좁혀 사용"
                    )
                items = region_matches
                is_ambiguous = len(items) > 1
                break

    if is_ambiguous:
        titles = [it.get("title") for it in items]
        print(f"[경고] '{keyword}' 검색 결과 {len(items)}건(지역 필터 없음, 동명이인 가능) - 첫 번째 사용. 후보: {titles}")

    return items[0], is_ambiguous


def get_overview(content_id: str) -> str:
    """
    KorService2.detailCommon2에서 overview(소개문구)를 가져온다. detailIntro2가 아님에 유의.
    detailCommon2는 contentId만 필수로 받고 contentTypeId는 파라미터로 받지 않는다 (매뉴얼 확인).
    """
    params = _common_params({"contentId": content_id})
    data = _get(f"{BASE_KORSERVICE}/detailCommon2", params)
    items = _extract_items(data)
    if not items:
        return ""
    return items[0].get("overview", "")


def _shift_month(base_ym: str, delta_months: int) -> str:
    """YYYYMM 문자열을 delta_months만큼 이동한다 (음수면 과거)."""
    year, month = int(base_ym[:4]), int(base_ym[4:])
    total = year * 12 + (month - 1) + delta_months
    new_year, new_month = divmod(total, 12)
    return f"{new_year:04d}{new_month + 1:02d}"


def get_related_candidates(area_cd: str, signgu_cd: str, keyword: str, base_ym: str) -> list[dict]:
    """
    TarRlteTarService1.searchKeyword1로 특정 관광지의 연관관광지 후보 목록을 가져온다.

    [중요] 이 API는 매월 갱신되는 실시간 피드가 아니라, data.go.kr 공식 설명 기준
    2024년 05월 ~ 2025년 04월 사이의 고정된 스냅샷 데이터만 제공한다(그 이후로는 갱신되지 않음).
    반드시 base_ym을 이 범위(예: "202504") 안의 값으로 넘길 것 - 범위 밖의 값(예: 현재 월)을
    넘기면 area_cd/signgu_cd/keyword가 맞아도 항상 0건이 반환된다.
    결과가 0건이면 자동으로 전월 데이터로 한 번 더 시도하지만, 이 재시도도 유효 범위 밖이면
    똑같이 0건이므로 애초에 유효 범위 안의 base_ym을 넘기는 것이 중요하다.

    [페이지네이션] numOfRows=50(응답 한 페이지 최대치)으로 요청하되, totalCount가 50보다 크면
    "전체/관광지/음식/숙박 유형별 최대 각 50위"라는 API 설명대로 한 번의 호출로는 못 받는 나머지가
    있다는 뜻이므로, pageNo를 늘려가며 totalCount에 도달할 때까지 자동으로 이어받는다.
    """
    page_size = 50
    params = _common_params(
        {
            "baseYm": base_ym,
            "areaCd": area_cd,
            "signguCd": signgu_cd,
            "keyword": keyword,
            "numOfRows": page_size,
            "pageNo": 1,
        }
    )
    data = _get(f"{BASE_TARRLTETAR}/searchKeyword1", params)
    total_count = data.get("response", {}).get("body", {}).get("totalCount", 0)
    items = _extract_items(data)

    if not items:
        prev_ym = _shift_month(base_ym, -1)
        print(f"[안내] baseYm={base_ym} 결과 0건(totalCount={total_count}) - 전월({prev_ym})로 재시도")
        params["baseYm"] = prev_ym
        data = _get(f"{BASE_TARRLTETAR}/searchKeyword1", params)
        total_count = data.get("response", {}).get("body", {}).get("totalCount", 0)
        items = _extract_items(data)
        if not items:
            print(f"[경고] baseYm={prev_ym}로도 결과 0건. area_cd/signgu_cd/keyword를 확인할 것.")
            return items

    print(f"[안내] '{keyword}' baseYm={params['baseYm']} totalCount={total_count}, 1페이지 {len(items)}건 수신")

    # totalCount가 한 페이지(50건)보다 많으면 나머지 페이지를 이어서 받는다.
    page_no = 2
    while len(items) < total_count:
        params["pageNo"] = page_no
        data = _get(f"{BASE_TARRLTETAR}/searchKeyword1", params)
        more_items = _extract_items(data)
        if not more_items:
            print(f"[경고] totalCount={total_count}인데 {page_no}페이지에서 빈 응답 - 페이지네이션 중단")
            break
        items.extend(more_items)
        print(f"[안내] '{keyword}' {page_no}페이지 {len(more_items)}건 추가 수신 (누적 {len(items)}/{total_count})")
        page_no += 1

    return items



def get_related_candidates_by_area(area_cd: str, signgu_cd: str, base_ym: str) -> list[dict]:
    """
    TarRlteTarService1.areaBasedList1로 특정 지역(area_cd/signgu_cd)에 등록된
    "모든" 중심관광지-연관관광지 관계를 한 번에 가져온다 (관광지명을 몰라도 됨).

    searchKeyword1과 달리 keyword 파라미터가 없다 - 그 지역에 등록된 여러 중심관광지의
    연관목록이 tAtsNm으로 구분되어 함께 반환된다. 반환된 item 목록을 tAtsNm 기준으로
    묶으면(group by), 이 지역에 어떤 중심관광지들이 등록돼 있는지 자체를 발굴할 수 있다
    (2026-09 조사 결과: 원주시 한 곳만으로도 totalCount=800, searchKeyword1의 50건보다 훨씬 큼).

    base_ym 유효 범위는 get_related_candidates()와 동일 (RELATED_SPOT_DATA_MIN_YM~MAX_YM).
    """
    page_size = 50
    params = _common_params(
        {
            "baseYm": base_ym,
            "areaCd": area_cd,
            "signguCd": signgu_cd,
            "numOfRows": page_size,
            "pageNo": 1,
        }
    )
    data = _get(f"{BASE_TARRLTETAR}/areaBasedList1", params)
    total_count = data.get("response", {}).get("body", {}).get("totalCount", 0)
    items = _extract_items(data)
    print(f"[안내] area={area_cd}/{signgu_cd} baseYm={base_ym} totalCount={total_count}, 1페이지 {len(items)}건 수신")

    page_no = 2
    while len(items) < total_count:
        params["pageNo"] = page_no
        data = _get(f"{BASE_TARRLTETAR}/areaBasedList1", params)
        more_items = _extract_items(data)
        if not more_items:
            print(f"[경고] totalCount={total_count}인데 {page_no}페이지에서 빈 응답 - 페이지네이션 중단")
            break
        items.extend(more_items)
        print(f"[안내] area={area_cd}/{signgu_cd} {page_no}페이지 {len(more_items)}건 추가 수신 (누적 {len(items)}/{total_count})")
        page_no += 1

    return items


def get_cnctr_rate_7d_avg(area_cd: str, signgu_cd: str, tats_nm: str) -> float | None:
    """
    TatsCnctrRateService.tatsCnctrRatedList로 향후 cnctrRate를 조회해 7일 평균을 계산한다.
    numOfRows=7로 요청해 API가 반환하는 첫 7건(현재일 기준 순서대로 온다고 매뉴얼에 명시됨)을 그대로 평균낸다.
    """
    params = _common_params(
        {"areaCd": area_cd, "signguCd": signgu_cd, "tAtsNm": tats_nm, "numOfRows": 7, "pageNo": 1}
    )
    data = _get(f"{BASE_CNCTRRATE}/tatsCnctrRatedList", params)
    items = _extract_items(data)
    if not items:
        print(f"[경고] '{tats_nm}' cnctrRate 조회 결과 없음")
        return None
    rates = [float(it["cnctrRate"]) for it in items if "cnctrRate" in it]
    return sum(rates) / len(rates) if rates else None




# TarRlteTarService1(연관관광지)이 실제로 데이터를 제공하는 고정 범위: 2024년 05월 ~ 2025년 04월.
# (data.go.kr 상세설명 기준. 이 서비스는 매월 갱신되는 게 아니라 이 기간의 스냅샷만 제공한다.)
RELATED_SPOT_DATA_MIN_YM = "202405"
RELATED_SPOT_DATA_MAX_YM = "202504"
DEFAULT_BASE_YM = RELATED_SPOT_DATA_MAX_YM  # 가장 최근에 데이터가 존재하는 달


def build_real_congested_spot_with_candidates(
    area_cd: str, signgu_cd: str, tats_nm: str, base_ym: str | None = None
) -> tuple[CongestedSpot, list[Candidate]]:
    """
    실제 API 3종을 조합해 mock_tarrltetar.get_mock_congested_spot_with_candidates()와
    동일한 스키마(CongestedSpot, list[Candidate])로 반환한다.

    Args:
        area_cd: 지역코드
        signgu_cd: 시군구코드
        tats_nm: 과밀 관광지명 (사용자가 조회한 대상)
        base_ym: 연관관광지 조회 기준연월 (YYYYMM). 미지정 시 DEFAULT_BASE_YM("202504")로 자동 설정.
            [중요] TarRlteTarService1은 2024.05~2025.04 데이터만 제공하므로, 이 범위 밖의 값을
            넘기면 (예: 오늘 날짜 기준 월) 후보가 항상 0건으로 나온다. date.today()를 쓰지 말 것.
    """
    if base_ym is None:
        base_ym = DEFAULT_BASE_YM
    elif not (RELATED_SPOT_DATA_MIN_YM <= base_ym <= RELATED_SPOT_DATA_MAX_YM):
        print(
            f"[경고] base_ym={base_ym}는 TarRlteTarService1의 데이터 제공 범위"
            f"({RELATED_SPOT_DATA_MIN_YM}~{RELATED_SPOT_DATA_MAX_YM}) 밖입니다. 항상 0건이 반환될 수 있습니다."
        )

    congested = _build_congested_spot(area_cd, signgu_cd, tats_nm)
    related_items = get_related_candidates(area_cd, signgu_cd, tats_nm, base_ym)
    candidates = _build_candidates_from_raw_items(area_cd, signgu_cd, related_items, congested)
    return congested, candidates


def _build_congested_spot(
    area_cd: str,
    signgu_cd: str,
    tats_nm: str,
    cache: dict[str, dict | None] | None = None,
    overview_cache: dict[str, str] | None = None,
) -> CongestedSpot:
    """과밀 관광지 자신의 KorService2 기본정보 + overview + cnctrRate를 조합해 CongestedSpot을 만든다.

    cache: {tats_nm: (target_info, is_ambiguous)} 형태의 KorService2 검색 결과 캐시.
    같은 이름이 여러 지역 수집에서 반복 조회되는 걸 막기 위해 build_congested_spots_for_region()에서 공유한다.
    overview_cache: {content_id: overview} 캐시. get_overview()는 자체 캐시가 없어 매번 API를
    호출하므로, 여기서 감싸서 같은 contentId를 다시 조회하지 않게 한다.
    """
    region_hints = SIGNGU_REGION_HINTS.get(signgu_cd)

    if cache is not None and tats_nm in cache:
        target_info, target_ambiguous = cache[tats_nm]
    else:
        target_info, target_ambiguous = search_korservice_by_keyword(tats_nm, region_hints=region_hints)
        if cache is not None:
            cache[tats_nm] = (target_info, target_ambiguous)

    if target_info is None:
        raise ValueError(f"KorService2에서 '{tats_nm}'을 찾을 수 없습니다")
    if target_ambiguous:
        print(f"[주의] 과밀 관광지 자신('{tats_nm}')의 KorService2 매칭이 애매합니다 - 결과를 신중히 확인할 것")

    content_id = target_info["contentid"]
    if overview_cache is not None and content_id in overview_cache:
        overview = overview_cache[content_id]
    else:
        overview = get_overview(content_id)
        if overview_cache is not None:
            overview_cache[content_id] = overview

    return CongestedSpot(
        tats_nm=tats_nm,
        area_cd=area_cd,
        signgu_cd=signgu_cd,
        content_type_id=target_info["contenttypeid"],
        overview=overview,
        mapx=float(target_info["mapx"]),
        mapy=float(target_info["mapy"]),
        cnctr_rate_7d_avg=get_cnctr_rate_7d_avg(area_cd, signgu_cd, tats_nm) or 0.0,
    )


def _build_candidates_from_raw_items(
    area_cd: str,
    signgu_cd: str,
    raw_items: list[dict],
    congested: CongestedSpot,
    korservice_cache: dict[str, tuple[dict | None, bool]] | None = None,
    cnctr_cache: dict[tuple[str, str, str], float | None] | None = None,
    overview_cache: dict[str, str] | None = None,
) -> list[Candidate]:
    """TarRlteTarService1 raw item 목록 -> KorService2/cnctrRate 결합 -> Candidate 목록.

    korservice_cache/cnctr_cache/overview_cache를 넘기면 같은 이름(예: 동네 어디서나 나오는
    '스타벅스')이나 같은 contentId가 여러 중심관광지 밑에서 반복 등장할 때 API를 다시 호출하지
    않고 캐시를 재사용한다.
    """
    region_hints = SIGNGU_REGION_HINTS.get(signgu_cd)

    candidates: list[Candidate] = []
    for item in raw_items:
        rlte_name = item.get("rlteTatsNm")
        if not rlte_name:
            continue

        if korservice_cache is not None and rlte_name in korservice_cache:
            candidate_info, is_ambiguous = korservice_cache[rlte_name]
        else:
            candidate_info, is_ambiguous = search_korservice_by_keyword(rlte_name, region_hints=region_hints)
            if korservice_cache is not None:
                korservice_cache[rlte_name] = (candidate_info, is_ambiguous)

        if candidate_info is None:
            print(f"[건너뜀] '{rlte_name}' KorService2 매칭 실패")
            continue

        rlte_area_cd = item.get("rlteRegnCd", area_cd)
        rlte_signgu_cd = item.get("rlteSignguCd", signgu_cd)
        cnctr_key = (rlte_area_cd, rlte_signgu_cd, rlte_name)
        if cnctr_cache is not None and cnctr_key in cnctr_cache:
            candidate_cnctr_rate = cnctr_cache[cnctr_key]
        else:
            candidate_cnctr_rate = get_cnctr_rate_7d_avg(rlte_area_cd, rlte_signgu_cd, rlte_name)
            if cnctr_cache is not None:
                cnctr_cache[cnctr_key] = candidate_cnctr_rate

        if candidate_cnctr_rate is None:
            # [주의] TatsCnctrRateService는 관광지(contentTypeId=12) 위주로만 집중률을 제공하는 것으로 보임
            # (실행 로그에서 음식점/카페 등 후보 다수가 조회 결과 없음으로 나옴).
            # 0.0으로 채우면 "측정 안 됨"이 "전혀 안 붐빔"으로 둔갑해 cnctr_rate_gap이 부풀려지므로,
            # 과밀 관광지 자신의 cnctrRate와 동일한 값(중립, gap=0)으로 대체한다.
            candidate_cnctr_rate = congested.cnctr_rate_7d_avg
            print(f"[안내] '{rlte_name}' cnctrRate 미제공 - 중립값(과밀지와 동일)으로 대체")

        content_id = candidate_info["contentid"]
        if overview_cache is not None and content_id in overview_cache:
            overview = overview_cache[content_id]
        else:
            overview = get_overview(content_id)
            if overview_cache is not None:
                overview_cache[content_id] = overview

        candidates.append(
            Candidate(
                rlte_tats_nm=rlte_name,
                rlte_rank=int(item.get("rlteRank", 0)),
                rlte_ctgry_lcls_nm=item.get("rlteCtgryLclsNm", ""),
                rlte_ctgry_mcls_nm=item.get("rlteCtgryMclsNm", ""),
                rlte_ctgry_scls_nm=item.get("rlteCtgrySclsNm", ""),
                overview=overview,
                mapx=float(candidate_info["mapx"]),
                mapy=float(candidate_info["mapy"]),
                cnctr_rate_7d_avg=candidate_cnctr_rate,
                is_region_ambiguous=is_ambiguous,
            )
        )

    return candidates


def build_congested_spots_for_region(
    area_cd: str, signgu_cd: str, base_ym: str | None = None
) -> list[tuple[CongestedSpot, list[Candidate]]]:
    """
    areaBasedList1로 지역 전체를 한 번에 수집해, 그 지역에 등록된 모든 중심관광지 각각에 대해
    (CongestedSpot, list[Candidate])를 만들어 반환한다. TARGET_SPOTS처럼 관광지 이름을
    미리 알 필요가 없다 - tAtsNm 기준으로 raw item을 그룹핑해서 자동으로 중심관광지 목록을 발굴한다.

    KorService2/cnctrRate/overview 조회는 이름·contentId 기준으로 캐싱되어, 같은 이름/콘텐츠가
    여러 중심관광지의 후보로 반복 등장해도 API를 중복 호출하지 않는다. 이 캐시는 디스크
    (data/cache/*.json)에도 저장되어 스크립트를 재실행해도 유지된다 - 429(트래픽 한도)로 중간에
    멈춘 뒤 다시 실행해도 이미 성공했던 조회는 API를 다시 태우지 않는다.
    """
    if base_ym is None:
        base_ym = DEFAULT_BASE_YM

    raw_items = get_related_candidates_by_area(area_cd, signgu_cd, base_ym)

    by_center: dict[str, list[dict]] = {}
    for item in raw_items:
        center_name = item.get("tAtsNm")
        if not center_name:
            continue
        by_center.setdefault(center_name, []).append(item)

    korservice_cache: dict[str, tuple[dict | None, bool]] = _load_json_cache(_KORSERVICE_CACHE_PATH)
    cnctr_cache_raw: dict[str, float | None] = _load_json_cache(_CNCTR_CACHE_PATH)
    # cnctr_cache의 키는 튜플이라 JSON에 그대로 못 담는다 - "area|signgu|name" 문자열로 저장/복원한다.
    cnctr_cache: dict[tuple[str, str, str], float | None] = {
        tuple(k.split("|", 2)): v for k, v in cnctr_cache_raw.items()  # type: ignore[misc]
    }
    overview_cache: dict[str, str] = _load_json_cache(_OVERVIEW_CACHE_PATH)

    def _flush_caches() -> None:
        _save_json_cache(_KORSERVICE_CACHE_PATH, korservice_cache)
        _save_json_cache(_CNCTR_CACHE_PATH, {"|".join(k): v for k, v in cnctr_cache.items()})
        _save_json_cache(_OVERVIEW_CACHE_PATH, overview_cache)

    results: list[tuple[CongestedSpot, list[Candidate]]] = []
    for center_name, items in by_center.items():
        print(f"\n=== {center_name} (지역기반, 원본 후보 {len(items)}건) ===")
        # [수정] 429는 requests.exceptions.HTTPError로 올라오지 RuntimeError가 아니다 - 예전에
        # (ValueError, RuntimeError)로만 잡아서 429가 그대로 새어나가 지역 수집 함수 전체를 죽이고
        # 이미 모은 results까지 날렸다(부산시립미술관에서 재현됨). requests 예외 계열까지 넓게 잡는다.
        try:
            congested = _build_congested_spot(
                area_cd, signgu_cd, center_name, cache=korservice_cache, overview_cache=overview_cache
            )
        except (ValueError, RuntimeError, requests.exceptions.RequestException) as e:
            print(f"[건너뜀] '{center_name}' 수집 실패: {e}")
            _flush_caches()
            continue

        # [중요] 마찬가지로 이 지점 하나만 건너뛰고 이미 모은 results는 지킨다. results가 지역
        # 수집 함수 끝에서야 반환되는 로컬 변수라, 중간에 예외가 새면 호출부가 아무것도 못 받아
        # build_multi_spot_dataset.py에서 "총 0건"이 되는 게 반복됐던 원인이다.
        try:
            candidates = _build_candidates_from_raw_items(
                area_cd,
                signgu_cd,
                items,
                congested,
                korservice_cache=korservice_cache,
                cnctr_cache=cnctr_cache,
                overview_cache=overview_cache,
            )
        except Exception as e:  # noqa: BLE001 - 한 지점 실패가 이미 모은 다른 지점 결과를 날리지 않도록
            print(f"[건너뜀] '{center_name}' 후보 수집 중 오류로 제외: {e}")
            _flush_caches()
            continue

        # [체크포인트] 지점 하나가 끝날 때마다 캐시를 디스크에 저장한다. 이후 지점에서 429가 나서
        # 이 함수 자체가 통째로 죽더라도(예: 위 두 try로도 못 막는 예상 밖 예외), 여기까지 성공한
        # 조회 결과는 캐시 파일에 남아 다음 실행에서 재사용된다.
        _flush_caches()

        if not candidates:
            print(f"[건너뜀] '{center_name}' KorService2 매칭 성공한 후보 0건 - 데이터셋에서 제외")
            continue

        print(f"'{center_name}' 완료: 후보 {len(candidates)}건 (원본 {len(items)}건 중 매칭 성공)")
        results.append((congested, candidates))

    return results


if __name__ == "__main__":
    # 실행: python -m matching.live_api_client  (ai/ 폴더 안에서)
    # 먼저 관광지 1곳으로만 테스트해볼 것. 매뉴얼 예제에 나온 "간현관광지"(강원 원주시)로 기본 세팅.
    if not SERVICE_KEY:
        raise SystemExit(".env의 KORSERVICE_API_KEY가 비어있습니다. 디코딩 키를 넣었는지 확인하세요.")

    congested, candidates = build_real_congested_spot_with_candidates(
        area_cd="51", signgu_cd="51130", tats_nm="간현관광지"
    )

    print(f"과밀 관광지: {congested.tats_nm}")
    print(f"  overview: {congested.overview[:60]}...")
    print(f"  cnctrRate(7일평균): {congested.cnctr_rate_7d_avg}")
    ambiguous_count = sum(1 for c in candidates if c.is_region_ambiguous)
    print(f"\n연관관광지 후보 {len(candidates)}개 (지역 매칭 애매 {ambiguous_count}개)")
    for c in candidates[:10]:
        flag = " [애매]" if c.is_region_ambiguous else ""
        print(f"  - {c.rlte_tats_nm}{flag} (rlteRank={c.rlte_rank}, {c.rlte_ctgry_mcls_nm}, cnctrRate={c.cnctr_rate_7d_avg})")
