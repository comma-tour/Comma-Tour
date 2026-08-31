from app.routers.courses import router as courses_router
from app.routers.recommendations import router as recommendations_router
from app.routers.spots import router as spots_router

__all__ = [
    "spots_router",
    "recommendations_router",
    "courses_router",
]