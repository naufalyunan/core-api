from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request. Commit/rollback is the service layer's responsibility."""
    async with SessionLocal() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """For background jobs, which must open their OWN session.

    The request's session is closed as soon as the response is sent, but a background
    task runs after that. A dependency (instead of importing SessionLocal directly) lets
    tests point background jobs at the test database.
    """
    return SessionLocal
