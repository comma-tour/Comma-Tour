import json
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_cache import ApiCache


def get_or_fetch(
    db: Session,
    cache_key: str,
    ttl: timedelta,
    fetch_fn: Callable[[], dict],
) -> dict:
    """
    cache_key로 캐시를 조회하고, ttl 이내면 캐시된 값을 그대로 반환한다.
    캐시가 없거나 만료됐으면 fetch_fn()을 실행해 실시간 조회하고, 결과를 캐시에 저장한 뒤 반환한다.

    fetch_fn 실행 중 예외가 나면 캐시에 아무것도 쓰지 않고 그대로 예외를 올린다.
    (호출부에서 fallback을 원하면 fetch_fn 자체에서 처리할 것.)
    """
    cached = db.scalar(
        select(ApiCache).where(ApiCache.cache_key == cache_key)
    )

    if cached is not None and datetime.utcnow() - cached.fetched_at < ttl:
        return json.loads(cached.payload_json)

    payload = fetch_fn()

    if cached is None:
        cached = ApiCache(
            cache_key=cache_key,
            payload_json=json.dumps(payload),
            fetched_at=datetime.utcnow(),
        )
        db.add(cached)
    else:
        cached.payload_json = json.dumps(payload)
        cached.fetched_at = datetime.utcnow()

    db.commit()

    return payload
