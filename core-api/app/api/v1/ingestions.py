"""CSV ingestion endpoints. YOUR TURN: implement the two routes below.

Everything they need already exists:
  - IngestionServiceDep        app/services/ingestion.py  -> .create(user, filename), .get(user, id)
  - process_ingestion          app/services/ingestion.py  -> the background job
  - MAX_UPLOAD_BYTES           app/services/ingestion.py  -> 5 MB
  - SessionFactoryDep          app/core/dependencies.py   -> pass to the background job
  - require_role(Role.ADMIN)   app/core/dependencies.py   -> only admins may upload

Tests that must pass: uv run pytest tests/integration/test_ingestions.py
(Also add `ingestions` back to app/api/v1/__init__.py, or every request will 404.)
"""

import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status, BackgroundTasks, Depends

from app.core.dependencies import CurrentUserDep, SessionFactoryDep, require_role, Role
from app.services.ingestion import IngestionServiceDep, process_ingestion, MAX_UPLOAD_BYTES
from app.schemas.ingestion import IngestionRead

router = APIRouter(prefix="/ingestions", tags=["ingestions"])


@router.post(
    "", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_role(Role.ADMIN))]
)
async def create_ingestion(
    file: UploadFile,
    user: CurrentUserDep,
    service: IngestionServiceDep,
    session_factory: SessionFactoryDep,
    background_tasks: BackgroundTasks,
) -> IngestionRead:
    """Upload a lithology CSV. Returns 202 at once; processing continues in the background."""

    if file.filename.lower().endswith(".csv") is False:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only CSV files are accepted")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")
    ingestion = await service.create(user, file.filename)
    background_tasks.add_task(process_ingestion, session_factory, ingestion.id, content)
    return IngestionRead.model_validate(ingestion)


@router.get("/{ingestion_id}")
async def get_ingestion(
    ingestion_id: uuid.UUID, user: CurrentUserDep, service: IngestionServiceDep
) -> IngestionRead:
    """Status of one ingestion: pending, processing, completed, or failed (with errors)."""
    return IngestionRead.model_validate(await service.get(user, ingestion_id))
