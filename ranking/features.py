"""
랭킹 모델 feature 정의 및 출처 (4장 4.4-2 pseudo-label 기반 랭킹 모델 학습)

1순위 작업: feature로 쓸 값들의 출처를 실제 OT 자료 API 매뉴얼(19/21/1번 docx)과 대조해 확인했다.
3순위에서 이 feature들의 가중합으로 pseudo-label을 설계하고 학습셋을 구성한다 (아래는 골격).

┌─────────────────────────┬───────────────────────────┬──────────────────────────────────────────────┐
│ feature                 │ 출처 API                    │ 필드명 / 비고                                        │
├─────────────────────────┼───────────────────────────┼──────────────────────────────────────────────┤
│ rlteRank 정규화값          │ TarRlteTarService1        │ rlteRank (연관순위, 1=가장 연관도 높음, 매뉴얼 예제로 확인함)   │
│ 카테고리 3단 일치도          │ TarRlteTarService1        │ rlteCtgryLclsNm / MclsNm / SclsNm (예: 관광지/문화관광/전시시설) │
│ 임베딩 코사인 유사도          │ KorService2 (로컬 계산)      │ [정정] detailCommon2.overview → matching/embedding.py │
│ cnctrRate 격차            │ TatsCnctrRateService      │ [주의] 향후 30일 예측치가 baseYmd별 배열로 옴, 단일값 아님        │
│ 좌표 거리                  │ KorService2               │ mapx, mapy (WGS84 경도/위도, Haversine 등으로 거리 계산)   │
└─────────────────────────┴───────────────────────────┴──────────────────────────────────────────────┘

[1순위 검증 결과 - 정정 사항]
    1. 임베딩 대상 필드 정정: 최초 설계는 "KorService2 detailIntro2 소개문구"였으나,
       실제 매뉴얼 확인 결과 detailIntro2는 휴무일/개장시간/주차시설 등 구조화된 운영정보만 반환하며
       자유 서술형 소개문구가 아니었다. 실제 소개문구는 detailCommon2 오퍼레이션의 overview 필드다.
       → 은진님 백엔드 배치 수집 대상(어떤 오퍼레이션을 호출하는지)도 이 기준으로 함께 확인 필요.
    2. cnctrRate 시점 확정: TatsCnctrRateService 응답은 관광지 1곳당 baseYmd(일자)별로
       향후 30일 예측 cnctrRate가 배열로 온다. "과밀지 대비 대체지 집중률 격차"는
       **조회시점부터 향후 7일 평균**을 사용하기로 확정 (오늘 1일치는 이상치에 취약, 30일 평균은 최신성이
       서비스 목적과 어긋남 → 7일 평균이 균형점). 은진님 배치 계층에서 7일치 평균을 미리 계산해 저장 권장.
    3. rlteRank 방향 확인: 매뉴얼 응답 예제에서 rlteRank=1이 최상위 연관 후보로 나열됨.
       "낮을수록 연관도 높음"이 맞으므로 정규화 시 역수 또는 (max_rank - rank) 방식으로 방향 반전 필요.

갱신주기 주의 (4장 4.2절, 매뉴얼 재확인 완료):
    - cnctrRate: 일 1회 갱신 (TatsCnctrRateService 매뉴얼 표에서 확인)
    - rlteRank(TarRlteTarService1): 월 1회(매월 8일) 갱신 (매뉴얼 표에서 확인, baseYm=YYYYMM 단위 요청)
    실시간 호출이 아닌 배치 적재된 DB 값을 사용하는 것을 전제로 함.

[3순위 - 카테고리 일치도 계산 방식에 대한 스코프 결정]
TarRlteTarService1은 후보(candidate)의 3단 카테고리(rlteCtgryLclsNm/MclsNm/SclsNm)는 주지만,
과밀 관광지(congested) 자신의 3단 카테고리는 제공하지 않는다 (KorService2의 contentTypeId만 알 수 있음).
따라서 이번 3순위에서는 "대분류 일치 여부"만 계산한다 (contentTypeId → 대분류명 매핑 후 후보의 rlteCtgryLclsNm과 비교).
중분류/소분류 일치도는 과밀 관광지 자신의 세부 카테고리 정보를 확보하기 전까지는 계산하지 않는다 (보류, 향후 KorService2 분류체계 코드 활용 검토).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

FEATURE_SOURCES = {
    "rlte_rank_norm": "TarRlteTarService1.rlteRank (1=최상위 연관도, 정규화 시 방향 반전 필요)",
    "category_match": "TarRlteTarService1.rlteCtgryLclsNm/MclsNm/SclsNm (3단 일치 개수 또는 가중 일치도)",
    "embedding_similarity": "matching/embedding.py 코사인 유사도 (KorService2 detailCommon2.overview 기반, detailIntro2 아님)",
    "cnctr_rate_gap": "TatsCnctrRateService.cnctrRate (조회시점부터 향후 7일 평균, 과밀지-대체지 격차. 확정 사유는 상단 docstring 참고)",
    "coord_distance": "KorService2.mapx/mapy (WGS84, Haversine 거리)",
}

# 3순위: pseudo-label 가중합 초안 (상식적 기준, 팀 정성 검토로 조정 예정)
# 주의: 아래 가중치는 "정규화된(0~1) feature"에 곱해지는 값이다. rlte_rank_norm/category_match/embedding_similarity는
# 원래도 대략 0~1 범위지만, cnctr_rate_gap과 coord_distance는 원시값 단위(퍼센트포인트, km)가 서로 달라
# compute_pseudo_label() 내부에서 먼저 0~1 범위로 정규화한 뒤에 이 가중치를 곱한다 (그대로 곱하면 값의 스케일이 다른
# feature가 결과를 압도하는 문제가 있었음 - 3순위 검토 중 발견해 정규화 단계를 추가함).
PSEUDO_LABEL_WEIGHTS = {
    "rlte_rank_norm": 0.3,
    "category_match": 0.2,
    "embedding_similarity": 0.3,
    "cnctr_rate_gap": 0.15,
    "coord_distance": -0.05,  # 거리가 멀수록 감점 (정규화된 proximity가 아닌 원시 거리 방향에 맞춰 음수 가중치 유지)
}

# 카테고리 일치도 계산용: KorService2 contentTypeId → TarRlteTarService1 rlteCtgryLclsNm 대분류명 매핑
# (매뉴얼 예제에서 관찰된 rlteCtgryLclsNm 값: "관광지", "음식", "쇼핑", "숙박" 등. 정확한 전체 목록은 실 데이터로 재확인 필요)
CONTENT_TYPE_ID_TO_CTGRY_LCLS_NM = {
    "12": "관광지",
    "14": "관광지",  # 문화시설도 TarRlteTarService1 응답에서는 "관광지" 대분류로 묶여 나타남 (매뉴얼 예제 기준)
    "15": "관광지",
    "25": "관광지",
    "28": "관광지",
    "32": "숙박",
    "38": "쇼핑",
    "39": "음식",
}


@dataclass
class CandidateFeatures:
    """관광지-후보 쌍 하나의 feature 벡터"""

    rlte_rank_norm: float  # 0~1, 1에 가까울수록 연관순위 상위
    category_match: float  # 0 또는 1 (대분류 일치 여부, 3순위 스코프: 대분류만)
    embedding_similarity: float  # -1~1 (보통 0~1), matching/similarity_matching.py 결과 재사용
    cnctr_rate_gap: float  # 원시값(퍼센트포인트), 과밀지 - 대체지 7일평균 cnctrRate (양수일수록 대체지가 덜 붐빔)
    coord_distance: float  # 원시값(km), Haversine 거리


def normalize_rlte_rank(rank: int, max_rank: int = 15) -> float:
    """
    rlteRank(1=최상위)를 0~1로 정규화한다. rank=1 -> 1.0, rank=max_rank -> 0.0.
    max_rank 기본값 15는 2순위에서 확정한 "카테고리별 상위 15개" 후보 수집 방침과 맞춘 것.
    rank가 max_rank를 넘는 경우 0으로 clip.
    """
    if rank <= 1:
        return 1.0
    if rank >= max_rank:
        return 0.0
    return 1.0 - (rank - 1) / (max_rank - 1)


def category_match_score(congested_content_type_id: str, candidate_rlte_ctgry_lcls_nm: str) -> float:
    """
    과밀 관광지의 contentTypeId를 대분류명으로 매핑해, 후보의 rlteCtgryLclsNm과 일치하는지 확인한다.
    3순위 스코프: 대분류 일치 여부만 (중/소분류는 과밀 관광지 쪽 세부 카테고리 정보가 없어 보류).
    """
    congested_lcls_nm = CONTENT_TYPE_ID_TO_CTGRY_LCLS_NM.get(congested_content_type_id)
    if congested_lcls_nm is None:
        return 0.0  # 매핑에 없는 contentTypeId는 불일치로 처리
    return 1.0 if congested_lcls_nm == candidate_rlte_ctgry_lcls_nm else 0.0


def coord_distance_km(mapx1: float, mapy1: float, mapx2: float, mapy2: float) -> float:
    """
    두 지점(WGS84 경도 mapx, 위도 mapy) 간 Haversine 거리를 km 단위로 계산한다.
    """
    lon1, lat1, lon2, lat2 = map(radians, [mapx1, mapy1, mapx2, mapy2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    earth_radius_km = 6371.0
    return 2 * earth_radius_km * asin(sqrt(a))


def cnctr_rate_gap(congested_cnctr_rate_7d_avg: float, candidate_cnctr_rate_7d_avg: float) -> float:
    """
    cnctrRate 격차 = 과밀지 7일 평균 - 대체지 7일 평균 (양수일수록 대체지가 덜 붐빔 = 좋은 추천).
    시점을 7일 평균으로 정한 이유는 상단 docstring 참고.
    """
    return congested_cnctr_rate_7d_avg - candidate_cnctr_rate_7d_avg


def compute_pseudo_label(features: CandidateFeatures) -> float:
    """
    feature 가중합으로 pseudo-label(임시 정답 점수)을 계산한다.
    가중치는 PSEUDO_LABEL_WEIGHTS를 상식적 기준 초안으로 시작, 팀 정성 검토 후 조정.

    정규화 방식:
        - rlte_rank_norm, category_match: 이미 0~1이므로 그대로 사용
        - embedding_similarity: 코사인 유사도라 이미 대략 0~1 범위 (음수 나올 수 있으나 실측상 드묾), 그대로 사용
        - cnctr_rate_gap: 퍼센트포인트(-100~100) 단위를 100으로 나눠 대략 -1~1로 정규화
        - coord_distance: km 단위 원시값을 그대로 쓰면 값이 커서(수십 km) 결과를 압도하므로,
          proximity = 1 / (1 + distance_km) 형태로 0~1 범위 근접도 점수로 변환 후 사용
          (거리가 0km면 1.0, 거리가 멀어질수록 0에 가까워짐 - PSEUDO_LABEL_WEIGHTS의 음수 가중치와 결합하면
          "가까울수록 가점"이 되도록 부호를 맞춰야 하므로, 가중치는 양수로 보고 proximity에 곱한다)
    """
    normalized_cnctr_rate_gap = features.cnctr_rate_gap / 100.0
    coord_proximity = 1.0 / (1.0 + features.coord_distance)  # 0~1, 가까울수록 1에 근접

    score = (
        PSEUDO_LABEL_WEIGHTS["rlte_rank_norm"] * features.rlte_rank_norm
        + PSEUDO_LABEL_WEIGHTS["category_match"] * features.category_match
        + PSEUDO_LABEL_WEIGHTS["embedding_similarity"] * features.embedding_similarity
        + PSEUDO_LABEL_WEIGHTS["cnctr_rate_gap"] * normalized_cnctr_rate_gap
        + abs(PSEUDO_LABEL_WEIGHTS["coord_distance"]) * coord_proximity  # proximity로 변환했으므로 양수로 적용
    )
    return score
