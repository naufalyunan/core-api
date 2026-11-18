from fastapi import APIRouter

from app.core.dependencies import CurrentUserDep, SessionDep
from app.core.exceptions import NotFoundError
from app.repositories.user import UserRepository
from app.schemas.user import UserRead

router = APIRouter(tags=["users"])


@router.get("/me")
async def read_me(current: CurrentUserDep, session: SessionDep) -> UserRead:
    """The logged-in user's profile, including their organization and role."""
    user = await UserRepository(session).get_by_id(current.id)
    if user is None:
        raise NotFoundError("User not found")
    return UserRead.model_validate(user)
