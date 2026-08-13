import requests

from app.core.config import settings
from datetime import date

BASE_KORSERVICE = "https://apis.data.go.kr/B551011/KorService2"
MOBILE_APP = "CommaTour"
BASE_CNCTRRATE = "https://apis.data.go.kr/B551011/TatsCnctrRateService"
BASE_TARRLTETAR = "https://apis.data.go.kr/B551011/TarRlteTarService1"

def _common_params(extra: dict) -> dict:
    params = {
        "serviceKey": settings.KORSERVICE_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": MOBILE_APP,
        "_type": "json",
    }
    params.update(extra)
    return params


def _get(url: str, params: dict) -> dict:
    response = requests.get(
        url,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    api_response = data.get("response")
    if api_response is None:
        raise RuntimeError(
            "한국관광공사 API 응답 형식이 올바르지 않습니다."
        )

    header = api_response.get("header", {})
    result_code = header.get("resultCode")

    if result_code not in ("0000", "00"):
        raise RuntimeError(
            f"한국관광공사 API 오류: {header}"
        )

    return data


def _extract_items(data: dict) -> list[dict]:
    items = (
        data.get("response", {})
        .get("body", {})
        .get("items", "")
    )

    if not items:
        return []

    item = items.get("item", [])

    if isinstance(item, dict):
        return [item]

    return item


def search_tourist_spots(
    keyword: str,
    limit: int = 20,
) -> list[dict]:
    params = _common_params(
        {
            "keyword": keyword,
            "contentTypeId": "12",
            "numOfRows": limit,
            "pageNo": 1,
            "arrange": "C",
        }
    )

    data = _get(
        f"{BASE_KORSERVICE}/searchKeyword2",
        params,
    )

    return _extract_items(data)


def get_cnctr_rate_7d_avg(
    area_cd: str,
    signgu_cd: str,
    tourist_spot_name: str,
) -> float | None:
    params = _common_params(
        {
            "areaCd": area_cd,
            "signguCd": signgu_cd,
            "tAtsNm": tourist_spot_name,
            "numOfRows": 7,
            "pageNo": 1,
        }
    )

    data = _get(
        f"{BASE_CNCTRRATE}/tatsCnctrRatedList",
        params,
    )

    items = _extract_items(data)

    if not items:
        return None

    rates = []

    for item in items:
        value = item.get("cnctrRate")

        if value in (None, ""):
            continue

        try:
            rates.append(float(value))
        except (TypeError, ValueError):
            continue

    if not rates:
        return None

    return sum(rates) / len(rates)

def get_spot_overview(content_id: str) -> str | None:
    params = _common_params(
        {
            "contentId": content_id,
        }
    )

    data = _get(
        f"{BASE_KORSERVICE}/detailCommon2",
        params,
    )

    items = _extract_items(data)

    if not items:
        return None

    overview = items[0].get("overview")

    if not overview:
        return None

    return overview.strip()

def get_related_tourist_spots(
    area_cd: str,
    signgu_cd: str,
    tourist_spot_name: str,
    limit: int = 20,
) -> list[dict]:
    base_ym = date.today().strftime("%Y%m")

    params = _common_params(
        {
            "baseYm": base_ym,
            "areaCd": area_cd,
            "signguCd": signgu_cd,
            "keyword": tourist_spot_name,
            "numOfRows": limit,
            "pageNo": 1,
        }
    )

    data = _get(
        f"{BASE_TARRLTETAR}/searchKeyword1",
        params,
    )

    items = _extract_items(data)

    if items:
        return items

    previous_ym = _shift_month(base_ym, -1)

    params["baseYm"] = previous_ym

    data = _get(
        f"{BASE_TARRLTETAR}/searchKeyword1",
        params,
    )

    return _extract_items(data)
def _shift_month(base_ym: str, delta_months: int) -> str:
    year = int(base_ym[:4])
    month = int(base_ym[4:])

    total = year * 12 + (month - 1) + delta_months

    new_year, new_month = divmod(total, 12)

    return f"{new_year:04d}{new_month + 1:02d}"