import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class IngestionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Ingestion(UUIDPkMixin, TimestampMixin, Base):
    """An uploaded dataset and the state of its background processing job."""

    __tablename__ = "ingestions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[IngestionStatus] = mapped_column(
        Enum(
            IngestionStatus,
            name="ingestion_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=IngestionStatus.PENDING,
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    rows_total: Mapped[int | None]
    rows_valid: Mapped[int | None]
    # e.g. [{"line": 3, "field": "from_m", "message": "overlaps previous interval"}]
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
