from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import SessionDep
from app.core.security import DUMMY_HASH, create_access_token, verify_password
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(data: LoginRequest, session: SessionDep) -> Token:
    """Exchange email + password for a JWT access token."""
    user = await UserRepository(session).get_by_email(data.email)

    # Always run one Argon2 verify (against DUMMY_HASH if the email is unknown) so the
    # response time doesn't reveal which emails have accounts.
    hashed = user.hashed_password if user else DUMMY_HASH
    password_ok = verify_password(data.password, hashed)

    if user is None or not password_ok or not user.is_active:
        # Same message for every failure: don't tell the caller which part was wrong.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    token = create_access_token(
        subject=str(user.id),
        organization_id=str(user.organization_id),
        role=user.role.value,
    )
    return Token(access_token=token)
