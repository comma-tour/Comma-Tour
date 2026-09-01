from sqlalchemy.orm import Session

from app.models.spot import Spot
from app.services.ai_recommendation_service import (
    build_ai_inputs,
    run_ai_recommendation,
)
from app.services.spot_service import (
    get_congestion_level,
    upsert_spots_from_korservice,
)
from app.services.tourism_api import (
    get_related_tourist_spots,
    search_tourist_spots,
)


def _has_final_consonant(text: str) -> bool:
    if not text:
        return False

    char = text[-1]

    if not ("가" <= char <= "힣"):
        return False

    return (ord(char) - ord("가")) % 28 != 0


def _with_gwa_wa(text: str) -> str:
    particle = "과" if _has_final_consonant(text) else "와"
    return f"{text}{particle}"


def build_recommendation_reason(
    base_spot_name: str,
    category_medium: str | None,
    congestion_reduction_rate: float | None,
) -> str:
    category_text = (
        f"{category_medium} 유형"
        if category_medium
        else "유사한 관광 유형"
    )

    if congestion_reduction_rate is not None:
        return (
            f"{_with_gwa_wa(base_spot_name)} 유사한 {category_text}이며, "
            f"향후 7일 평균 관광 집중률이 약 "
            f"{congestion_reduction_rate:.1f}% 낮아 "
            "상대적으로 여유로운 대안 관광지입니다."
        )

    return (
        f"{_with_gwa_wa(base_spot_name)} 유사한 {category_text}로, "
        "AI 추천 결과를 기반으로 선정된 대안 관광지입니다."
    )


def create_recommendations(
    db: Session,
    spot_id: int,
    limit: int = 5,
) -> dict | None:
    spot = db.get(Spot, spot_id)

    if spot is None:
        return None

    if not spot.area_cd or not spot.signgu_cd:
        raise ValueError(
            "기준 관광지의 지역 코드가 없습니다."
        )

    print(
        f"[진단] spot={spot.tourist_spot_name!r} "
        f"area_cd={spot.area_cd!r} signgu_cd={spot.signgu_cd!r} "
        f"cnctr_rate_7d_avg={spot.cnctr_rate_7d_avg!r}"
    )

    related_items = get_related_tourist_spots(
        area_cd=spot.area_cd,
        signgu_cd=spot.signgu_cd,
        tourist_spot_name=spot.tourist_spot_name,
        # TarRlteTarService1은 관광지 하나당 최대 50건까지 제공한다(2026-09 조사로 확인).
        # KorService2 매칭 실패로 상당수가 걸러지기 때문에, 처음부터 50건을 받아와야
        # 필터 이후 남는 후보 수가 줄어들지 않는다.
        limit=50,
    )
    print(f"[진단] get_related_tourist_spots 원본 반환 건수: {len(related_items)}")

    congested, candidates = build_ai_inputs(
        db=db,
        spot=spot,
        related_items=related_items,
    )
    print(f"[진단] build_ai_inputs 이후 candidates 건수(필터 전): {len(candidates)}")

    # 쉼표투어 서비스 정책:
    # 기준 관광지보다 실제 집중률이 낮거나 같은 관광지만 추천 후보로 사용한다.
    # [주의] cnctrRate 미제공 후보는 build_ai_inputs()에서 기준 관광지와 "동일한 값"으로
    # 중립 처리된다(AI 팀 코드와 동일한 정책). 여기서 엄격한 '<'를 쓰면 그렇게 중립 처리된
    # 후보들이 전부 걸러져서, 기준 관광지 집중률이 높을 때 추천 결과가 통째로 0건이 되는
    # 문제가 있었다. '<='로 완화해 중립 처리된 후보는 통과시키고, 실제로 더 붐비는
    # (진짜 더 높은 cnctrRate를 가진) 후보만 제외한다.
    if spot.cnctr_rate_7d_avg is not None:
        candidates = [
            candidate
            for candidate in candidates
            if candidate.cnctr_rate_7d_avg <= spot.cnctr_rate_7d_avg
        ]
    print(f"[진단] 집중률 필터 이후 candidates 건수: {len(candidates)}")

    if not candidates:
        return {
            "congestedSpot": {
                "spotId": spot.id,
                "tAtsNm": spot.tourist_spot_name,
                "cnctrRate7dAvg": spot.cnctr_rate_7d_avg,
                "congestionLevel": get_congestion_level(
                    spot.cnctr_rate_7d_avg
                ),
            },
            "recommendations": [],
        }

    ai_result = run_ai_recommendation(
        congested=congested,
        candidates=candidates,
        top_k=limit,
    )

    recommendations = []

    candidate_by_name = {
        candidate.rlte_tats_nm: candidate
        for candidate in candidates
    }

    for item in ai_result["recommendations"]:
        name = item["rlteTatsNm"]

        candidate = candidate_by_name.get(name)
        if candidate is None:
            continue

        # 추천 관광지를 KorService에서 다시 조회해서
        # 백엔드 spots DB에도 저장한다.
        kor_items = search_tourist_spots(
            keyword=name,
            limit=5,
        )

        if not kor_items:
            continue

        # 우선 exact title match를 사용하고,
        # 없으면 첫 번째 결과를 fallback으로 사용
        matched = next(
            (
                kor_item
                for kor_item in kor_items
                if kor_item.get("title") == name
            ),
            kor_items[0],
        )

        stored = upsert_spots_from_korservice(
            db=db,
            items=[matched],
        )[0]

        stored.category_large = item.get("rlteCtgryLclsNm")
        stored.category_medium = item.get("rlteCtgryMclsNm")
        stored.category_small = item.get("rlteCtgrySclsNm")

        db.commit()
        db.refresh(stored)

        
        base_rate = spot.cnctr_rate_7d_avg
        candidate_rate = candidate.cnctr_rate_7d_avg

        congestion_difference = None
        congestion_reduction_rate = None

        if base_rate is not None:
            congestion_difference = round(
                base_rate - candidate_rate,
                2,
            )

            if base_rate != 0:
                congestion_reduction_rate = round(
                    (
                        (base_rate - candidate_rate)
                        / base_rate
                    )
                    * 100,
                    2,
                )

        recommendation_reason = build_recommendation_reason(
            base_spot_name=spot.tourist_spot_name,
            category_medium=item.get("rlteCtgryMclsNm"),
            congestion_reduction_rate=congestion_reduction_rate,
        )

        recommendations.append(
            {
                "spotId": stored.id,
                "rlteTatsNm": name,
                "rlteRank": item["rlteRank"],
                "rlteCtgryLclsNm": item.get(
                    "rlteCtgryLclsNm"
                ),
                "rlteCtgryMclsNm": item.get(
                    "rlteCtgryMclsNm"
                ),
                "rlteCtgrySclsNm": item.get(
                    "rlteCtgrySclsNm"
                ),
                "cnctrRate7dAvg": candidate_rate,
                "congestionLevel": get_congestion_level(
                    candidate_rate
                ),
                "congestionDifference": (
                    congestion_difference
                ),
                "congestionReductionRate": (
                    congestion_reduction_rate
                ),
                "mapx": candidate.mapx,
                "mapy": candidate.mapy,
                "score": item["score"],
                "recommendationReason": recommendation_reason,
                "address": stored.address,
                "imageUrl": stored.image_url,
                "summary": candidate.overview,
            }
        )

    return {
        "congestedSpot": {
            "spotId": spot.id,
            "tAtsNm": spot.tourist_spot_name,
            "cnctrRate7dAvg": spot.cnctr_rate_7d_avg,
            "congestionLevel": get_congestion_level(
                spot.cnctr_rate_7d_avg
            ),
        },
        "recommendations": recommendations,
    }