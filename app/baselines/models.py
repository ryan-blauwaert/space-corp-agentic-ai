"""Publication records; only trusted migration/seed code may write them."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class BaselineRecord(Base):
    __tablename__ = "baselines"
    __table_args__ = (UniqueConstraint("id", "catalog_release_id", name="uq_baselines_id_release"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    catalog_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT"), nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
