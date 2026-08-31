from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendation_service import (
    create_recommendations,
)


router = APIRouter(
    prefix="/api/recommendations",
    tags=["recommendations"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=RecommendationResponse,
)
def recommend_spots(
    request: RecommendationRequest,
    db: Session = Depends(get_db),
):
    try:
        result = create_recommendations(
            db=db,
            spot_id=request.spotId,
            limit=request.limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RECOMMENDATION_FAILED",
                    "message": str(exc),
                }
            },
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SPOT_NOT_FOUND",
                    "message": "관광지 정보를 찾을 수 없습니다.",
                }
            },
        )

    return result