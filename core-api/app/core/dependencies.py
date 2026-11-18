import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import PermissionDeniedError
from app.core.security import decode_access_token
from app.db.models.user import Role
from app.db.session import get_session
from app.repositories.user import UserRepository
from app.schemas.user import CurrentUser

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Reads the "Authorization: Bearer <token>" header. It also adds an "Authorize" button to
# /docs where you paste the token. auto_error=False so we return our own 401 below.
bearer_scheme = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(credentials: BearerDep, session: SessionDep) -> CurrentUser:
    """Authentication: who is calling? Turns the bearer token into a CurrentUser, or 401."""
    if credentials is None:
        raise _unauthorized()

    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc

    # Load the user from the DB on every request, so a deactivated or deleted user is locked
    # out immediately, and organization_id/role come from the database, not from the client.
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")

    return CurrentUser(id=user.id, organization_id=user.organization_id, role=user.role)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """Authorization: is the caller allowed? Returns 403 if the user's role isn't in `roles`.

    Usage: `dependencies=[Depends(require_role(Role.ADMIN))]` on a route or router.
    """

    async def checker(user: CurrentUserDep) -> CurrentUser:
        if user.role not in roles:
            raise PermissionDeniedError()
        return user

    return checker
