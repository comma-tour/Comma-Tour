### 임베딩 모델 비교

**1. 실행 명령어**
```bash
python -m matching.embedding
```
과밀 관광지-후보 관광지 소개문구(overview)의 "실제로 유사한 쌍" vs "실제로 안 유사한 쌍" 코사인 유사도 평균을 비교한다.
기준: **gap = 유사쌍 평균 - 비유사쌍 평균** (클수록 두 그룹을 잘 구분함)

**2. 비교 결과** (gap 내림차순)

| 모델 | 차원 | 로딩(s) | 임베딩(s) | 유사쌍 평균 | 비유사쌍 평균 | gap |
|---|---|---|---|---|---|---|
| jhgan/ko-sroberta-multitask | 768 | 19.51 | 9.904 | 0.7759 | 0.2745 | **0.5014** |
| BM-K/KoSimCSE-roberta | 768 | 3.95 | 10.094 | 0.7865 | 0.3227 | **0.4638** |
| intfloat/multilingual-e5-base | 768 | 7.14 | 7.831 | 0.9024 | 0.8427 | **0.0597** |

**3. 최종 선정: `jhgan/ko-sroberta-multitask`**

- gap 최고(0.5014) - 추천 랭킹에 필요한 건 절대 유사도가 아니라 유사/비유사 **구분 능력**
- `multilingual-e5-base`: 속도는 최상이지만 gap 0.0597 (다 비슷하다고 답함) - 한국어 관광지 도메인 변별력 부족, 제외
- `KoSimCSE-roberta`: gap 근소 열세, 임베딩 단계도 근소하게 더 느림 - 정확도 우선으로 제외
- 로딩 19.51s는 서버 기동 시 1회성 비용 (요청마다 재로딩 아님) - gap 우위가 더 중요하다고 판단

**4. 적용 위치**
```python
# matching/embedding.py
DEFAULT_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jhgan/ko-sroberta-multitask")
```
