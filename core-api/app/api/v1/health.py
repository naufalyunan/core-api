import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.dependencies import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("")
async def liveness() -> HealthStatus:
    """Process is up. Does not touch dependencies (use for container liveness probes)."""
    return HealthStatus()


@router.get("/ready")
async def readiness(session: SessionDep) -> HealthStatus:
    """Dependencies are reachable (use for readiness probes / load balancers)."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    return HealthStatus()
