"""CSV ingestion through the API: upload -> 202 -> background job -> poll for the result.

With httpx's ASGITransport, FastAPI's background tasks finish before `client.post` returns,
so the very next GET already sees the final status. (A real server returns 202 first and
the job finishes a moment later; clients poll GET /ingestions/{id}.)
"""

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LithologyInterval
from app.schemas.user import CurrentUser
from tests.conftest import random_uuid

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
ClientFactory = Callable[[CurrentUser | None], AsyncClient]

RED_RIDGE_HOLES = [
    {"hole_id": "DH-001", "project": "Pilbara North", "latitude": -22.3104,
     "longitude": 118.7231, "total_depth_m": 60.0},
    {"hole_id": "DH-002", "project": "Pilbara North", "latitude": -22.3127,
     "longitude": 118.7289, "total_depth_m": 45.0},
]  # fmt: skip


def csv_upload(name: str) -> dict:
    return {"file": (name, (SAMPLES / name).read_bytes(), "text/csv")}


async def count_intervals(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(LithologyInterval)) or 0


@pytest.fixture
async def red_ridge(
    client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> AsyncIterator[AsyncClient]:
    """Company A's admin client, with DH-001 and DH-002 created."""
    async with client_as(tenants["a_admin"]) as client:
        for hole in RED_RIDGE_HOLES:
            assert (await client.post("/api/v1/drillholes", json=hole)).status_code == 201
        yield client


async def test_valid_csv_is_loaded(red_ridge: AsyncClient, session: AsyncSession) -> None:
    resp = await red_ridge.post(
        "/api/v1/ingestions", files=csv_upload("intervals_red_ridge_valid.csv")
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "pending"  # what the client sees immediately
    assert body["original_filename"] == "intervals_red_ridge_valid.csv"

    result = (await red_ridge.get(f"/api/v1/ingestions/{body['id']}")).json()
    assert result["status"] == "completed"
    assert result["rows_total"] == result["rows_valid"] == 11
    assert result["errors"] is None
    assert await count_intervals(session) == 11


async def test_invalid_csv_is_rejected_and_nothing_is_saved(
    red_ridge: AsyncClient,
    client_as: ClientFactory,
    tenants: dict[str, CurrentUser],
    session: AsyncSession,
) -> None:
    # DH-003 exists, but in Company B. Company A's file must still treat it as unknown.
    async with client_as(tenants["b_admin"]) as b:
        hole = {**RED_RIDGE_HOLES[0], "hole_id": "DH-003"}
        assert (await b.post("/api/v1/drillholes", json=hole)).status_code == 201

    resp = await red_ridge.post(
        "/api/v1/ingestions", files=csv_upload("intervals_red_ridge_invalid.csv")
    )
    assert resp.status_code == 202
    result = (await red_ridge.get(f"/api/v1/ingestions/{resp.json()['id']}")).json()

    assert result["status"] == "failed"
    assert result["rows_total"] == 11
    assert result["rows_valid"] == 1
    assert sorted({e["line"] for e in result["errors"]}) == list(range(3, 13))
    dh003 = next(e for e in result["errors"] if e["line"] == 10)
    assert dh003["message"] == "Unknown drillhole 'DH-003'"
    assert await count_intervals(session) == 0  # all-or-nothing


async def test_uploading_the_same_file_twice_fails_on_overlap(
    red_ridge: AsyncClient, session: AsyncSession
) -> None:
    for expected in ("completed", "failed"):
        resp = await red_ridge.post(
            "/api/v1/ingestions", files=csv_upload("intervals_red_ridge_valid.csv")
        )
        result = (await red_ridge.get(f"/api/v1/ingestions/{resp.json()['id']}")).json()
        assert result["status"] == expected
    assert "Overlaps existing interval" in result["errors"][0]["message"]
    assert await count_intervals(session) == 11


async def test_non_csv_file_is_rejected(red_ridge: AsyncClient) -> None:
    resp = await red_ridge.post(
        "/api/v1/ingestions", files={"file": ("photo.png", b"\x89PNG...", "image/png")}
    )
    assert resp.status_code == 415


async def test_too_large_file_is_rejected(red_ridge: AsyncClient) -> None:
    big = b"hole_id,from_m,to_m,lithology,rqd_pct\n" + b"x" * (5 * 1024 * 1024)
    resp = await red_ridge.post("/api/v1/ingestions", files={"file": ("big.csv", big, "text/csv")})
    assert resp.status_code == 413


async def test_viewer_cannot_upload(
    client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> None:
    async with client_as(tenants["a_viewer"]) as client:
        resp = await client.post(
            "/api/v1/ingestions", files=csv_upload("intervals_red_ridge_valid.csv")
        )
    assert resp.status_code == 403


async def test_other_tenant_cannot_see_ingestion(
    red_ridge: AsyncClient, client_as: ClientFactory, tenants: dict[str, CurrentUser]
) -> None:
    resp = await red_ridge.post(
        "/api/v1/ingestions", files=csv_upload("intervals_red_ridge_valid.csv")
    )
    async with client_as(tenants["b_admin"]) as b:
        other_tenant = await b.get(f"/api/v1/ingestions/{resp.json()['id']}")
        missing = await b.get(f"/api/v1/ingestions/{random_uuid()}")
    assert other_tenant.status_code == missing.status_code == 404


async def test_job_crash_marks_ingestion_failed(
    red_ridge: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexpected error must not leave the job stuck in "processing" or half-loaded."""

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated bug")

    monkeypatch.setattr("app.services.ingestion.validate_csv", boom)
    resp = await red_ridge.post(
        "/api/v1/ingestions", files=csv_upload("intervals_red_ridge_valid.csv")
    )
    result = (await red_ridge.get(f"/api/v1/ingestions/{resp.json()['id']}")).json()
    assert result["status"] == "failed"
    assert result["errors"] == [{"line": 0, "field": None, "message": "Internal processing error"}]
    assert await count_intervals(session) == 0
