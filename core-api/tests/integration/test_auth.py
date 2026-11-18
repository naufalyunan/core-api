"""Authentication (login, tokens) and authorization (roles) through the real HTTP flow."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User
from app.schemas.user import CurrentUser
from tests.conftest import TEST_PASSWORD
from tests.integration.test_drillholes import DH_001

LOGIN = "/api/v1/auth/login"


async def login(client: AsyncClient, email: str, password: str = TEST_PASSWORD) -> str:
    resp = await client.post(LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_login_returns_token_and_me_works(
    anon_client: AsyncClient, tenants: dict[str, CurrentUser]
) -> None:
    token = await login(anon_client, "admin@redridge.example")

    me = await anon_client.get("/api/v1/me", headers=bearer(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "admin@redridge.example"
    assert body["role"] == "admin"
    assert body["organization_id"] == str(tenants["a_admin"].organization_id)
    assert "hashed_password" not in body


@pytest.mark.parametrize(
    "email,password",
    [
        ("admin@redridge.example", "wrong-password"),  # wrong password
        ("nobody@redridge.example", TEST_PASSWORD),  # unknown email
    ],
)
async def test_login_failures_look_identical(
    anon_client: AsyncClient, tenants: dict[str, CurrentUser], email: str, password: str
) -> None:
    resp = await anon_client.post(LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Incorrect email or password"}


async def test_inactive_user_cannot_log_in(
    anon_client: AsyncClient, tenants: dict[str, CurrentUser], session: AsyncSession
) -> None:
    await session.execute(
        update(User).where(User.email == "viewer@redridge.example").values(is_active=False)
    )
    await session.commit()
    resp = await anon_client.post(
        LOGIN, json={"email": "viewer@redridge.example", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 401


async def test_missing_token_is_401(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c"])
async def test_garbage_token_is_401(anon_client: AsyncClient, token: str) -> None:
    resp = await anon_client.get("/api/v1/me", headers=bearer(token))
    assert resp.status_code == 401


async def test_expired_token_is_401(
    anon_client: AsyncClient, tenants: dict[str, CurrentUser]
) -> None:
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    user = tenants["a_admin"]
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "org_id": str(user.organization_id),
            "role": "admin",
            "iat": past - timedelta(minutes=30),
            "exp": past,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    resp = await anon_client.get("/api/v1/me", headers=bearer(expired))
    assert resp.status_code == 401


async def test_role_is_enforced_with_real_token(
    anon_client: AsyncClient, tenants: dict[str, CurrentUser]
) -> None:
    viewer = await login(anon_client, "viewer@redridge.example")
    admin = await login(anon_client, "admin@redridge.example")

    denied = await anon_client.post("/api/v1/drillholes", json=DH_001, headers=bearer(viewer))
    assert denied.status_code == 403

    created = await anon_client.post("/api/v1/drillholes", json=DH_001, headers=bearer(admin))
    assert created.status_code == 201

    # Viewers can still read.
    listed = await anon_client.get("/api/v1/drillholes", headers=bearer(viewer))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
