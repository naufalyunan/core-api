"""Domain exceptions and their HTTP mapping.

Services raise these; they never import FastAPI/HTTPException. The handlers below
translate them to HTTP responses, keeping business logic transport-agnostic.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    default_detail: str = "Bad request"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(DomainError):
    """Also used for cross-tenant access so we never reveal that a resource exists."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Permission denied"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource already exists"


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
