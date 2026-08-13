from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.course import (
    CourseRequest,
    CourseResponse,
    ShareCourseRequest,
    ShareCourseResponse,
    SharedCourseResponse,
)

from app.services.course_service import (
    create_course,
    create_shared_course,
    get_shared_course,
)


router = APIRouter(
    prefix="/api/courses",
    tags=["courses"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=CourseResponse,
)
def generate_course(
    request: CourseRequest,
    db: Session = Depends(get_db),
):
    try:
        return create_course(
            db=db,
            spot_ids=request.spotIds,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SPOT_NOT_FOUND",
                    "message": str(exc),
                }
            },
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(exc),
                }
            },
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "COURSE_GENERATION_FAILED",
                    "message": "코스를 생성하지 못했습니다.",
                }
            },
        )


@router.post(
    "/share",
    response_model=ShareCourseResponse,
)
def share_course(
    request: ShareCourseRequest,
    db: Session = Depends(get_db),
):
    try:
        return create_shared_course(
            db=db,
            spot_ids=request.spotIds,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SPOT_NOT_FOUND",
                    "message": str(exc),
                }
            },
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(exc),
                }
            },
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SHARE_CREATION_FAILED",
                    "message": "공유 링크를 생성하지 못했습니다.",
                }
            },
        )


@router.get(
    "/shared/{share_id}",
    response_model=SharedCourseResponse,
)
def read_shared_course(
    share_id: str,
    db: Session = Depends(get_db),
):
    result = get_shared_course(
        db=db,
        share_id=share_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "SHARE_NOT_FOUND",
                    "message": "공유 코스를 찾을 수 없습니다.",
                }
            },
        )

    return result