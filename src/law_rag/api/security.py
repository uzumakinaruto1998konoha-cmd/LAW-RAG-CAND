"""Authentication and RBAC policy for the REST API.

Baseline decisions recorded for this layer (see docs/17 decision log):
- Authentication uses an opaque bearer token resolved on the server to an
  ``AppUser`` (baseline local account per ADR-009). Raw tokens are never
  persisted or logged: only a SHA-256 digest is held in memory so a process
  dump of the registry does not disclose usable credentials.
- Authorization is deny-by-default RBAC. The role matrix below is a
  provisional default that deployments may override through
  ``RbacPolicy(role_permissions=...)``; ADR-010 keeps the final matrix open.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Iterable, Mapping

from .errors import AuthenticationRequiredError

LOGGER = logging.getLogger(__name__)

_PERMISSION_CATALOGUE: frozenset[str] = frozenset(
    {
        "search.query",
        "chat.query",
        "document.view",
        "document.upload",
        "document.edit_metadata",
        "document.approve",
        "version.view",
        "relation.manage",
        "collection.manage",
        "index.manage",
        "audit.view",
    }
)

DEFAULT_ROLE_PERMISSIONS: Mapping[str, frozenset[str]] = {
    "system_admin": _PERMISSION_CATALOGUE,
    "knowledge_admin": frozenset(
        {
            "search.query",
            "chat.query",
            "document.view",
            "document.upload",
            "document.edit_metadata",
            "document.approve",
            "version.view",
            "relation.manage",
            "collection.manage",
            "index.manage",
        }
    ),
    "reviewer": frozenset(
        {
            "search.query",
            "chat.query",
            "document.view",
            "document.edit_metadata",
            "document.approve",
            "version.view",
            "relation.manage",
        }
    ),
    "user": frozenset({"search.query", "chat.query", "document.view", "version.view"}),
    "auditor": frozenset({"document.view", "version.view", "audit.view"}),
}


class RbacPolicy:
    """Resolve permissions from role assignments without touching legal data."""

    def __init__(self, *, role_permissions: Mapping[str, Iterable[str]] | None = None) -> None:
        source = role_permissions if role_permissions is not None else DEFAULT_ROLE_PERMISSIONS
        self._role_permissions: dict[str, frozenset[str]] = {
            role: frozenset(permissions) for role, permissions in source.items()
        }

    def known_role(self, role_name: str) -> bool:
        return role_name in self._role_permissions

    def permissions_for(self, role_names: Iterable[str]) -> frozenset[str]:
        """Union of permissions granted by the given roles (unknown roles grant nothing)."""
        granted: set[str] = set()
        for role_name in role_names:
            granted.update(self._role_permissions.get(role_name, ()))
        return frozenset(granted)


def hash_token(token: str) -> str:
    """Digest a bearer token for storage (raw tokens are never kept)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token_from_header(header_value: str | None) -> str | None:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


class TokenAuthenticator:
    """Server-side registry mapping issued tokens to user ids."""

    def __init__(self, *, token_factory=secrets.token_urlsafe) -> None:
        self._token_factory = token_factory
        self._digests: dict[str, str] = {}

    def issue_token(self, user_id: str) -> str:
        """Generate and register a new token for the user."""
        return self.register_token(user_id, self._token_factory(32))

    def register_token(self, user_id: str, token: str) -> None:
        """Register a provisioned token (used by deployment tooling and tests)."""
        if not token or len(token) < 16:
            raise ValueError("Bearer tokens must be at least 16 characters")
        self._digests[hash_token(token)] = user_id

    def revoke_token(self, token: str) -> bool:
        return self._digests.pop(hash_token(token), None) is not None

    def authenticate(self, token: str | None) -> str:
        """Return the user id for a token or raise with a generic message."""
        if not token:
            raise AuthenticationRequiredError("Bearer token is required.")
        user_id = self._digests.get(hash_token(token))
        if user_id is None:
            LOGGER.info("Rejected bearer token digest_prefix=%s", hash_token(token)[:12])
            raise AuthenticationRequiredError("Bearer token is not valid.")
        return user_id
