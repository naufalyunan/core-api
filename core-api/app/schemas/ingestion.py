import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.ingestion import IngestionStatus


class IntervalRow(BaseModel):
    """One row of an uploaded lithology CSV: the rules that only need this row.

    Rules that need context (overlaps, depth beyond the hole's total depth, unknown
    hole_id for this tenant) are in app/services/ingestion_validation.py.
    """

    hole_id: str = Field(min_length=1, max_length=50)
    from_m: float = Field(ge=0)
    to_m: float = Field(gt=0)
    lithology: str = Field(min_length=1, max_length=100)
    rqd_pct: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def check_interval_order(self) -> Self:
        # Runs after the field checks, so from_m and to_m are already valid floats.
        if self.to_m <= self.from_m:
            raise ValueError("to_m must be greater than from_m")
        return self


class IngestionError(BaseModel):
    line: int
    field: str | None = None
    message: str


class IngestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: IngestionStatus
    original_filename: str
    rows_total: int | None
    rows_valid: int | None
    errors: list[IngestionError] | None
    created_at: datetime
    updated_at: datetime
