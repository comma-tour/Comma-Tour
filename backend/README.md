### 백엔드 실행 방법 (개발/테스트)

**1. 가상환경 생성 및 활성화**
```bash
cd Comma-Tour/backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

**2. 의존성 설치** (torch 포함으로 5~10분 소요, AI 추천 모듈 연동 때문)
```bash
pip install --upgrade pip   # Windows : python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium  # PDF 지도 스크린샷용 헤드리스 브라우저 (최초 1회, 수백MB 다운로드)
```

**3. 환경변수 설정**
```bash
# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env
```
`.env` 파일 열고 아래 값 채우기:
```
DATABASE_URL=sqlite:///./commatour.db   # 로컬은 sqlite, 배포는 Postgres 등으로 교체
KORSERVICE_API_KEY=발급받은_디코딩_키       # ai/.env와 동일한 키 사용
KAKAO_REST_API_KEY=발급받은_REST_API_키    # 카카오 개발자 콘솔의 "REST API 키" (JavaScript 키 아님)
KAKAO_JS_API_KEY=발급받은_JavaScript_키    # frontend .env.local의 NEXT_PUBLIC_KAKAO_MAP_KEY와 동일한 값
FRONTEND_BASE_URL=http://localhost:3000
```

**4. DB 마이그레이션**
```bash
alembic upgrade head
```
스키마를 바꿨다면(모델 파일 수정) 아래로 새 마이그레이션 생성 후 위 명령 재실행:
```bash
alembic revision --autogenerate -m "설명"
```

**5. 해운대구 초기 데이터 시딩** (최초 1회)
```bash
python -m scripts.seed_haeundae
```

**6. 서버 실행**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
정상 기동하면 http://127.0.0.1:8000/docs 에서 API 문서(Swagger) 확인 가능.


