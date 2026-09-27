"""FastAPI dependency providers for the REST API layer."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from law_rag.ingestion.knowledge_models import AppUser

from .container import ApiContainer
from .errors import ApiError, AuthenticationRequiredError
from .security import bearer_token_from_header


def get_container(request: Request) -> ApiContainer:
    """Return the container bound to the running application."""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, ApiContainer):
        raise ApiError("API container chưa được cấu hình.")
    return container


def get_request_id(request: Request) -> str:
    """Correlation id assigned by the request-id middleware."""
    return getattr(request.state, "request_id", "-")


def get_current_user(request: Request) -> AppUser:
    """Authenticate the caller from the Authorization header."""
    container = get_container(request)
    token = bearer_token_from_header(request.headers.get("authorization"))
    if token is None:
        raise AuthenticationRequiredError("Cần header Authorization: Bearer <token>.")
    return container.authenticate(token)


def require_permission(permission: str) -> Callable[[Request], AppUser]:
    """Build a dependency that authenticates the caller and checks a permission."""

    def dependency(request: Request) -> AppUser:
        container = get_container(request)
        user = get_current_user(request)
        container.authorize(user, permission)
        return user

    return dependency
