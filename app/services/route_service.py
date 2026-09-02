import requests

from app.core.config import settings


KAKAO_DIRECTIONS_URL = (
    "https://apis-navi.kakaomobility.com/v1/directions"
)


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