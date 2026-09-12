# Comma-Tour (쉼표투어)

<img src="./frontend/public/images/comma-tour-logo.png" width="200" alt="Comma-Tour 로고" />

**2026 관광데이터 활용 공모전 - 오프피크 팀**

### 팀원
**경기대학교 AI컴퓨터공학부 인공지능전공**
- [장수민](https://github.com/1ongevitymin) : ai(추천 모델 개발) + 배포/인프라(Docker, Cloud Run)

**경기대학교 AI컴퓨터공학부 컴퓨터공학전공**
- [김은진](https://github.com/silverjini0) : frontend(Next.js 프론트엔드)

**경기대학교 AI컴퓨터공학부 SW안전보안전공**
- [김하연](https://github.com/machkite) : backend(FastAPI 백엔드 서버)

### 프로젝트 구조

```
Comma-Tour/
├── ai/         # 추천 모델 (임베딩 매칭 + 랭킹)
├── backend/    # FastAPI 백엔드 서버
└── frontend/   # Next.js 프론트엔드
```

### 로컬 실행 방법

세 모듈은 각각 독립적으로 실행합니다. 정상 동작 확인을 위해서는 `backend`를 먼저 켠 뒤 `frontend`를 실행하는 순서를 권장합니다.

**사전 준비물**
- Python 3.x
- Node.js
- 한국관광공사 OpenAPI 서비스 키, 카카오 REST API 키 / JavaScript 키

**1. 저장소 클론**
```bash
git clone https://github.com/comma-tour/Comma-Tour.git
cd Comma-Tour
```

**2. Backend 실행**
```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install --upgrade pip   # Windows : python -m pip install --upgrade pip
pip install -r requirements.txt

# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env

alembic upgrade head
python -m scripts.seed_haeundae   # 해운대구 초기 데이터 시딩, 최초 1회

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
정상 기동하면 http://127.0.0.1:8000/docs 에서 API 문서(Swagger) 확인 가능.

**2-1. Backend 실행 (Docker, 선택)**

Google Cloud Run 배포를 염두에 두고 만든 Dockerfile입니다. 빌드 컨텍스트는 `backend/`가 아니라 프로젝트 루트 기준입니다.

사전 준비물:
- `ai/models/ranking_model.joblib` (로컬에서 `cd ai && python -m ranking.train_final_model`로 미리 학습해둔 결과물)
- `backend/app/assets/fonts/NanumGothic-Regular.ttf`, `NanumGothic-Bold.ttf` (코스 PDF 생성용 한글 폰트)
- `backend/.env` (`.env.example` 참고)

```bash
docker build -f backend/Dockerfile -t comma-tour-backend .
docker run -p 8000:8080 --env-file backend/.env comma-tour-backend
```

컨테이너는 매번 새로 뜰 때마다 빈 DB로 시작하므로, 최초 실행 후 시딩을 한 번 해줘야 합니다 (`docker ps`로 컨테이너 이름 확인 후 실행).

```bash
docker exec -it <컨테이너이름> python -m scripts.seed_haeundae
```

정상 기동하면 로컬 실행과 동일하게 http://127.0.0.1:8000/docs 에서 확인 가능.

**3. Frontend 실행**
```bash
cd frontend
npm install

# Windows
copy .env.local.example .env.local
# macOS/Linux
cp .env.local.example .env.local

npm run dev
```
정상 기동하면 http://localhost:3000 에서 확인 가능.

**4. AI 모듈 실행**
```bash
cd ai
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install --upgrade pip   # Windows : python -m pip install --upgrade pip
pip install -r requirements.txt

# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env

python -m ranking.build_multi_spot_dataset
python -m ranking.train_final_model
python -m ranking.recommend
```

각 모듈별 상세 실행 방법(환경변수 값 채우는 방법, 모델 학습 순서 등)은 아래 문서를 참고하세요.

- [Backend 로컬 실행 방법](./backend/README.md)
- [Frontend 로컬 실행 방법](./frontend/README.md)
- [AI(추천 모델) 로컬 실행 방법](./ai/README.md)