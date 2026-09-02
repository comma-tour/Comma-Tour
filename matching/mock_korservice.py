"""
KorService2 목데이터 생성 모듈

1순위 작업: API 키 승인 전이면 임시 목데이터로 파이프라인 골격을 먼저 작성한다.
반환 스키마는 실제 KorService2 응답 필드와 동일하게 맞춰서,
API 키 승인 후 clients/korservice.py 실제 호출로 교체할 때 이후 단계(임베딩 모듈)가 영향받지 않도록 한다.

[중요 정정] 최초 설계 문서(4장 4.4절)는 "detailIntro2 소개문구"를 임베딩 대상으로 명시했으나,
실제 API 매뉴얼(19/21/1번 OT 자료 docx) 대조 결과 detailIntro2는 휴무일/개장시간/주차시설 등
구조화된 운영정보만 반환하고, 자유 서술형 소개문구가 아니다.
실제 소개문구는 detailCommon2 오퍼레이션의 overview 필드에 있다 (은진님 백엔드 배치 수집 대상도 동일하게 확인 필요).

기본정보(addr1, mapx/mapy 등)는 areaBasedList2/detailCommon2, 소개문구는 detailCommon2.overview 기준으로 스키마를 구성.
실제 서비스 명세는 OT 자료의
"한국관광공사_OpenAPI_활용매뉴얼(국문)_v4.4.docx" 를 참고해 필드명/타입을 재확인할 것.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class MockTourSpot:
    """KorService2 기본정보(areaBasedList2/detailCommon2) + 소개문구(detailCommon2.overview) 목데이터 스키마"""

    content_id: str  # contentid
    title: str  # title, 관광지명
    content_type_id: str  # contenttypeid: 12 관광지, 14 문화시설, 15 행사/공연/축제, 25 여행코스, 28 레포츠, 32 숙박, 38 쇼핑, 39 음식점
    area_cd: str  # lDongRegnCd (법정동 시도 코드, KorService2 4.4 기준)
    signgu_cd: str  # lDongSignguCd (법정동 시군구 코드)
    addr: str  # addr1
    mapx: float  # GPS X좌표(경도, WGS84)
    mapy: float  # GPS Y좌표(위도, WGS84)
    overview: str  # detailCommon2.overview - 임베딩 대상 자유 서술형 소개문구
    rlte_ctgry_lcls_nm: str = ""  # TarRlteTarService1 응답 필드 (참고용, KorService2에는 없음)
    rlte_ctgry_mcls_nm: str = ""
    rlte_ctgry_scls_nm: str = ""


_SAMPLE_OVERVIEWS = [
    "고즈넉한 전통 한옥 마을로, 옛 정취를 느끼며 산책하기 좋은 명소입니다.",
    "탁 트인 해안 절경과 일몰 명소로 유명한 관광지입니다.",
    "산책로와 벚꽃길이 아름다운 도심 속 공원입니다.",
    "지역 특산물을 판매하는 전통 시장으로 다양한 먹거리를 즐길 수 있습니다.",
    "고대 유적과 박물관이 함께 있는 역사 문화 공간입니다.",
]


def get_mock_tour_spots(n: int = 20, seed: int = 42) -> list[MockTourSpot]:
    """
    detailCommon2.overview 샘플 데이터를 목데이터로 생성.

    Args:
        n: 생성할 관광지 목데이터 개수
        seed: 재현 가능성을 위한 랜덤 시드

    Returns:
        MockTourSpot 리스트 (실제 KorService2 응답과 동일한 필드 구조)
    """
    rng = random.Random(seed)
    spots: list[MockTourSpot] = []
    for i in range(n):
        spots.append(
            MockTourSpot(
                content_id=f"MOCK{i:04d}",
                title=f"목데이터 관광지 {i}",
                content_type_id=rng.choice(["12", "14", "15", "28", "39"]),
                # [P2] 1차 심사 범위(해운대구)에 맞춰 고정값으로 정리. 이전에는 서울/부산/제주 중
                # 무작위 선택이라 다른 곳에서 해운대구로 통일한 실 데이터/실행 코드와 지역이 어긋났었다.
                area_cd="26",  # 부산광역시
                signgu_cd="350",  # 해운대구 (lDongSignguCd 기준)
                addr=f"부산광역시 해운대구 임시주소 {i}",
                mapx=129.16 + rng.uniform(-0.02, 0.02),
                mapy=35.16 + rng.uniform(-0.02, 0.02),
                overview=rng.choice(_SAMPLE_OVERVIEWS),
            )
        )
    return spots


if __name__ == "__main__":
    for spot in get_mock_tour_spots(5):
        print(spot)
