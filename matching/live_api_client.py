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
from datetime import date

import requests
from dotenv import load_dotenv

from matching.mock_tarrltetar import Candidate, CongestedSpot

load_dotenv()

SERVICE_KEY = os.getenv("KORSERVICE_API_KEY")
MOBILE_APP = "CommaTour"

BASE_KORSERVICE = "https://apis.data.go.kr/B551011/KorService2"
BASE_TARRLTETAR = "https://apis.data.go.kr/B551011/TarRlteTarService1"
BASE_CNCTRRATE = "https://apis.data.go.kr/B551011/TatsCnctrRateService"

REQUEST_INTERVAL_SEC = 0.2  # 개발계정 트래픽 한도(일 1,000건) 보호용 최소 호출 간격


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


def _get(url: str, params: dict) -> dict:
    """
    공통 GET 요청 + 에러 체크.
    data.go.kr 게이트웨이 레벨 에러(인증키 미등록 등)는 정상 응답과 다른 스키마(OpenAPI_ServiceResponse)로
    오는 경우가 있어 별도로 처리하고, 그 외 예상치 못한 구조는 원문을 그대로 보여줘서 디버깅할 수 있게 한다.
    """
    time.sleep(REQUEST_INTERVAL_SEC)
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()

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


def search_korservice_by_keyword(keyword: str) -> tuple[dict | None, bool]:
    """
    KorService2.searchKeyword2로 관광지명을 검색해 contentid/contenttypeid/mapx/mapy를 가져온다.
    [ID 매칭 이슈] 결과가 여러 건이면 경고를 출력하고 첫 번째 결과를 사용한다 - 실행 결과를 반드시 확인할 것.
    1차 검색이 실패하고 이름에 "/"(지점명 구분자로 추정)가 있으면, "/" 앞부분만으로 한 번 더 시도한다.

    [지역 불일치 위험] TarRlteTarService1의 지역코드(areaCd/signguCd)와 KorService2의
    법정동코드(lDongRegnCd/lDongSignguCd)는 서로 다른 코드 체계라, 이 함수는 지역 필터 없이 전국에서
    이름만으로 검색한다. 그래서 동명이인(예: '베니키아호텔'이 원주가 아닌 여수/천안에도 있음)이 잘못
    매칭될 수 있다. 이 함수는 (결과, is_ambiguous) 튜플을 반환해 호출부가 애매한 매칭을 표시할 수 있게 한다.

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

    [주의] 이 API는 월 1회(매월 8일) 갱신이라, 조회 시점이 매월 초입이면 이번 달(base_ym) 데이터가
    아직 반영 안 됐을 수 있다. 결과가 0건이면 자동으로 전월 데이터로 한 번 더 시도한다.
    """
    params = _common_params(
        {
            "baseYm": base_ym,
            "areaCd": area_cd,
            "signguCd": signgu_cd,
            "keyword": keyword,
            "numOfRows": 50,
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
        items = _extract_items(data)
        if not items:
            print(f"[경고] baseYm={prev_ym}로도 결과 0건. area_cd/signgu_cd/keyword를 확인할 것.")

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
        base_ym: 연관관광지 조회 기준연월 (YYYYMM). 미지정 시 이번 달로 자동 설정.
    """
    if base_ym is None:
        base_ym = date.today().strftime("%Y%m")

    # 1. 과밀 관광지 자신의 기본정보 + overview + cnctrRate
    target_info, target_ambiguous = search_korservice_by_keyword(tats_nm)
    if target_info is None:
        raise ValueError(f"KorService2에서 '{tats_nm}'을 찾을 수 없습니다")
    if target_ambiguous:
        print(f"[주의] 과밀 관광지 자신('{tats_nm}')의 KorService2 매칭이 애매합니다 - 결과를 신중히 확인할 것")

    congested = CongestedSpot(
        tats_nm=tats_nm,
        area_cd=area_cd,
        signgu_cd=signgu_cd,
        content_type_id=target_info["contenttypeid"],
        overview=get_overview(target_info["contentid"]),
        mapx=float(target_info["mapx"]),
        mapy=float(target_info["mapy"]),
        cnctr_rate_7d_avg=get_cnctr_rate_7d_avg(area_cd, signgu_cd, tats_nm) or 0.0,
    )

    # 2. 연관관광지 후보 목록
    related_items = get_related_candidates(area_cd, signgu_cd, tats_nm, base_ym)

    candidates: list[Candidate] = []
    for item in related_items:
        rlte_name = item.get("rlteTatsNm")
        if not rlte_name:
            continue

        candidate_info, is_ambiguous = search_korservice_by_keyword(rlte_name)
        if candidate_info is None:
            print(f"[건너뜀] '{rlte_name}' KorService2 매칭 실패")
            continue

        candidate_cnctr_rate = get_cnctr_rate_7d_avg(
            item.get("rlteRegnCd", area_cd), item.get("rlteSignguCd", signgu_cd), rlte_name
        )
        if candidate_cnctr_rate is None:
            # [주의] TatsCnctrRateService는 관광지(contentTypeId=12) 위주로만 집중률을 제공하는 것으로 보임
            # (실행 로그에서 음식점/카페 등 후보 다수가 조회 결과 없음으로 나옴).
            # 0.0으로 채우면 "측정 안 됨"이 "전혀 안 붐빔"으로 둔갑해 cnctr_rate_gap이 부풀려지므로,
            # 과밀 관광지 자신의 cnctrRate와 동일한 값(중립, gap=0)으로 대체한다.
            candidate_cnctr_rate = congested.cnctr_rate_7d_avg
            print(f"[안내] '{rlte_name}' cnctrRate 미제공 - 중립값(과밀지와 동일)으로 대체")

        candidates.append(
            Candidate(
                rlte_tats_nm=rlte_name,
                rlte_rank=int(item.get("rlteRank", 0)),
                rlte_ctgry_lcls_nm=item.get("rlteCtgryLclsNm", ""),
                rlte_ctgry_mcls_nm=item.get("rlteCtgryMclsNm", ""),
                rlte_ctgry_scls_nm=item.get("rlteCtgrySclsNm", ""),
                overview=get_overview(candidate_info["contentid"]),
                mapx=float(candidate_info["mapx"]),
                mapy=float(candidate_info["mapy"]),
                cnctr_rate_7d_avg=candidate_cnctr_rate,
                is_region_ambiguous=is_ambiguous,
            )
        )

    return congested, candidates


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
