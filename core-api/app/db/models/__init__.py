"""Import every model here so `Base.metadata` is complete for Alembic autogenerate."""

from app.db.models.drillhole import Drillhole
from app.db.models.ingestion import Ingestion, IngestionStatus
from app.db.models.interval import LithologyInterval
from app.db.models.organization import Organization
from app.db.models.user import Role, User

__all__ = [
    "Drillhole",
    "Ingestion",
    "IngestionStatus",
    "LithologyInterval",
    "Organization",
    "Role",
    "User",
]
