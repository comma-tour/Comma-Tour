from datetime import timedelta

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.api_cache_service import get_or_fetch


KAKAO_DIRECTIONS_URL = (
    "https://apis-navi.kakaomobility.com/v1/directions"
)

# 길찾기 결과(거리/소요시간)는 도로가 새로 나지 않는 한 잘 안 바뀐다.
# 90일 캐시로 잡아도 데이터 신선도 손해가 거의 없고, quota를 크게 아낄 수 있다.
ROUTE_CACHE_TTL = timedelta(days=90)


def get_driving_route(
    origin_mapx: float,
    origin_mapy: float,
    destination_mapx: float,
    destination_mapy: float,
) -> dict:
    headers = {
        "Authorization": (
            f"KakaoAK {settings.KAKAO_REST_API_KEY}"
        ),
    }

    params = {
        "origin": (
            f"{origin_mapx},{origin_mapy}"
        ),
        "destination": (
            f"{destination_mapx},{destination_mapy}"
        ),
        "priority": "RECOMMEND",
    }

    response = requests.get(
        KAKAO_DIRECTIONS_URL,
        headers=headers,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    routes = data.get("routes", [])

    if not routes:
        raise RuntimeError(
            "Kakao 길찾기 결과가 없습니다."
        )

    route = routes[0]

    if route.get("result_code") != 0:
        raise RuntimeError(
            "Kakao 길찾기에 실패했습니다."
        )

    summary = route.get("summary", {})

    distance_m = summary.get("distance")
    duration_sec = summary.get("duration")

    if distance_m is None or duration_sec is None:
        raise RuntimeError(
            "Kakao 길찾기 요약 정보가 없습니다."
        )

    path = []

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes", [])

            for index in range(
                0,
                len(vertexes),
                2,
            ):
                if index + 1 >= len(vertexes):
                    break

                path.append(
                    {
                        "mapx": vertexes[index],
                        "mapy": vertexes[index + 1],
                    }
                )

    return {
        "distanceKm": round(
            distance_m / 1000,
            2,
        ),
        "durationMinutes": round(
            duration_sec / 60,
        ),
        "path": path,
    }


def get_driving_route_cached(
    db: Session,
    origin_spot_id: int,
    origin_mapx: float,
    origin_mapy: float,
    destination_spot_id: int,
    destination_mapx: float,
    destination_mapy: float,
) -> dict:
    """
    spot id 쌍을 캐시 키로 써서 get_driving_route()를 감싼 버전.
    같은 (출발지, 도착지) 쌍은 90일 동안 실시간 API를 다시 부르지 않는다.

    순서(출발→도착)가 바뀌면 다른 캐시 키로 취급한다. 카카오 길찾기는 편도 기준
    소요시간이 달라질 수 있어(일방통행 등) 방향을 구분하는 게 안전하다.
    """
    cache_key = f"kakao_route:{origin_spot_id}:{destination_spot_id}"

    return get_or_fetch(
        db=db,
        cache_key=cache_key,
        ttl=ROUTE_CACHE_TTL,
        fetch_fn=lambda: get_driving_route(
            origin_mapx=origin_mapx,
            origin_mapy=origin_mapy,
            destination_mapx=destination_mapx,
            destination_mapy=destination_mapy,
        ),
    )