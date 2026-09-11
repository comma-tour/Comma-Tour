import secrets
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.shared_course import SharedCourse
from app.models.spot import Spot
from app.services.route_service import get_driving_route
from app.services.spot_service import get_congestion_level


def _distance_km(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """
    두 WGS84 좌표 사이의 직선 거리를 Haversine 공식으로 계산한다.
    """
    radius = 6371.0

    lon1_rad = radians(lon1)
    lat1_rad = radians(lat1)
    lon2_rad = radians(lon2)
    lat2_rad = radians(lat2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(dlon / 2) ** 2
    )

    c = 2 * asin(sqrt(a))

    return radius * c


def _nearest_neighbor(spots: list[Spot]) -> list[Spot]:
    if not spots:
        return []

    # 요청 spotIds의 첫 번째 관광지를 출발점으로 사용한다.
    ordered = [spots[0]]
    remaining = spots[1:]

    while remaining:
        current = ordered[-1]

        next_spot = min(
            remaining,
            key=lambda spot: _distance_km(
                current.mapx,
                current.mapy,
                spot.mapx,
                spot.mapy,
            ),
        )

        ordered.append(next_spot)
        remaining.remove(next_spot)

    return ordered

def _nearest_neighbor_by_driving_distance(
    spots: list[Spot],
) -> tuple[list[Spot], dict[tuple[int, int], dict]]:
    if not spots:
        return [], {}

    ordered = [spots[0]]
    remaining = spots[1:]

    route_cache: dict[tuple[int, int], dict] = {}

    while remaining:
        current = ordered[-1]

        candidates = []

        for spot in remaining:
            cache_key = (
                current.id,
                spot.id,
            )

            try:
                driving_route = get_driving_route(
                    origin_mapx=current.mapx,
                    origin_mapy=current.mapy,
                    destination_mapx=spot.mapx,
                    destination_mapy=spot.mapy,
                )

                route_cache[cache_key] = driving_route

                distance = driving_route["distanceKm"]

            except Exception:
                distance = _distance_km(
                    current.mapx,
                    current.mapy,
                    spot.mapx,
                    spot.mapy,
                )

            candidates.append(
                (
                    distance,
                    spot,
                )
            )

        _, next_spot = min(
            candidates,
            key=lambda item: item[0],
        )

        ordered.append(next_spot)
        remaining.remove(next_spot)

    return ordered, route_cache


def create_course(
    db: Session,
    spot_ids: list[int],
) -> dict:
    # 중복 관광지 차단
    if len(set(spot_ids)) != len(spot_ids):
        raise ValueError(
            "동일한 관광지를 중복 선택할 수 없습니다."
        )

    spots_by_id = {
        spot.id: spot
        for spot in db.scalars(
            select(Spot).where(Spot.id.in_(spot_ids))
        ).all()
    }

    missing_ids = [
        spot_id
        for spot_id in spot_ids
        if spot_id not in spots_by_id
    ]

    if missing_ids:
        raise LookupError(
            f"존재하지 않는 관광지 ID가 있습니다: {missing_ids}"
        )

    # 사용자가 전달한 첫 번째 spotId를 시작점으로 유지
    spots = [
        spots_by_id[spot_id]
        for spot_id in spot_ids
    ]

    for spot in spots:
        if spot.mapx is None or spot.mapy is None:
            raise ValueError(
                f"{spot.tourist_spot_name}의 좌표 정보가 없습니다."
            )

    ordered_spots, route_cache = (
        _nearest_neighbor_by_driving_distance(spots)
    )

    total_distance = 0.0
    total_travel_time = 0
    path = []

    try:
        for index in range(len(ordered_spots) - 1):
            current = ordered_spots[index]
            next_spot = ordered_spots[index + 1]

            cache_key = (
                current.id,
                next_spot.id,
            )

            driving_route = route_cache.get(
                cache_key,
            )

            if driving_route is None:
                driving_route = get_driving_route(
                    origin_mapx=current.mapx,
                    origin_mapy=current.mapy,
                    destination_mapx=next_spot.mapx,
                    destination_mapy=next_spot.mapy,
                )

            total_distance += driving_route["distanceKm"]
            total_travel_time += driving_route["durationMinutes"]

            segment_path = driving_route["path"]

            if path and segment_path:
                segment_path = segment_path[1:]

            path.extend(segment_path)

    except Exception:
        total_distance = 0.0
        total_travel_time = 0

        for index in range(len(ordered_spots) - 1):
            current = ordered_spots[index]
            next_spot = ordered_spots[index + 1]

            total_distance += _distance_km(
                current.mapx,
                current.mapy,
                next_spot.mapx,
                next_spot.mapy,
            )

        path = [
            {
                "mapx": spot.mapx,
                "mapy": spot.mapy,
            }
            for spot in ordered_spots
        ]

    route = []

    for index, spot in enumerate(
        ordered_spots,
        start=1,
    ):
        category = (
            spot.category_small
            or spot.category_medium
            or spot.category_large
        )

        route.append(
            {
                "order": index,
                "spotId": spot.id,
                "tAtsNm": spot.tourist_spot_name,
                "category": category,
                "cnctrRate7dAvg": spot.cnctr_rate_7d_avg,
                "congestionLevel": get_congestion_level(
                    spot.cnctr_rate_7d_avg
                ),
                "address": spot.address,
                "imageUrl": spot.image_url,
                "summary": spot.summary,
                "mapx": spot.mapx,
                "mapy": spot.mapy,
            }
        )


    return {
        "course": {
            "spotCount": len(ordered_spots),
            "totalDistanceKm": round(
                total_distance,
                2,
            ),
            "totalTravelTimeMinutes": total_travel_time,
            "route": route,
            "path": path,
        }
    }

def create_shared_course(
    db: Session,
    spot_ids: list[int],
) -> dict:
    # 먼저 코스 생성이 가능한 유효한 spotIds인지 검증
    create_course(
        db=db,
        spot_ids=spot_ids,
    )

    while True:
        share_id = secrets.token_urlsafe(6)

        existing = db.get(
            SharedCourse,
            share_id,
        )

        if existing is None:
            break

    shared_course = SharedCourse(
        share_id=share_id,
        spot_ids=spot_ids,
    )

    db.add(shared_course)
    db.commit()

    return {
        "shareId": share_id,
        "shareUrl": (
            f"{settings.FRONTEND_BASE_URL.rstrip('/')}"
            f"/course/{share_id}"
        ),
    }


def get_shared_course(
    db: Session,
    share_id: str,
) -> dict | None:
    shared = db.get(
        SharedCourse,
        share_id,
    )

    if shared is None:
        return None

    result = create_course(
        db=db,
        spot_ids=shared.spot_ids,
    )

    return {
        "shareId": share_id,
        "course": result["course"],
    }