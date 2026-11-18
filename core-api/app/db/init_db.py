"""Create database tables from the SQLAlchemy models (replaces Alembic).

`Base.metadata.create_all` runs CREATE TABLE / CREATE TYPE / CREATE INDEX for every model
registered on Base.metadata, and skips anything that already exists (checkfirst=True).

Limitation: it never ALTERs an existing table. If you add, rename or change a column,
the existing table is left as it was. In local dev, reset with `drop_tables()` (or
`docker compose down -v`). For a database with real data you'd need migrations again.
"""

from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import models  # noqa: F401  (imports every model so Base.metadata knows them)
from app.db.base import Base


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        # create_all is synchronous; run_sync runs it on the async connection.
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables(engine: AsyncEngine) -> None:
    """Delete every table. Local dev / tests only."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
