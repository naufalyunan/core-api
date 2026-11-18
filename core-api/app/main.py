from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.init_db import create_tables
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # Startup: create any missing tables (this is what replaces `alembic upgrade head`).
    await create_tables(engine)
    yield
    # Shutdown: close pooled database connections.
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Multi-tenant geoscience data platform: drillholes and lithology intervals.",
        debug=settings.debug,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(v1_router)
    return app


app = create_app()
