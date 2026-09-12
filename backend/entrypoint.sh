#!/bin/sh
set -e

echo "[entrypoint] DB 마이그레이션 적용 중 (alembic upgrade head)"
alembic upgrade head

echo "[entrypoint] uvicorn 실행 (port ${PORT:-8080})"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
