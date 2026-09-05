from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiCache(Base):
    """
    외부 API(TourAPI 3종 + 카카오모빌리티) 응답을 캐싱하기 위한 범용 테이블.

    cache_key 규칙 (호출부에서 구성):
      - "tarlte:{area_cd}:{signgu_cd}:{tourist_spot_name}"   (TarRlteTarService1)
      - "kor_detail:{content_id}"                             (KorService2.detailCommon2)
      - "cnctr:{content_id}:{base_ym}"                        (TatsCnctrRateService)
      - "kakao_route:{origin_spot_id}:{destination_spot_id}"  (카카오모빌리티 길찾기)

    TTL은 호출부가 fetched_at을 보고 판단한다 (이 테이블 자체는 만료 개념을 모른다).
    """

    __tablename__ = "api_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    cache_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    payload_json: Mapped[str] = mapped_column(Text)

    fetched_at: Mapped[datetime] = mapped_column(DateTime)
