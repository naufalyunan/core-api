"""Password hashing (Argon2 via pwdlib) and JWT access tokens (PyJWT)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

REQUIRED_CLAIMS = ["sub", "org_id", "role", "exp", "iat"]

# Build the hasher 
password_hash = PasswordHash.recommended()

# A real Argon2 hash of a random value. Login verifies against it when the email doesn't
# exist, so "unknown email" and "wrong password" take the same time (no user enumeration).
DUMMY_HASH = password_hash.hash("dummy-password-for-constant-time-login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """True if `password` matches. Never raises for a malformed/legacy stored hash."""
    try:
        return password_hash.verify(password, hashed_password)
    except UnknownHashError:
        return False


def create_access_token(*, subject: str, organization_id: str, role: str) -> str:
    """Create a signed, short-lived access token for an authenticated user."""
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": subject,  # user id
        "org_id": organization_id,  # tenant
        "role": role,
        "iat": now,  # issued at
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Return the claims, or raise if the token is invalid/expired.

    Raises jwt.InvalidTokenError (or a subclass such as jwt.ExpiredSignatureError /
    jwt.MissingRequiredClaimError). The caller turns that into a 401.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        # Pin the accepted algorithm(s): never trust the "alg" header from the token itself.
        algorithms=[settings.jwt_algorithm],
        options={"require": REQUIRED_CLAIMS},
    )
