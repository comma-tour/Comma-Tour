### AI 추천 모듈 실행 방법 (개발/테스트)

**1. 가상환경 생성 및 활성화**
```bash
cd Comma-Tour/ai
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

**2. 의존성 설치** (torch 포함으로 5~10분 소요)
```bash
pip install --upgrade pip   # Windows : python -m pip install --upgrade pip
pip install -r requirements.txt
```

**3. 환경변수 설정**
```bash
# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env
```
`.env` 파일 열고 한국관광공사 OpenAPI 서비스 키 + 카카오모빌리티 REST API 키 입력:
```
KORSERVICE_API_KEY=발급받은_디코딩_키
KAKAO_REST_API_KEY=발급받은_REST_API_키   
# 카카오 개발자 콘솔의 "REST API 키" (JavaScript 키 아님, backend/.env와 동일한 키 사용)
```

**4. 임베딩 모델 동작 확인**
```bash
python -m matching.embedding
```

**5. API 인증 확인** (관광지 1곳으로 실제 API 호출)
```bash
python -m matching.live_api_client
```

**6. 카카오모빌리티 이동시간 조회 확인** (mock 데이터로 API 연결 확인)
```bash
python -m matching.kakao_mobility_client
```

**7. 모델 학습** (데이터 수집(이동시간 포함) → 모델 비교 → 최종 학습)
```bash
python -m ranking.build_multi_spot_dataset
python -m ranking.model_comparison
python -m ranking.train_final_model
```

**8. 추천 함수 테스트**
```bash
python -m ranking.recommend
```

**9. 응답 속도 벤치마크** (선택)
```bash
python -m ranking.benchmark
```