"""Data access for drillholes.

Rule: every method takes organization_id and filters by it. There is deliberately no
"get by id" without a tenant — that makes cross-tenant leaks hard to write by accident.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.drillhole import Drillhole


class DrillholeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, organization_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[Sequence[Drillhole], int]:
        base = select(Drillhole).where(Drillhole.organization_id == organization_id)
        total = await self.session.scalar(select(func.count()).select_from(base.subquery()))
        rows = await self.session.scalars(
            base.order_by(Drillhole.hole_id).limit(limit).offset(offset)
        )
        return rows.all(), total or 0

    async def get(self, organization_id: uuid.UUID, drillhole_id: uuid.UUID) -> Drillhole | None:
        return await self.session.scalar(
            select(Drillhole).where(
                Drillhole.id == drillhole_id,
                Drillhole.organization_id == organization_id,
            )
        )

    async def list_all(self, organization_id: uuid.UUID) -> Sequence[Drillhole]:
        """Every drillhole of one organization (used by ingestion to resolve hole_ids)."""
        rows = await self.session.scalars(
            select(Drillhole).where(Drillhole.organization_id == organization_id)
        )
        return rows.all()

    async def get_by_hole_id(self, organization_id: uuid.UUID, hole_id: str) -> Drillhole | None:
        return await self.session.scalar(
            select(Drillhole).where(
                Drillhole.hole_id == hole_id,
                Drillhole.organization_id == organization_id,
            )
        )

    def add(self, drillhole: Drillhole) -> None:
        self.session.add(drillhole)

    async def delete(self, drillhole: Drillhole) -> None:
        await self.session.delete(drillhole)
