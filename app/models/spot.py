from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Spot(Base):
    __tablename__ = "spots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tourist_spot_name: Mapped[str] = mapped_column(String(255), index=True)
    area_cd: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
        nullable=True,
    )

    signgu_cd: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
        nullable=True,
    )

    content_type_id: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    
    content_id: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=True,
    )

    sido: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    sigungu: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    category_large: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_small: Mapped[str | None] = mapped_column(String(100), nullable=True)

    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    mapx: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapy: Mapped[float | None] = mapped_column(Float, nullable=True)

    cnctr_rate_7d_avg: Mapped[float | None] = mapped_column(Float, nullable=True)

