from fastapi import APIRouter

from app.api.v1 import auth, drillholes, health, ingestions, users

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health.router)
v1_router.include_router(auth.router)
v1_router.include_router(users.router)
v1_router.include_router(drillholes.router)
v1_router.include_router(ingestions.router)
