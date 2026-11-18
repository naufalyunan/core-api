import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class LithologyInterval(UUIDPkMixin, TimestampMixin, Base):
    """One logged depth interval (from_m..to_m) of a drillhole.

    organization_id is denormalized from the drillhole so every tenant-owned table can be
    filtered (and later protected by Postgres Row-Level Security) without a join.
    Overlap between intervals is validated in the ingestion service, not here.
    """

    __tablename__ = "lithology_intervals"
    __table_args__ = (
        CheckConstraint("from_m >= 0", name="from_non_negative"),
        CheckConstraint("to_m > from_m", name="to_after_from"),
        CheckConstraint("rqd_pct IS NULL OR rqd_pct BETWEEN 0 AND 100", name="rqd_range"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    drillhole_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drillholes.id", ondelete="CASCADE"), index=True
    )
    from_m: Mapped[float]
    to_m: Mapped[float]
    lithology: Mapped[str] = mapped_column(String(100))
    rqd_pct: Mapped[float | None]
