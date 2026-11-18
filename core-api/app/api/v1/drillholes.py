"""Drillhole endpoints. Routes stay thin: parse input, call the service, return a schema."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import CurrentUserDep, require_role
from app.db.models.user import Role
from app.schemas.common import Page, PageParams
from app.schemas.drillhole import DrillholeCreate, DrillholeRead, DrillholeUpdate
from app.services.drillhole import DrillholeServiceDep

router = APIRouter(prefix="/drillholes", tags=["drillholes"])

AdminOnly = Depends(require_role(Role.ADMIN))


@router.get("")
async def list_drillholes(
    user: CurrentUserDep,
    service: DrillholeServiceDep,
    page: Annotated[PageParams, Query()],
) -> Page[DrillholeRead]:
    return await service.list(user, page)


@router.get("/{drillhole_id}")
async def get_drillhole(
    drillhole_id: uuid.UUID, user: CurrentUserDep, service: DrillholeServiceDep
) -> DrillholeRead:
    return DrillholeRead.model_validate(await service.get(user, drillhole_id))


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[AdminOnly])
async def create_drillhole(
    data: DrillholeCreate, user: CurrentUserDep, service: DrillholeServiceDep
) -> DrillholeRead:
    return DrillholeRead.model_validate(await service.create(user, data))


@router.patch("/{drillhole_id}", dependencies=[AdminOnly])
async def update_drillhole(
    drillhole_id: uuid.UUID,
    data: DrillholeUpdate,
    user: CurrentUserDep,
    service: DrillholeServiceDep,
) -> DrillholeRead:
    return DrillholeRead.model_validate(await service.update(user, drillhole_id, data))


@router.delete("/{drillhole_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminOnly])
async def delete_drillhole(
    drillhole_id: uuid.UUID, user: CurrentUserDep, service: DrillholeServiceDep
) -> None:
    await service.delete(user, drillhole_id)
