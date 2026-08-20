from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.spot import Spot
from app.services.tourism_api import (
    get_cnctr_rate_7d_avg,
    get_spot_overview,
)

def get_congestion_level(rate: float | None) -> str:
    if rate is None:
        return "UNKNOWN"

    if rate < 30:
        return "LOW"
    if rate < 50:
        return "MEDIUM"
    if rate < 70:
        return "HIGH"

    return "VERY_HIGH"

def search_spots(
    db: Session,
    keyword: str | None = None,
    sido: str | None = None,
    sigungu: str | None = None,
    limit: int = 20,
) -> list[dict]:
    stmt = select(Spot)

    if keyword:
        normalized_keyword = " ".join(keyword.split())
        compact_keyword = normalized_keyword.replace(" ", "")

        stmt = stmt.where(
            func.replace(
                Spot.tourist_spot_name,
                " ",
                "",
            ).ilike(f"%{compact_keyword}%")
        )

    if sido:
        stmt = stmt.where(
            Spot.sido == sido.strip()
        )

    if sigungu:
        stmt = stmt.where(
            Spot.sigungu == sigungu.strip()
        )

    stmt = stmt.limit(limit)

    spots = db.scalars(stmt).all()

    return [
        {
            "spotId": spot.id,
            "tAtsNm": spot.tourist_spot_name,
            "address": spot.address,
            "imageUrl": spot.image_url,
            "summary": spot.summary,
            "cnctrRate7dAvg": spot.cnctr_rate_7d_avg,
            "congestionLevel": get_congestion_level(
                spot.cnctr_rate_7d_avg
            ),
            "mapx": spot.mapx,
            "mapy": spot.mapy,
        }
        for spot in spots
    ]

def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def upsert_spot_from_korservice(
    db: Session,
    item: dict,
) -> Spot:
    content_id = item.get("contentid")

    if not content_id:
        raise ValueError("KorService 응답에 contentid가 없습니다.")

    spot = db.scalar(
        select(Spot).where(Spot.content_id == str(content_id))
    )

    if spot is None:
        spot = Spot(
            content_id=str(content_id),
            tourist_spot_name=item.get("title") or "이름 없음",
        )
        db.add(spot)

    spot.tourist_spot_name = (
        item.get("title") or spot.tourist_spot_name
    )

    spot.content_type_id = (
        str(item.get("contenttypeid"))
        if item.get("contenttypeid")
        else None
    )

    region_code = item.get("lDongRegnCd")
    sigungu_code = item.get("lDongSignguCd")

    if region_code:
        spot.area_cd = str(region_code)

    if region_code and sigungu_code:
        spot.signgu_cd = f"{region_code}{sigungu_code}"

    spot.address = item.get("addr1") or None

    spot.image_url = (
        item.get("firstimage")
        or item.get("firstimage2")
        or None
    )

    try:
        spot.summary = get_spot_overview(
            str(content_id)
        )
    except Exception:
        spot.summary = spot.summary

    spot.mapx = _to_float(item.get("mapx"))
    spot.mapy = _to_float(item.get("mapy"))

    if spot.area_cd and spot.signgu_cd:
        try:
            spot.cnctr_rate_7d_avg = get_cnctr_rate_7d_avg(
                area_cd=spot.area_cd,
                signgu_cd=spot.signgu_cd,
                tourist_spot_name=spot.tourist_spot_name,
            )
        except Exception:
            spot.cnctr_rate_7d_avg = None


    db.flush()

    return spot


def upsert_spots_from_korservice(
    db: Session,
    items: list[dict],
) -> list[Spot]:
    spots = [
        upsert_spot_from_korservice(db, item)
        for item in items
    ]

    db.commit()

    return spots

def get_spot_detail(
    db: Session,
    spot_id: int,
) -> dict | None:
    spot = db.get(Spot, spot_id)

    if spot is None:
        return None

    return {
        "spotId": spot.id,
        "tAtsNm": spot.tourist_spot_name,
        "address": spot.address,
        "imageUrl": spot.image_url,
        "summary": spot.summary,
        "category": {
            "large": spot.category_large,
            "medium": spot.category_medium,
            "small": spot.category_small,
        },
        "cnctrRate7dAvg": spot.cnctr_rate_7d_avg,
        "congestionLevel": get_congestion_level(
            spot.cnctr_rate_7d_avg
        ),
        "mapx": spot.mapx,
        "mapy": spot.mapy,
    }