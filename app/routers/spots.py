from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.spot import (
    SpotDetailResponse,
    SpotSearchResponse,
)
from app.services.tourism_api import search_tourist_spots
from app.services.spot_service import (
    get_spot_detail,
    search_spots,
    upsert_spots_from_korservice,
)


router = APIRouter(
    prefix="/api/spots",
    tags=["spots"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/search",
    response_model=SpotSearchResponse,
)
def search_spot_list(
    keyword: str | None = Query(default=None),
    sido: str | None = Query(default=None),
    sigungu: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if not any([keyword, sido, sigungu]):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "keyword, sido, sigungu 중 하나 이상 입력해야 합니다.",
                }
            },
        )
    if keyword:
        korservice_items = search_tourist_spots(
            keyword=keyword,
            limit=limit,
        )

        upsert_spots_from_korservice(
            db=db,
            items=korservice_items,
        )

    items = search_spots(
        db=db,
        keyword=keyword,
        sido=sido,
        sigungu=sigungu,
        limit=limit,
    )

    return {
        "items": items,
        "count": len(items),
    }

@router.get(
    "/{spot_id}",
    response_model=SpotDetailResponse,
)
def get_spot(
    spot_id: int,
    db: Session = Depends(get_db),
):
    spot = get_spot_detail(
        db=db,
        spot_id=spot_id,
    )

    if spot is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SPOT_NOT_FOUND",
                    "message": "관광지 정보를 찾을 수 없습니다.",
                }
            },
        )

    return spot