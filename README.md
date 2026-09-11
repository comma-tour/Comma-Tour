V### 프론트엔드 실행 방법 (개발/테스트)

**1. 의존성 설치**
```bash
cd Comma-Tour/frontend
npm install
```

**2. 환경변수 설정**
```bash
# Windows
copy .env.local.example .env.local
# macOS/Linux
cp .env.local.example .env.local
```
`.env.local` 파일 열고 아래 값 채우기:
```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000   # 로컬은 백엔드 로컬 주소, 배포는 Railway/Render 도메인
NEXT_PUBLIC_KAKAO_MAP_KEY=발급받은_JavaScript_키   # 카카오 개발자 콘솔의 "JavaScript 키" (REST API 키 아님)
```
카카오 개발자 콘솔 > 플랫폼 > Web에 아래 도메인을 등록해야 지도가 정상적으로 뜬다:
```
http://localhost:3000
(배포 도메인, 예: https://comma-tour.vercel.app)
```

**3. 개발 서버 실행**
```bash
npm run dev
```
정상 기동하면 http://localhost:3000 에서 확인 가능. 백엔드(`uvicorn app.main:app`)가 먼저 켜져 있어야 API 호출이 정상 동작함.

**4. 빌드 확인** (배포 전 로컬 검증)
```bash
npm run build
npm run start
```
