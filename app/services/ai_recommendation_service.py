from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session

import os
import sys
from pathlib import Path

from app.models.spot import Spot
from app.services.route_service import get_driving_route_cached
from app.services.tourism_api import (
    get_cnctr_rate_7d_avg,
    get_spot_overview,
    search_tourist_spots,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AI_DIR = PROJECT_ROOT / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))


def build_ai_inputs(
    db: Session,
    spot: Spot,
    related_items: list[dict],
):
    from matching.mock_tarrltetar import Candidate, CongestedSpot

    congested = CongestedSpot(
        tats_nm=spot.tourist_spot_name,
        area_cd=spot.area_cd or "",
        signgu_cd=spot.signgu_cd or "",
        content_type_id=spot.content_type_id or "12",
        overview=spot.summary or "",
        mapx=spot.mapx or 0.0,
        mapy=spot.mapy or 0.0,
        cnctr_rate_7d_avg=spot.cnctr_rate_7d_avg or 0.0,
    )

    candidates = []

    for item in related_items:
        name = item.get("rlteTatsNm")

        if not name:
            continue

        cached_spot = db.scalar(
            select(Spot).where(
                Spot.tourist_spot_name == name
            )
        )

        if (
            cached_spot is not None
            and cached_spot.summary
            and cached_spot.mapx is not None
            and cached_spot.mapy is not None
            and cached_spot.cnctr_rate_7d_avg is not None
        ):
            # [6순위] 목적지가 이미 DB에 있는 경우에만 실제 이동시간을 채운다. 아직 DB에 없는
            # (처음 보는) 후보는 spot id가 없어 캐시 키를 만들 수 없으므로, ranking/recommend.py의
            # Haversine 기반 폴백에 맡긴다 - 추천 결과 재조회 이후 DB에 저장되면 다음 요청부터는
            # 이 분기를 타게 된다.
            travel_time_minutes = None
            try:
                driving_route = get_driving_route_cached(
                    db=db,
                    origin_spot_id=spot.id,
                    origin_mapx=congested.mapx,
                    origin_mapy=congested.mapy,
                    destination_spot_id=cached_spot.id,
                    destination_mapx=float(cached_spot.mapx),
                    destination_mapy=float(cached_spot.mapy),
                )
                travel_time_minutes = driving_route["durationMinutes"]
            except Exception:
                pass  # 카카오 API 실패 시 None으로 남기고 AI 모듈의 폴백에 맡긴다

            candidates.append(
                Candidate(
                    rlte_tats_nm=name,
                    rlte_rank=int(item.get("rlteRank") or 0),
                    rlte_ctgry_lcls_nm=item.get(
                        "rlteCtgryLclsNm", ""
                    ),
                    rlte_ctgry_mcls_nm=item.get(
                        "rlteCtgryMclsNm", ""
                    ),
                    rlte_ctgry_scls_nm=item.get(
                        "rlteCtgrySclsNm", ""
                    ),
                    overview=cached_spot.summary,
                    mapx=float(cached_spot.mapx),
                    mapy=float(cached_spot.mapy),
                    cnctr_rate_7d_avg=float(
                        cached_spot.cnctr_rate_7d_avg
                    ),
                    travel_time_minutes=travel_time_minutes,
                )
            )
            continue

        kor_items = search_tourist_spots(
            keyword=name,
            limit=5,
        )

        if not kor_items:
            continue

        candidate_info = kor_items[0]

        mapx = candidate_info.get("mapx")
        mapy = candidate_info.get("mapy")

        if not mapx or not mapy:
            continue

        area_cd = item.get("rlteRegnCd") or spot.area_cd
        signgu_cd = item.get("rlteSignguCd") or spot.signgu_cd

        try:
            cnctr_rate = get_cnctr_rate_7d_avg(
                area_cd=str(area_cd),
                signgu_cd=str(signgu_cd),
                tourist_spot_name=name,
            )
        except Exception:
            cnctr_rate = None

        # AI 팀 코드와 동일하게,
        # 집중률 미제공이면 기준 관광지와 동일한 값으로 중립 처리
        if cnctr_rate is None:
            cnctr_rate = spot.cnctr_rate_7d_avg or 0.0

        try:
            overview = get_spot_overview(
                str(candidate_info["contentid"])
            )
        except Exception:
            overview = ""

        candidates.append(
            Candidate(
                rlte_tats_nm=name,
                rlte_rank=int(item.get("rlteRank") or 0),
                rlte_ctgry_lcls_nm=item.get(
                    "rlteCtgryLclsNm", ""
                ),
                rlte_ctgry_mcls_nm=item.get(
                    "rlteCtgryMclsNm", ""
                ),
                rlte_ctgry_scls_nm=item.get(
                    "rlteCtgrySclsNm", ""
                ),
                overview=overview or "",
                mapx=float(mapx),
                mapy=float(mapy),
                cnctr_rate_7d_avg=float(cnctr_rate),
            )
        )

    return congested, candidates


def run_ai_recommendation(
    congested,
    candidates,
    top_k: int = 5,
) -> dict:
    original_cwd = os.getcwd()

    try:
        os.chdir(AI_DIR)

        from ranking.recommend import recommend

        return recommend(
            congested=congested,
            candidates=candidates,
            top_k=top_k,
        )

    finally:
        os.chdir(original_cwd)