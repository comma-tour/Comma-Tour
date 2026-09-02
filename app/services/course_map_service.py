from io import BytesIO

import requests

from app.core.config import settings


KAKAO_STATIC_MAP_URL = (
    "https://dapi.kakao.com/v2/maps/staticmap"
)

def _get_map_level(
    mapx_values: list[float],
    mapy_values: list[float],
) -> int:
    longitude_span = max(mapx_values) - min(mapx_values)
    latitude_span = max(mapy_values) - min(mapy_values)

    span = max(
        longitude_span,
        latitude_span,
    )

    if span < 0.015:
        return 5

    if span < 0.03:
        return 6

    if span < 0.06:
        return 7

    if span < 0.12:
        return 8

    if span < 0.25:
        return 9

    return 10


def generate_course_map_image(
    route: list[dict],
) -> BytesIO | None:
    if not route:
        return None

    mapx_values = [
        item["mapx"]
        for item in route
        if item.get("mapx") is not None
    ]
    mapy_values = [
        item["mapy"]
        for item in route
        if item.get("mapy") is not None
    ]

    if not mapx_values or not mapy_values:
        return None

    center_mapx = sum(mapx_values) / len(mapx_values)
    center_mapy = sum(mapy_values) / len(mapy_values)

    map_level = _get_map_level(
        mapx_values,
        mapy_values,
    )

    markers = []

    for item in route:
        if (
            item.get("mapx") is None
            or item.get("mapy") is None
        ):
            continue

        markers.append(
            (
                "markers",
                (
                    f"location:{item['mapx']},{item['mapy']}"
                    "|option:false"
                ),
            )
        )

    headers = {
        "Authorization": (
            f"KakaoAK {settings.KAKAO_REST_API_KEY}"
        ),
    }

    params = [
        (
            "center",
            f"{center_mapx},{center_mapy}",
        ),
        (
            "size",
            "900x500",
        ),
        (
            "lv",
            str(map_level),
        ),
        (
            "format",
            "png",
        ),
        *markers,
    ]


    try:
        response = requests.get(
            KAKAO_STATIC_MAP_URL,
            headers=headers,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "",
        )

        if not content_type.startswith("image/"):
            return None

        return BytesIO(response.content)

    except Exception:
        return None