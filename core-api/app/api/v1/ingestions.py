"""CSV ingestion endpoints: upload a lithology CSV, then poll for the processing result."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from app.core.dependencies import CurrentUserDep, SessionFactoryDep, require_role
from app.db.models.user import Role
from app.schemas.ingestion import IngestionRead
from app.services.ingestion import MAX_UPLOAD_BYTES, IngestionServiceDep, process_ingestion

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

    filename = file.filename or ""  # a client may send a file part without a filename
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only CSV files are accepted")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")
    ingestion = await service.create(user, filename)
    background_tasks.add_task(process_ingestion, session_factory, ingestion.id, content)
    return IngestionRead.model_validate(ingestion)


@router.get("/{ingestion_id}")
async def get_ingestion(
    ingestion_id: uuid.UUID, user: CurrentUserDep, service: IngestionServiceDep
) -> IngestionRead:
    """Status of one ingestion: pending, processing, completed, or failed (with errors)."""
    return IngestionRead.model_validate(await service.get(user, ingestion_id))
