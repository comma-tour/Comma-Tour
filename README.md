# Comma-Tour (쉼표투어)

<img src="./frontend/public/images/comma-tour-logo.png" width="200" alt="Comma-Tour 로고" />

**2026 관광데이터 활용 공모전 - 오프피크 팀**

### 팀원
**경기대학교 AI컴퓨터공학부 인공지능전공**
- [장수민](https://github.com/1ongevitymin) : 팀대표, ai(추천 모델 개발)
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
