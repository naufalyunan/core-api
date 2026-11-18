"""CSV ingestion: create the job (during the request) and process it (after the response).

Flow:
  POST /ingestions  -> IngestionService.create()        status = pending, return 202
                    -> BackgroundTasks runs process_ingestion() after the response is sent
  process_ingestion -> status = processing
                    -> validate_csv()                    all-or-nothing:
                         errors?  -> status = failed, store errors, insert nothing
                         no errors -> insert every interval, status = completed
  GET /ingestions/{id} -> IngestionService.get()        client polls until completed/failed
"""

import logging
import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.dependencies import SessionDep
from app.core.exceptions import NotFoundError
from app.db.models.ingestion import Ingestion, IngestionStatus
from app.db.models.interval import LithologyInterval
from app.repositories.drillhole import DrillholeRepository
from app.repositories.ingestion import IngestionRepository
from app.repositories.interval import IntervalRepository
from app.schemas.user import CurrentUser
from app.services.ingestion_validation import HoleInfo, validate_csv

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class IngestionService:
    def __init__(self, session: SessionDep) -> None:
        self.session = session
        self.repo = IngestionRepository(session)

    async def create(self, user: CurrentUser, filename: str) -> Ingestion:
        """Record a new pending ingestion for the user's organization."""
        ingestion = Ingestion(
            organization_id=user.organization_id,
            created_by_id=user.id,
            original_filename=filename,
            status=IngestionStatus.PENDING,
        )
        self.repo.add(ingestion)
        await self.session.commit()
        await self.session.refresh(ingestion)
        return ingestion

    async def get(self, user: CurrentUser, ingestion_id: uuid.UUID) -> Ingestion:
        ingestion = await self.repo.get(user.organization_id, ingestion_id)
        if ingestion is None:
            raise NotFoundError("Ingestion not found")
        return ingestion


IngestionServiceDep = Annotated[IngestionService, Depends()]


async def process_ingestion(
    session_factory: async_sessionmaker[AsyncSession], ingestion_id: uuid.UUID, content: bytes
) -> None:
    """Background job. Runs after the 202 response, so it opens its own DB session."""
    async with session_factory() as session:
        ingestion = await IngestionRepository(session).get_for_job(ingestion_id)
        if ingestion is None:
            logger.error("Ingestion %s not found; skipping", ingestion_id)
            return

        ingestion.status = IngestionStatus.PROCESSING
        await session.commit()

        try:
            await _validate_and_load(session, ingestion, content)
        except Exception:
            # Never leave a job stuck in "processing": record the failure, log the details.
            logger.exception("Ingestion %s crashed", ingestion_id)
            await session.rollback()
            # rollback() expires loaded objects; reload before touching attributes, because
            # an async session can't lazy-load them implicitly.
            await session.refresh(ingestion)
            ingestion.status = IngestionStatus.FAILED
            ingestion.errors = [{"line": 0, "field": None, "message": "Internal processing error"}]
        await session.commit()

        logger.info(
            "Ingestion %s finished: status=%s rows_total=%s rows_valid=%s",
            ingestion_id,
            ingestion.status,
            ingestion.rows_total,
            ingestion.rows_valid,
        )


async def _validate_and_load(session: AsyncSession, ingestion: Ingestion, content: bytes) -> None:
    org_id = ingestion.organization_id

    # Only THIS organization's drillholes: another tenant's hole_id is simply "unknown".
    drillholes = await DrillholeRepository(session).list_all(org_id)
    holes = {d.hole_id: HoleInfo(d.id, d.total_depth_m) for d in drillholes}
    hole_id_by_pk = {d.id: d.hole_id for d in drillholes}

    existing: dict[str, list[tuple[float, float]]] = defaultdict(list)
    interval_repo = IntervalRepository(session)
    for interval in await interval_repo.list_for_organization(org_id):
        existing[hole_id_by_pk[interval.drillhole_id]].append((interval.from_m, interval.to_m))

    result = validate_csv(content, holes, existing)
    ingestion.rows_total = result.rows_total
    ingestion.rows_valid = result.rows_valid

    if result.errors:
        # All-or-nothing: one bad row rejects the whole file, so a dataset is never half-loaded.
        ingestion.status = IngestionStatus.FAILED
        ingestion.errors = [e.model_dump() for e in result.errors]
        return

    interval_repo.add_all(
        [
            LithologyInterval(
                organization_id=org_id,
                drillhole_id=holes[row.hole_id].id,
                from_m=row.from_m,
                to_m=row.to_m,
                lithology=row.lithology,
                rqd_pct=row.rqd_pct,
            )
            for _, row in result.rows
        ]
    )
    ingestion.status = IngestionStatus.COMPLETED
    ingestion.errors = None
