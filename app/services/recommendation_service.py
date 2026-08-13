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

    related_items = get_related_tourist_spots(
        area_cd=spot.area_cd,
        signgu_cd=spot.signgu_cd,
        tourist_spot_name=spot.tourist_spot_name,
        limit=20,
    )

    congested, candidates = build_ai_inputs(
        spot=spot,
        related_items=related_items,
    )

    # 쉼표투어 서비스 정책:
    # 기준 관광지보다 실제 집중률이 낮은 관광지만 추천 후보로 사용한다.
    if spot.cnctr_rate_7d_avg is not None:
        candidates = [
            candidate
            for candidate in candidates
            if candidate.cnctr_rate_7d_avg < spot.cnctr_rate_7d_avg
        ]

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