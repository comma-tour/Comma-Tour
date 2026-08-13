from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from app.routers import (
    courses_router,
    recommendations_router,
    spots_router,
)



app = FastAPI(
    title="CommaTour API",
    description="쉼표투어 백엔드 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spots_router)
app.include_router(recommendations_router)
app.include_router(courses_router)


@app.get("/")
def root():
    return {
        "service": "CommaTour API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(
    request: Request,
    exc: FastAPIHTTPException,
):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": str(exc.detail),
            }
        },
    )