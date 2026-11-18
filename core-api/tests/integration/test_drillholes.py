from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.schemas.user import CurrentUser

DH_001 = {
    "hole_id": "DH-001",
    "project": "Pilbara North",
    "latitude": -22.3104,
    "longitude": 118.7231,
    "total_depth_m": 60.0,
}

ClientFactory = Callable[[CurrentUser | None], AsyncClient]


async def test_admin_creates_and_lists_drillhole(
    client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> None:
    async with client_as(tenants["a_admin"]) as client:
        created = await client.post("/api/v1/drillholes", json=DH_001)
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["hole_id"] == "DH-001"
        assert "organization_id" not in body

        listed = await client.get("/api/v1/drillholes")
        assert listed.status_code == 200
        page = listed.json()
        assert page["total"] == 1
        assert page["items"][0]["id"] == body["id"]

        fetched = await client.get(f"/api/v1/drillholes/{body['id']}")
        assert fetched.status_code == 200


async def test_duplicate_hole_id_in_same_org_conflicts(
    client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> None:
    async with client_as(tenants["a_admin"]) as client:
        assert (await client.post("/api/v1/drillholes", json=DH_001)).status_code == 201
        assert (await client.post("/api/v1/drillholes", json=DH_001)).status_code == 409


async def test_same_hole_id_allowed_in_different_orgs(
    client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> None:
    async with client_as(tenants["a_admin"]) as a, client_as(tenants["b_admin"]) as b:
        assert (await a.post("/api/v1/drillholes", json=DH_001)).status_code == 201
        assert (await b.post("/api/v1/drillholes", json=DH_001)).status_code == 201


@pytest.mark.parametrize(
    "field,value",
    [("latitude", 91), ("longitude", -181), ("total_depth_m", 0), ("hole_id", "")],
)
async def test_invalid_payload_rejected(
    client_as: ClientFactory, tenants: dict[str, CurrentUser], field: str, value: object
) -> None:
    async with client_as(tenants["a_admin"]) as client:
        resp = await client.post("/api/v1/drillholes", json={**DH_001, field: value})
        assert resp.status_code == 422


async def test_unauthenticated_request_rejected(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/drillholes")
    assert resp.status_code == 401
