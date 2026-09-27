"""PHASE 5 REST API package: FastAPI application, routers, and security glue."""

from __future__ import annotations

from .acl import ApiAuthorizationService, CollectionAcl
from .app import API_PREFIX, create_app
from .container import ApiContainer
from .errors import (
    ApiError,
    AuthenticationRequiredError,
    AuthorizationDeniedApiError,
    ConflictApiError,
    ResourceNotFoundApiError,
    ServiceUnavailableApiError,
    ValidationApiError,
)
from .security import RbacPolicy, TokenAuthenticator, bearer_token_from_header

__all__ = [
    "API_PREFIX",
    "ApiAuthorizationService",
    "ApiContainer",
    "ApiError",
    "AuthenticationRequiredError",
    "AuthorizationDeniedApiError",
    "CollectionAcl",
    "ConflictApiError",
    "RbacPolicy",
    "ResourceNotFoundApiError",
    "ServiceUnavailableApiError",
    "TokenAuthenticator",
    "ValidationApiError",
    "bearer_token_from_header",
    "create_app",
]
