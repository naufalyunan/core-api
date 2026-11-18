"""Shared test fixtures.

- A real Postgres 17 runs in Docker via Testcontainers (Docker must be running).
- Tables are created with create_tables(), the same function the app runs at startup.
- Every test starts with empty tables.
- `client_as(user)` builds a fresh app (via create_app) whose get_current_user is overridden,
  so tenancy/RBAC tests don't need to log in. tests/integration/test_auth.py covers the real
  login + token flow.
"""

import uuid
from collections.abc import AsyncIterator, Callable, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.db.base import Base
from app.db.init_db import create_tables
from app.db.models import Organization, Role, User
from app.db.session import get_session, get_session_factory
from app.main import create_app
from app.schemas.user import CurrentUser

TEST_PASSWORD = "DemoPass123!"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    await create_tables(engine)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def test_password_hash() -> str:
    # Argon2 is slow on purpose, so hash once per test session, not once per user.
    return hash_password(TEST_PASSWORD)


@pytest.fixture(scope="session")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _clean_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


# --- Tenants & users ----------------------------------------------------------------


async def _create_user(
    session: AsyncSession, org: Organization, email: str, role: Role, hashed_password: str
) -> User:
    user = User(organization_id=org.id, email=email, hashed_password=hashed_password, role=role)
    session.add(user)
    await session.flush()
    return user


def _principal(user: User) -> CurrentUser:
    return CurrentUser(id=user.id, organization_id=user.organization_id, role=user.role)


@pytest.fixture
async def tenants(session: AsyncSession, test_password_hash: str) -> dict[str, CurrentUser]:
    """Two organizations, each with an admin and a viewer (mirrors data/seed).

    Every user's password is TEST_PASSWORD.
    """
    org_a = Organization(name="Red Ridge Mining", slug="red-ridge")
    org_b = Organization(name="Atacama Copper Co", slug="atacama-copper")
    session.add_all([org_a, org_b])
    await session.flush()
    pw = test_password_hash
    users = {
        "a_admin": await _create_user(session, org_a, "admin@redridge.example", Role.ADMIN, pw),
        "a_viewer": await _create_user(session, org_a, "viewer@redridge.example", Role.VIEWER, pw),
        "b_admin": await _create_user(session, org_b, "admin@atacama.example", Role.ADMIN, pw),
        "b_viewer": await _create_user(session, org_b, "viewer@atacama.example", Role.VIEWER, pw),
    }
    await session.commit()
    return {k: _principal(u) for k, u in users.items()}


# --- HTTP clients -------------------------------------------------------------------


@pytest.fixture
def client_as(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[CurrentUser | None], AsyncClient]:
    """Build an HTTP client authenticated as `user` (or anonymous when None)."""

    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    def _make(user: CurrentUser | None) -> AsyncClient:
        app = create_app()
        app.dependency_overrides[get_session] = _get_test_session
        # Background jobs (ingestion) open their own sessions: point them at the test DB too.
        app.dependency_overrides[get_session_factory] = lambda: session_factory
        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return _make


@pytest.fixture
async def anon_client(
    client_as: Callable[[CurrentUser | None], AsyncClient],
) -> AsyncIterator[AsyncClient]:
    async with client_as(None) as c:
        yield c


def random_uuid() -> str:
    return str(uuid.uuid4())
