"""Deny-by-default collection ACL and API authorization service (ADR-010).

The retrieval engine always calls ``AuthorizationService.check_collection_access``
before ranking, so binding that method to a real ACL store is what turns
"ACL leakage = 0" into an enforced server-side guarantee for the API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterable

from law_rag.ingestion.authorization import (
    AccessDeniedError,
    AuthorizationService,
    PermissionDeniedError,
)
from law_rag.ingestion.knowledge_models import (
    AccessLevel,
    AppUser,
    CollectionAccess,
    DocumentCollection,
)

from .security import RbacPolicy

_LEVEL_ORDER: dict[AccessLevel, int] = {
    AccessLevel.READ: 0,
    AccessLevel.WRITE: 1,
    AccessLevel.ADMIN: 2,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CollectionAcl:
    """In-memory collection ACL store: public collections plus explicit grants."""

    def __init__(self) -> None:
        self._collections: dict[str, DocumentCollection] = {}
        self._grants: dict[str, dict[str, AccessLevel]] = {}
        self._users_by_role: dict[str, set[str]] = {}

    def register_collection(self, collection: DocumentCollection) -> DocumentCollection:
        self._collections[collection.collection_id] = collection
        return collection

    def collection(self, collection_id: str) -> DocumentCollection | None:
        return self._collections.get(collection_id)

    def collection_ids(self) -> tuple[str, ...]:
        return tuple(self._collections)

    def grant(
        self,
        *,
        user_id: str,
        collection_id: str,
        access_level: AccessLevel = AccessLevel.READ,
        granted_by: str,
    ) -> CollectionAccess:
        if collection_id not in self._collections:
            raise ValueError(f"Unknown collection: {collection_id}")
        if access_level not in _LEVEL_ORDER:
            raise ValueError(f"Invalid access level: {access_level}")
        self._grants.setdefault(user_id, {})[collection_id] = access_level
        return CollectionAccess(
            collection_id=collection_id,
            user_id=user_id,
            access_level=access_level,
            granted_by=granted_by,
            granted_at=_now(),
        )

    def revoke(self, *, user_id: str, collection_id: str) -> bool:
        return self._grants.get(user_id, {}).pop(collection_id, None) is not None

    def assign_role(self, *, user_id: str, role_name: str) -> None:
        self._users_by_role.setdefault(role_name, set()).add(user_id)

    def roles_for(self, user_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(role for role, users in self._users_by_role.items() if user_id in users)
        )

    def effective_level(self, *, user_id: str, collection_id: str) -> AccessLevel | None:
        """Highest access level the user holds for a collection, or None."""
        collection = self._collections.get(collection_id)
        if collection is None:
            return None
        granted = self._grants.get(user_id, {}).get(collection_id)
        if granted is not None:
            return granted
        if collection.is_public:
            return AccessLevel.READ
        return None

    def has_access(
        self,
        *,
        user: AppUser,
        collection_id: str,
        min_access_level: AccessLevel = AccessLevel.READ,
    ) -> bool:
        if not user.is_active:
            return False
        if user.is_system:
            return collection_id in self._collections
        level = self.effective_level(user_id=user.user_id, collection_id=collection_id)
        if level is None:
            return False
        return _LEVEL_ORDER[level] >= _LEVEL_ORDER[min_access_level]

    def readable_collection_ids(
        self, *, user: AppUser, min_access_level: AccessLevel = AccessLevel.READ
    ) -> set[str]:
        if user.is_system:
            return set(self._collections)
        return {
            collection_id
            for collection_id in self._collections
            if self.has_access(
                user=user, collection_id=collection_id, min_access_level=min_access_level
            )
        }


class ApiAuthorizationService(AuthorizationService):
    """Server-side authorization: RBAC permission checks plus collection ACL."""

    def __init__(
        self,
        *,
        acl: CollectionAcl,
        rbac: RbacPolicy | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        super().__init__(clock=clock)
        self.acl = acl
        self.rbac = rbac or RbacPolicy()

    def assign_role(self, user_id: str, role_name: str) -> None:
        """Grant a role to a user; unknown roles are rejected."""
        if not self.rbac.known_role(role_name):
            raise ValueError(f"Unknown role: {role_name}")
        self.acl.assign_role(user_id=user_id, role_name=role_name)

    def get_user_permissions(self, user: AppUser) -> set[str]:
        if user.is_system:
            return set(self.rbac.permissions_for(("system_admin",)))
        return set(self.rbac.permissions_for(self.acl.roles_for(user.user_id)))

    def check_permission(self, user: AppUser, permission_name: str) -> None:
        if not user.is_active:
            raise PermissionDeniedError(f"User {user.user_id} is inactive")
        if permission_name not in self.get_user_permissions(user):
            raise PermissionDeniedError(f"Permission {permission_name} is required")

    def get_user_collections(
        self, user: AppUser, min_access_level: AccessLevel = AccessLevel.READ
    ) -> set[str]:
        return self.acl.readable_collection_ids(user=user, min_access_level=min_access_level)

    def check_collection_access(
        self,
        user: AppUser,
        collection_id: str,
        min_access_level: AccessLevel = AccessLevel.READ,
    ) -> None:
        if not self.acl.has_access(
            user=user, collection_id=collection_id, min_access_level=min_access_level
        ):
            raise AccessDeniedError(f"User {user.user_id} cannot read collection {collection_id}")

    def check_collection_ids(
        self,
        user: AppUser,
        collection_ids: Iterable[str],
        min_access_level: AccessLevel = AccessLevel.READ,
    ) -> bool:
        """True when the user can read at least one of the owning collections."""
        for collection_id in collection_ids:
            if self.acl.has_access(
                user=user, collection_id=collection_id, min_access_level=min_access_level
            ):
                return True
        return False

    def check_document_visibility(
        self,
        user: AppUser,
        is_restricted: bool,
        collection_ids: list[str],
    ) -> bool:
        if not user.is_active:
            return False
        if is_restricted and "document.view_restricted" not in self.get_user_permissions(user):
            return False
        return self.check_collection_ids(user, collection_ids)

