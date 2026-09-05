"""
카카오모빌리티 자동차 길찾기 API 클라이언트 (6순위: 학습 데이터에 실제 이동시간 채우기)

live_api_client.py와 마찬가지로 학습 데이터 수집(오프라인 스크립트) 전용이다.
5순위(백엔드 통합) 이후 서빙 시점의 이동시간 조회는 backend/app/services/route_service.py의
get_driving_route_cached()가 담당하고(DB 캐시), 이 모듈은 여기에 관여하지 않는다
(2순위에서 확정한 DB 접근 경계와 동일한 이유로, AI 모듈은 프로덕션 서빙 경로에 포함되지 않는다).

[쿼터/속도 제한 조사 결과]
카카오모빌리티 자동차 길찾기 API는 일일 무료 10,000건으로 TourAPI(1,000건)보다 넉넉하지만,
개발자 커뮤니티에 "총량은 남아있어도 짧은 시간에 연속 호출(약 50회)하면 API limit exceeded가
뜬다"는 보고가 있다 - TarRlteTarService1 후보가 최대 50건까지 나오는 지금 상황과 정확히
겹치는 시나리오라, live_api_client.py와 동일하게 디스크 캐시 + 호출 간격 제한을 둔다.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"

# TourAPI 쪽과 동일한 이유(순간 요청 속도 제한)로 호출 간격을 둔다.
# 카카오는 일일 총량이 넉넉해 TourAPI보다는 짧게 잡아도 되지만, 안전하게 동일한 값으로 시작한다.
REQUEST_INTERVAL_SEC = 0.5

_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_ROUTE_CACHE_PATH = _CACHE_DIR / "kakao_route_cache.json"

# 좌표를 그대로 캐시 키로 쓰면 부동소수점 오차로 같은 지점이 다른 키가 될 수 있어 소수 5자리(약 1m 오차)로 반올림한다.
_COORD_PRECISION = 5


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


def _route_cache_key(origin_mapx: float, origin_mapy: float, destination_mapx: float, destination_mapy: float) -> str:
    o_x = round(origin_mapx, _COORD_PRECISION)
    o_y = round(origin_mapy, _COORD_PRECISION)
    d_x = round(destination_mapx, _COORD_PRECISION)
    d_y = round(destination_mapy, _COORD_PRECISION)
    return f"{o_x},{o_y}->{d_x},{d_y}"


def get_travel_time_minutes(
    origin_mapx: float,
    origin_mapy: float,
    destination_mapx: float,
    destination_mapy: float,
    cache: dict[str, float | None] | None = None,
) -> float | None:
    """
    두 좌표 간 실제 자동차 이동시간(분)을 조회한다. 실패하면 None을 반환한다(호출부가
    ranking/features.py의 estimate_travel_time_minutes_fallback()으로 대체하도록 값을 비워둔다).

    cache를 넘기면 "성공한" 조회만 캐시에 남는다 (같은 좌표 쌍은 API를 다시 안 부름).
    실패/키 미설정으로 인한 None은 캐시하지 않는다 - 그대로 캐시했다가는 나중에
    KAKAO_REST_API_KEY를 설정해도 이미 저장된 null 때문에 영영 재시도가 안 되는 문제가 있다.
    """
    cache_key = _route_cache_key(origin_mapx, origin_mapy, destination_mapx, destination_mapy)

    if cache is not None and cache_key in cache:
        return cache[cache_key]

    if not KAKAO_REST_API_KEY:
        print("[경고] KAKAO_REST_API_KEY가 설정되지 않았습니다 - travel_time_minutes를 폴백으로 남깁니다.")
        return None

    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "origin": f"{origin_mapx},{origin_mapy}",
        "destination": f"{destination_mapx},{destination_mapy}",
        "priority": "RECOMMEND",
    }

    time.sleep(REQUEST_INTERVAL_SEC)

    try:
        response = requests.get(KAKAO_DIRECTIONS_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        routes = data.get("routes", [])
        if not routes or routes[0].get("result_code") != 0:
            raise RuntimeError(f"카카오 길찾기 실패: {data}")

        duration_sec = routes[0]["summary"]["duration"]
        minutes = round(duration_sec / 60, 1)

    except (requests.exceptions.RequestException, RuntimeError, KeyError) as e:
        print(f"[경고] 카카오 길찾기 조회 실패({e}) - 이 쌍은 폴백으로 남깁니다.")
        return None  # 캐시하지 않는다 - 다음 실행에서 재시도 가능하도록

    if cache is not None:
        cache[cache_key] = minutes

    return minutes


def fill_travel_times(congested, candidates: list) -> list:
    """
    과밀 관광지 1곳 + 후보 목록에 대해, 각 (과밀지, 후보) 쌍의 실제 이동시간을 조회해
    candidate.travel_time_minutes를 채운 새 Candidate 목록을 반환한다.

    조회 실패(또는 API 키 미설정)한 쌍은 travel_time_minutes=None으로 남아서, 이후
    ranking/dataset_builder.py의 폴백 로직(Haversine 기반 추정)이 대신 처리한다.
    """
    from dataclasses import replace

    cache = _load_json_cache(_ROUTE_CACHE_PATH)

    filled = []
    for c in candidates:
        minutes = get_travel_time_minutes(
            congested.mapx, congested.mapy, c.mapx, c.mapy, cache=cache
        )
        filled.append(replace(c, travel_time_minutes=minutes))

    _save_json_cache(_ROUTE_CACHE_PATH, cache)
    return filled


if __name__ == "__main__":
    # 데모: mock 데이터로 API 연결이 정상 동작하는지 확인
    # 실행: python -m matching.kakao_mobility_client  (ai/ 폴더 안에서, .env에 KAKAO_REST_API_KEY 필요)
    from ranking.features import coord_distance_km, estimate_travel_time_minutes_fallback
    from matching.mock_tarrltetar import get_mock_congested_spot_with_candidates

    congested, candidates = get_mock_congested_spot_with_candidates()
    filled = fill_travel_times(congested, candidates)

    for c in filled:
        if c.travel_time_minutes is not None:
            print(f"{c.rlte_tats_nm}: {c.travel_time_minutes}분 (카카오 실측)")
        else:
            # 실제 파이프라인(dataset_builder.py, recommend.py)이 자동으로 적용하는 폴백을
            # 여기서도 미리 보여준다 - 라우팅 실패 시 실제로 무슨 값이 쓰이는지 확인용.
            distance_km = coord_distance_km(congested.mapx, congested.mapy, c.mapx, c.mapy)
            fallback_minutes = estimate_travel_time_minutes_fallback(distance_km)
            print(f"{c.rlte_tats_nm}: None (카카오 미조회) -> 폴백 추정 {fallback_minutes:.1f}분 (직선거리 {distance_km:.1f}km 기준)")
