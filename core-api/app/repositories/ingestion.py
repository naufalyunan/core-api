import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion import Ingestion


class IngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, organization_id: uuid.UUID, ingestion_id: uuid.UUID) -> Ingestion | None:
        """Tenant-scoped lookup, for API requests."""
        return await self.session.scalar(
            select(Ingestion).where(
                Ingestion.id == ingestion_id,
                Ingestion.organization_id == organization_id,
            )
        )

    async def get_for_job(self, ingestion_id: uuid.UUID) -> Ingestion | None:
        """Unscoped lookup, for the background job only.

        The job receives an id the API created a moment earlier for the right tenant, and
        then works with ingestion.organization_id. Never call this from a route.
        """
        return await self.session.get(Ingestion, ingestion_id)

    def add(self, ingestion: Ingestion) -> None:
        self.session.add(ingestion)
