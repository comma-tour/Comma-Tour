from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SharedCourse(Base):
    __tablename__ = "shared_courses"

    share_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    spot_ids: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )