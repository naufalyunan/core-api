import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models.user import Role


class CurrentUser(BaseModel):
    """The authenticated principal, resolved from the access token.

    This is the ONLY source of organization_id for tenant scoping.
    """

    id: uuid.UUID
    organization_id: uuid.UUID
    role: Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    role: Role
    is_active: bool
