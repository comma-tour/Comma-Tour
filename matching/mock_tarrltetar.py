"""
TarRlteTarService1(연관관광지) + KorService2(overview) + TatsCnctrRateService(cnctrRate) 결합 목데이터

2순위 목표: 임베딩 유사도 모듈을 은진님 백엔드 모듈과 별개로 독립 실행 가능한 형태로 완성한다.
3순위 목표: feature 계산(카테고리 일치도, 좌표 거리, cnctrRate 격차)에 필요한 필드를 추가로 보강한다.
실제로는 아래 API 호출들을 은진님의 배치 수집 계층이 각각 수행하고 DB에서 조인해 내려주지만,
현재는 API 키가 없어 실제 호출이 불가능하므로, "이미 조인된 형태"의 목데이터를 여기서 직접 구성한다.

- TarRlteTarService1.areaBasedList1: 과밀 관광지 1곳에 대한 연관관광지 후보 목록 (rlteTatsNm, rlteRank, rlteCtgryLclsNm/MclsNm/SclsNm)
- KorService2.areaBasedList2/detailCommon2: 각 후보(및 과밀 관광지 자신)의 overview, contentTypeId, mapx/mapy
- TatsCnctrRateService.tatsCnctrRatedList: 각 후보(및 과밀 관광지 자신)의 향후 7일 평균 cnctrRate (시점 선정 근거는 ranking/features.py 참고)

실제 연동 시에는 이 모듈의 get_mock_congested_spot_with_candidates()를
"DB에서 과밀 관광지 1곳 + 연관관광지 후보 목록 + 각각의 overview/cnctrRate/좌표를 조인해 가져오는 함수"로 교체하면 되고,
반환 스키마(CongestedSpot, Candidate)는 그대로 유지해 matching/similarity_matching.py, ranking/ 모듈이 영향받지 않도록 한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CongestedSpot:
    """사용자가 조회한 과밀 관광지 (기준점)"""

    tats_nm: str  # 관광지명
    area_cd: str
    signgu_cd: str
    content_type_id: str  # KorService2 contentTypeId (12 관광지, 14 문화시설, 32 숙박, 38 쇼핑, 39 음식점 등) - 카테고리 일치도 계산용
    overview: str  # KorService2 detailCommon2.overview
    mapx: float  # GPS X좌표(경도, WGS84)
    mapy: float  # GPS Y좌표(위도, WGS84)
    cnctr_rate_7d_avg: float  # TatsCnctrRateService 향후 7일 평균 cnctrRate


@dataclass
class Candidate:
    """TarRlteTarService1 연관관광지 후보 (KorService2 overview/좌표, TatsCnctrRateService cnctrRate 결합됨)"""

    rlte_tats_nm: str  # 연관관광지명
    rlte_rank: int  # 연관순위 (1=최상위 연관도, 카테고리별로 리셋됨 - 2순위 검증 결과)
    rlte_ctgry_lcls_nm: str  # 연관카테고리대분류명
    rlte_ctgry_mcls_nm: str  # 연관카테고리중분류명
    rlte_ctgry_scls_nm: str  # 연관카테고리소분류명
    overview: str  # KorService2 detailCommon2.overview (연관관광지 자신의 소개문구)
    mapx: float  # GPS X좌표(경도, WGS84)
    mapy: float  # GPS Y좌표(위도, WGS84)
    cnctr_rate_7d_avg: float  # TatsCnctrRateService 향후 7일 평균 cnctrRate
    is_region_ambiguous: bool = False  # KorService2 검색 결과가 여러 건이라 지역 매칭이 불확실했는지 (live_api_client.py 참고)


def get_mock_congested_spot_with_candidates() -> tuple[CongestedSpot, list[Candidate]]:
    """
    과밀 관광지 1곳(해안 절경 관광지 가정, contentTypeId=12 관광지)과, 연관관광지 후보 8개를 반환한다.
    후보는 의도적으로 "실제로 유사한 것 3개 + 카테고리는 비슷하지만 내용은 다른 것 2개 +
    전혀 다른 것 3개"로 구성해, 임베딩 유사도가 rlteRank와 다른 신호를 준다는 걸 보여줄 수 있게 했다.

    cnctrRate는 해안 절경 계열(과밀지와 실제로 유사한 후보)일수록 함께 붐빌 가능성을 고려해 다소 높게,
    카테고리가 다른 후보(음식/쇼핑/숙박)일수록 낮게 설정해 "카테고리 일치 = 항상 좋은 추천"이 아니라는
    직관(비슷한 곳은 오히려 같이 붐빌 수 있다)을 pseudo-label 계산에서 확인할 수 있게 했다.
    [P2] 1차 심사 범위(해운대구)에 맞춰, 좌표는 부산 해운대구 인근 실제 좌표(해운대해수욕장 기준)로
    평행이동했다. 관광지명/소개문구 자체는 여전히 가상의 예시이며 실제 해운대구 관광지가 아니다 -
    이 모듈은 similarity_matching.py 오프라인 단위 테스트용 목데이터일 뿐, 프로덕션 데이터 소스가 아니다.
    """
    congested = CongestedSpot(
        tats_nm="간현관광지",
        area_cd="26",
        signgu_cd="26350",
        content_type_id="12",  # 관광지
        overview="탁 트인 해안선과 붉게 물드는 노을이 장관을 이루는 해변으로, 사진 명소로도 유명합니다.",
        mapx=129.1600,
        mapy=35.1587,
        cnctr_rate_7d_avg=82.3,  # 과밀 상태 가정
    )

    candidates = [
        # 실제로 내용이 유사한 후보 (해안/일몰 계열) - 임베딩 유사도가 높게 나와야 함, cnctrRate도 다소 높게(같이 붐빌 가능성)
        Candidate(
            rlte_tats_nm="일몰전망대",
            rlte_rank=3,
            rlte_ctgry_lcls_nm="관광지",
            rlte_ctgry_mcls_nm="자연관광",
            rlte_ctgry_scls_nm="해안절경",
            overview="일몰 무렵 바다와 하늘이 온통 주황빛으로 물드는 풍경을 감상할 수 있는 해안 산책로입니다.",
            mapx=129.1729,
            mapy=35.1475,
            cnctr_rate_7d_avg=58.1,
        ),
        Candidate(
            rlte_tats_nm="갯바위쉼터",
            rlte_rank=5,
            rlte_ctgry_lcls_nm="관광지",
            rlte_ctgry_mcls_nm="자연관광",
            rlte_ctgry_scls_nm="해안절경",
            overview="파도가 부서지는 갯바위와 넓게 펼쳐진 수평선을 조망할 수 있는 해변 쉼터입니다.",
            mapx=129.1444,
            mapy=35.1705,
            cnctr_rate_7d_avg=45.6,
        ),
        Candidate(
            rlte_tats_nm="등대전망길",
            rlte_rank=8,
            rlte_ctgry_lcls_nm="관광지",
            rlte_ctgry_mcls_nm="자연관광",
            rlte_ctgry_scls_nm="해안절경",
            overview="붉은 등대와 어우러진 해안선을 따라 걷는 산책길로, 노을 사진 명소로 알려져 있습니다.",
            mapx=129.1869,
            mapy=35.1825,
            cnctr_rate_7d_avg=39.2,
        ),
        # rlteRank는 상위지만 내용은 다소 다른 후보 (같은 대분류 '관광지'지만 자연관광 아님)
        Candidate(
            rlte_tats_nm="전통한옥마을",
            rlte_rank=1,
            rlte_ctgry_lcls_nm="관광지",
            rlte_ctgry_mcls_nm="문화관광",
            rlte_ctgry_scls_nm="전통마을",
            overview="기와지붕이 늘어선 골목을 따라 옛 정취를 느끼며 걸을 수 있는 전통 한옥 마을입니다.",
            mapx=129.1319,
            mapy=35.1375,
            cnctr_rate_7d_avg=28.4,
        ),
        Candidate(
            rlte_tats_nm="향토박물관",
            rlte_rank=2,
            rlte_ctgry_lcls_nm="관광지",
            rlte_ctgry_mcls_nm="문화관광",
            rlte_ctgry_scls_nm="전시시설",
            overview="선사시대부터 이어진 유물을 전시한 역사 박물관으로, 지역의 문화사를 한눈에 살펴볼 수 있습니다.",
            mapx=129.1169,
            mapy=35.1925,
            cnctr_rate_7d_avg=22.7,
        ),
        # 전혀 다른 후보 (음식/쇼핑/숙박 계열)
        Candidate(
            rlte_tats_nm="동원집",
            rlte_rank=4,
            rlte_ctgry_lcls_nm="음식",
            rlte_ctgry_mcls_nm="음식",
            rlte_ctgry_scls_nm="한식",
            overview="지역 향토 음식을 대표하는 손맛 깃든 메뉴로 유명한 오래된 식당입니다.",
            mapx=129.1619,
            mapy=35.1525,
            cnctr_rate_7d_avg=15.9,
        ),
        Candidate(
            rlte_tats_nm="중문향토오일시장",
            rlte_rank=6,
            rlte_ctgry_lcls_nm="쇼핑",
            rlte_ctgry_mcls_nm="쇼핑",
            rlte_ctgry_scls_nm="전통시장",
            overview="다양한 지역 특산물과 길거리 음식을 즐길 수 있는 활기 넘치는 전통 시장입니다.",
            mapx=129.2019,
            mapy=35.1225,
            cnctr_rate_7d_avg=33.5,
        ),
        Candidate(
            rlte_tats_nm="오션뷰리조트",
            rlte_rank=7,
            rlte_ctgry_lcls_nm="숙박",
            rlte_ctgry_mcls_nm="숙박",
            rlte_ctgry_scls_nm="리조트",
            overview="바다 전망을 갖춘 객실과 다양한 부대시설을 갖춘 휴양형 리조트입니다.",
            mapx=129.2119,
            mapy=35.2025,
            cnctr_rate_7d_avg=19.8,
        ),
    ]

    return congested, candidates


if __name__ == "__main__":
    congested, candidates = get_mock_congested_spot_with_candidates()
    print(f"과밀 관광지: {congested.tats_nm} (cnctrRate 7일평균={congested.cnctr_rate_7d_avg})")
    print(f"연관관광지 후보 {len(candidates)}개")
    for c in candidates:
        print(f"  - {c.rlte_tats_nm} (rlteRank={c.rlte_rank}, {c.rlte_ctgry_mcls_nm}, cnctrRate={c.cnctr_rate_7d_avg})")
