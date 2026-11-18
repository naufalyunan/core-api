from httpx import AsyncClient


async def test_liveness(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readiness_checks_database(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/health/ready")
    assert resp.status_code == 200
