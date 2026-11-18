import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Drillhole(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "drillholes"
    __table_args__ = (
        # hole_id is only unique *within* a tenant: two companies may both have "DH-001".
        UniqueConstraint("organization_id", "hole_id"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("total_depth_m > 0", name="total_depth_positive"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    hole_id: Mapped[str] = mapped_column(String(50))
    project: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float]
    longitude: Mapped[float]
    total_depth_m: Mapped[float]
