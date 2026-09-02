"""
1차 심사 범위(부산 해운대구) 관광지 벌크 적재 스크립트. (P0-2)

기존에는 관광지명 검색(searchKeyword2) 과정에서 우연히 들어간 15건 정도만 DB에 있어
해운대구로 지역 검색을 해도 결과가 빈약했다. 이 스크립트는 areaBasedList2로 해운대구
관광지 전체를 한 번에 가져와 upsert한다.

[중요 - 지역코드 체계 주의] KorService2(이 스크립트가 쓰는 areaBasedList2/areaCode2)는
TarRlteTarService1/TatsCnctrRateService(ai/ 파이프라인이 쓰는 areaCd="26"/signguCd="26350",
법정동코드 스타일)와 완전히 다른 구버전 지역코드 체계를 쓴다. KorService2 자체
조회 오퍼레이션(areaCode2)으로 직접 확인한 값:
  - 부산광역시: areaCode="6"  (참고: 서울=1, 인천=2, 대전=3, 대구=4, 광주=5, 부산=6, 울산=7 ...)
  - 해운대구: sigunguCode="16" (부산 산하 시군구 중, areaCode2에 areaCode="6"으로 조회해서 확인)
아래 AREA_CODE/SIGUNGU_CODE는 이 KorService2 전용 값이다. ai/ 폴더의 area_cd="26"/
signgu_cd="26350"과 절대 섞어 쓰지 말 것 - 섞으면 이번처럼 totalCount=0으로 조용히 실패한다.

실행: cd Comma-Tour/backend && python -m scripts.seed_haeundae
(개발계정 트래픽 한도 일 1,000건 - contentTypeId를 나눠서 여러 날에 걸쳐 실행 가능하도록
CONTENT_TYPE_IDS 리스트를 순회하는 구조로 작성했다. 한 번에 다 돌리기엔 무리면 리스트를
줄여서 나눠 실행할 것.)
"""

from __future__ import annotations

import time

from app.db.session import SessionLocal
from app.services.spot_service import upsert_spots_from_korservice
from app.services.tourism_api import search_tourist_spots_by_area

AREA_CD = "6"  # 부산광역시 (KorService2 전용 코드 - areaCode2로 직접 확인함)
SIGUNGU_CD = "16"  # 해운대구 (KorService2 전용 코드 - areaCode2(areaCode="6")로 직접 확인함)

# contentTypeId: 12=관광지, 14=문화시설, 15=행사/공연/축제, 28=레포츠, 39=음식점
# 코어 기능(과밀 판별·유사 명소 추천)은 관광지(12) 중심이므로 우선 12만 적재하고,
# 여력 되면 나머지 유형을 순차로 추가한다 (6.2절 콘텐츠 유형 확장 참고).
CONTENT_TYPE_IDS = ["12"]

PAGE_SIZE = 100
REQUEST_INTERVAL_SEC = 0.3  # 트래픽 한도 보호용 최소 호출 간격


def seed_content_type(db, content_type_id: str) -> int:
    page_no = 1
    total_collected = 0

    while True:
        items, total_count = search_tourist_spots_by_area(
            area_cd=AREA_CD,
            signgu_cd=SIGUNGU_CD,
            content_type_id=content_type_id,
            num_of_rows=PAGE_SIZE,
            page_no=page_no,
        )

        if not items:
            break

        upsert_spots_from_korservice(db=db, items=items)
        total_collected += len(items)

        print(
            f"[해운대구/contentTypeId={content_type_id}] "
            f"{page_no}페이지 {len(items)}건 적재 (누적 {total_collected}/{total_count})"
        )

        if total_collected >= total_count:
            break

        page_no += 1
        time.sleep(REQUEST_INTERVAL_SEC)

    return total_collected


def main() -> None:
    db = SessionLocal()
    try:
        grand_total = 0
        for content_type_id in CONTENT_TYPE_IDS:
            grand_total += seed_content_type(db, content_type_id)
        print(f"\n완료: 해운대구 총 {grand_total}건 적재/갱신")
    finally:
        db.close()


if __name__ == "__main__":
    main()
