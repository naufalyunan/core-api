import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DrillholeBase(BaseModel):
    hole_id: str = Field(min_length=1, max_length=50, examples=["DH-001"])
    project: str = Field(min_length=1, max_length=200, examples=["Pilbara North"])
    latitude: float = Field(ge=-90, le=90, examples=[-22.3104])
    longitude: float = Field(ge=-180, le=180, examples=[118.7231])
    total_depth_m: float = Field(gt=0, examples=[60.0])


class DrillholeCreate(DrillholeBase):
    # NOTE: no organization_id here on purpose — it comes from the authenticated user.
    pass


class DrillholeUpdate(BaseModel):
    project: str | None = Field(default=None, min_length=1, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    total_depth_m: float | None = Field(default=None, gt=0)


class DrillholeRead(DrillholeBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
