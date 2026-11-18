import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.interval import LithologyInterval


class IntervalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_organization(
        self, organization_id: uuid.UUID
    ) -> Sequence[LithologyInterval]:
        rows = await self.session.scalars(
            select(LithologyInterval).where(LithologyInterval.organization_id == organization_id)
        )
        return rows.all()

    def add_all(self, intervals: Sequence[LithologyInterval]) -> None:
        self.session.add_all(intervals)
