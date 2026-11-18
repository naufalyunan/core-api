"""Tenant isolation & RBAC: the most important tests in this project.

A user must never read or modify another organization's data, even when guessing IDs,
and must get 404 (not 403) so the response doesn't reveal that the resource exists.

Tests marked xfail cover features you still need to implement; remove the marker once done.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.schemas.user import CurrentUser
from tests.conftest import TEST_PASSWORD, random_uuid
from tests.integration.test_drillholes import DH_001

ClientFactory = Callable[[CurrentUser | None], AsyncClient]


@pytest.fixture
async def a_drillhole_id(client_as: ClientFactory, tenants: dict[str, CurrentUser]) -> str:
    async with client_as(tenants["a_admin"]) as client:
        resp = await client.post("/api/v1/drillholes", json=DH_001)
        assert resp.status_code == 201
        return resp.json()["id"]


async def test_other_tenant_cannot_read_drillhole(
    client_as: ClientFactory, tenants: dict[str, CurrentUser], a_drillhole_id: str
) -> None:
    async with client_as(tenants["b_admin"]) as client:
        resp = await client.get(f"/api/v1/drillholes/{a_drillhole_id}")
    assert resp.status_code == 404


async def test_cross_tenant_and_missing_ids_are_indistinguishable(
    client_as: ClientFactory, tenants: dict[str, CurrentUser], a_drillhole_id: str
) -> None:
    async with client_as(tenants["b_admin"]) as client:
        other_tenant = await client.get(f"/api/v1/drillholes/{a_drillhole_id}")
        missing = await client.get(f"/api/v1/drillholes/{random_uuid()}")
    assert other_tenant.status_code == missing.status_code == 404
    assert other_tenant.json() == missing.json()


async def test_other_tenant_list_excludes_foreign_drillholes(
    client_as: ClientFactory, tenants: dict[str, CurrentUser], a_drillhole_id: str
) -> None:
    async with client_as(tenants["b_viewer"]) as client:
        resp = await client.get("/api/v1/drillholes")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_viewer_cannot_create_drillhole(
    client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> None:
    async with client_as(tenants["a_viewer"]) as client:
        resp = await client.post("/api/v1/drillholes", json=DH_001)
    assert resp.status_code == 403


async def test_other_tenant_cannot_update_drillhole(
    client_as: ClientFactory, tenants: dict[str, CurrentUser], a_drillhole_id: str
) -> None:
    async with client_as(tenants["b_admin"]) as client:
        resp = await client.patch(f"/api/v1/drillholes/{a_drillhole_id}", json={"project": "x"})
    assert resp.status_code == 404


async def test_other_tenant_cannot_delete_drillhole(
    client_as: ClientFactory, tenants: dict[str, CurrentUser], a_drillhole_id: str
) -> None:
    async with client_as(tenants["b_admin"]) as client:
        resp = await client.delete(f"/api/v1/drillholes/{a_drillhole_id}")
    assert resp.status_code == 404


async def test_end_to_end_with_real_jwt(
    anon_client: AsyncClient, tenants: dict[str, CurrentUser], a_drillhole_id: str
) -> None:
    """Company B logs in for real and still can't see Company A's drillhole."""
    login = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@atacama.example", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    resp = await anon_client.get(
        f"/api/v1/drillholes/{a_drillhole_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
