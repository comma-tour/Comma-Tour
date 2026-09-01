"""
[조사/미리보기 전용 - 프로덕션 파이프라인에 포함되지 않음]

목적 (확장 계획 ① 본구현 전 규모 파악):
areaBasedList1로 특정 지역에 등록된 중심관광지가 몇 개, 각각 연관후보가 몇 개인지
tAtsNm 기준으로 묶어서 보여준다. KorService2/cnctrRate는 호출하지 않는다 - 그 두 API가
실제 쿼터를 많이 쓰는 부분이라, 본수집(build_multi_spot_dataset류) 전에 규모를 먼저
파악해서 어느 지역을 얼마나 돌릴지 결정하는 데 쓴다.

실행 방법 (ai/ 폴더 안에서):
    python -m matching.preview_area_spots 51 51130
    (인자 없이 실행하면 기존 TARGET_SPOTS에 쓰였던 4개 지역을 전부 미리보기)
"""

from __future__ import annotations

import sys
from collections import defaultdict

from matching.live_api_client import RELATED_SPOT_DATA_MAX_YM, get_related_candidates_by_area

DEFAULT_REGIONS = [
    ("51", "51130", "원주시"),
    ("11", "11110", "종로구"),
    ("26", "26350", "해운대구"),
    ("50", "50130", "서귀포시"),
]


def preview_region(area_cd: str, signgu_cd: str, label: str = "") -> None:
    items = get_related_candidates_by_area(area_cd, signgu_cd, RELATED_SPOT_DATA_MAX_YM)

    by_center: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_center[item.get("tAtsNm", "?")].append(item)

    print(f"\n--- {label}({area_cd}/{signgu_cd}) 요약: 중심관광지 {len(by_center)}곳, 총 연관후보 {len(items)}건 ---")
    for center_name, candidates in sorted(by_center.items(), key=lambda kv: -len(kv[1])):
        print(f"  · {center_name}: 연관후보 {len(candidates)}건")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        preview_region(sys.argv[1], sys.argv[2])
    else:
        for area_cd, signgu_cd, label in DEFAULT_REGIONS:
            preview_region(area_cd, signgu_cd, label)
