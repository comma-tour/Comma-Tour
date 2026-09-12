# syntax=docker/dockerfile:1
#
# 빌드 컨텍스트는 backend/ 가 아니라 프로젝트 루트(Comma-Tour/)입니다.
# 예) docker build -f backend/Dockerfile -t comma-tour-backend .
#
# 이 Dockerfile은 backend/Dockerfile 경로에 두는 것을 전제로 작성했습니다.

FROM python:3.11-slim

# lightgbm 실행 시 필요한 최소 시스템 라이브러리 (libgomp)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# ---------------------------------------------------------------------------
# 1) 의존성 레이어
#    requirements.txt만 먼저 복사해서 pip install을 레이어로 캐싱합니다.
#    코드만 바뀌었을 때는 이 레이어가 재사용되어 재빌드가 빨라집니다.
#
#    torch는 --extra-index-url로 CPU 전용 wheel을 우선 받도록 해서
#    이미지 용량을 줄입니다 (Cloud Run 프리티어는 GPU를 지원하지 않습니다).
# ---------------------------------------------------------------------------
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
       --extra-index-url https://download.pytorch.org/whl/cpu

# ---------------------------------------------------------------------------
# 2) 애플리케이션 코드
# ---------------------------------------------------------------------------
COPY backend/app         ./app
COPY backend/scripts     ./scripts
COPY backend/alembic     ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/entrypoint.sh ./entrypoint.sh

# ---------------------------------------------------------------------------
# 3) ai/ 하위 모듈
#    app/services/ai_recommendation_service.py 가
#    PROJECT_ROOT/ai (= WORKDIR의 형제 경로 /app/ai) 를 sys.path에 추가해서
#    "from matching...", "from ranking..." 형태로 import합니다.
#    그래서 /app/backend가 아니라 /app/ai 에 복사해야 합니다.
# ---------------------------------------------------------------------------
COPY ai/matching /app/ai/matching
COPY ai/ranking  /app/ai/ranking

# ---------------------------------------------------------------------------
# 4) 미리 학습시킨 랭킹 모델
#    [중요] app/services/ai_recommendation_service.py의 run_ai_recommendation()이
#    ranking.recommend를 호출하기 직전에 os.chdir(AI_DIR)로 작업 디렉터리를
#    /app/ai 로 바꿨다가 끝나고 되돌립니다. 즉 recommend.py가 쓰는 상대경로
#    "models/ranking_model.joblib"는 backend가 아니라 /app/ai 기준입니다.
#    그래서 로컬 구조(ai/models/ranking_model.joblib)와 동일하게
#    /app/ai/models/ 밑에 넣어줍니다.
#    [필수 사전작업] 빌드 전에 ai/models/ranking_model.joblib 파일이 로컬에 있어야 합니다.
#    없으면 아래 COPY 단계에서 빌드가 실패합니다.
# ---------------------------------------------------------------------------
COPY ai/models/ranking_model.joblib /app/ai/models/ranking_model.joblib

RUN chmod +x entrypoint.sh

# Cloud Run은 PORT 환경변수를 주입합니다. 로컬 테스트용 기본값만 8080으로 지정.
ENV PORT=8080
EXPOSE 8080

# 참고: Cloud Run은 이 HEALTHCHECK 지시어를 직접 사용하지 않고 자체 프로브를 씁니다.
# 로컬 docker run / docker-compose 환경에서 컨테이너 상태 확인용으로만 유효합니다.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8080') + '/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
