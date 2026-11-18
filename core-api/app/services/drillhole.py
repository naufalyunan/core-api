"""Business logic for drillholes. Owns the transaction (commit) and raises domain errors."""

import uuid
from typing import Annotated

from fastapi import Depends

from app.core.dependencies import SessionDep
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.drillhole import Drillhole
from app.repositories.drillhole import DrillholeRepository
from app.schemas.common import Page, PageParams
from app.schemas.drillhole import DrillholeCreate, DrillholeRead, DrillholeUpdate
from app.schemas.user import CurrentUser


class DrillholeService:
    def __init__(self, session: SessionDep) -> None:
        self.session = session
        self.repo = DrillholeRepository(session)

    async def list(self, user: CurrentUser, page: PageParams) -> Page[DrillholeRead]:
        rows, total = await self.repo.list(
            user.organization_id, limit=page.limit, offset=page.offset
        )
        return Page[DrillholeRead](
            items=[DrillholeRead.model_validate(r) for r in rows],
            total=total,
            limit=page.limit,
            offset=page.offset,
        )

    async def get(self, user: CurrentUser, drillhole_id: uuid.UUID) -> Drillhole:
        drillhole = await self.repo.get(user.organization_id, drillhole_id)
        if drillhole is None:
            # Same response whether it doesn't exist or belongs to another tenant.
            raise NotFoundError("Drillhole not found")
        return drillhole

    async def create(self, user: CurrentUser, data: DrillholeCreate) -> Drillhole:
        if await self.repo.get_by_hole_id(user.organization_id, data.hole_id):
            raise ConflictError(f"Drillhole {data.hole_id!r} already exists")
        drillhole = Drillhole(organization_id=user.organization_id, **data.model_dump())
        self.repo.add(drillhole)
        await self.session.commit()
        await self.session.refresh(drillhole)
        return drillhole

    async def update(
        self, user: CurrentUser, drillhole_id: uuid.UUID, data: DrillholeUpdate
    ) -> Drillhole:
        drillhole = await self.get(user, drillhole_id)

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(drillhole, key, value)

        await self.session.commit()
        await self.session.refresh(drillhole)
        return drillhole

    async def delete(self, user: CurrentUser, drillhole_id: uuid.UUID) -> None:
        drillhole = await self.get(user, drillhole_id)
        await self.repo.delete(drillhole)
        await self.session.commit()


DrillholeServiceDep = Annotated[DrillholeService, Depends()]
