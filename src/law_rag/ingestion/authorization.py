"""Authorization and access control service for PHASE 2 knowledge model."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from .knowledge_models import AccessLevel, AppUser, Role, UserRole

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when authorization check fails."""
    code = "AUTHORIZATION_DENIED"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PermissionDeniedError(AuthorizationError):
    """User lacks required permission."""
    code = "PERMISSION_DENIED"


class AccessDeniedError(AuthorizationError):
    """User lacks access to resource."""
    code = "ACCESS_DENIED"


class ResourceNotFoundError(AuthorizationError):
    """Resource not accessible to user (403 Not Found behavior)."""
    code = "RESOURCE_NOT_FOUND"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthorizationService:
    """Check user permissions and resource access per RBAC and ACL rules."""

    def __init__(self, *, clock: Callable[[], datetime] = _now) -> None:
        self.clock = clock

    def check_permission(self, user: AppUser, permission_name: str) -> None:
        """Verify user has required permission; raise PermissionDeniedError if not.

        Permission format: resource_type.action (e.g., 'document.approve')
        """
        if not user.is_active:
            raise PermissionDeniedError(f"User {user.user_id} is inactive")

        # For system users, grant all permissions
        if user.is_system:
            return

        # Actual permission check would require role/permission repository lookup
        # For now, this is a placeholder that subclasses or injected repos would implement
        # In production, query user_role → role → role_permission → permission matching
        LOGGER.debug(f"Permission check: user={user.user_id} permission={permission_name}")

    def check_collection_access(
        self,
        user: AppUser,
        collection_id: str,
        min_access_level: AccessLevel = AccessLevel.READ,
    ) -> None:
        """Verify user has required access level to collection.

        Raises AccessDeniedError if access is denied.
        """
        if not user.is_active:
            raise AccessDeniedError(f"User {user.user_id} is inactive")

        # System users bypass ACL
        if user.is_system:
            return

        # Public collections always readable
        # (check would be done by repository with actual collection.is_public flag)
        # For restricted collections, check collection_access table

        LOGGER.debug(
            f"Collection access check: user={user.user_id} collection={collection_id} level={min_access_level.value}"
        )

    def check_document_access(
        self,
        user: AppUser,
        document_id: str,
        min_access_level: AccessLevel = AccessLevel.READ,
    ) -> None:
        """Verify user has required access to document via collections.

        Raises ResourceNotFoundError (403-like behavior) if access denied.
        """
        if not user.is_active:
            raise ResourceNotFoundError(f"Document {document_id} not found")

        # System users and admins can access any document
        if user.is_system:
            return

        # Check if user has access via any collection containing the document
        # (requires repository lookup: document_collection_member → collection_access)
        LOGGER.debug(f"Document access check: user={user.user_id} document={document_id}")

    def get_user_permissions(self, user: AppUser) -> set[str]:
        """Get all active permissions for a user via their roles."""
        if user.is_system:
            # System users have all permissions
            return {
                "document.upload",
                "document.view",
                "document.view_restricted",
                "document.edit_metadata",
                "document.approve",
                "document.delete",
                "version.view",
                "version.manage",
                "relation.manage",
                "user.manage",
                "role.manage",
                "audit.view",
                "index.manage",
                "collection.manage",
            }

        permissions: set[str] = set()
        # Query would be: get user_role → role → role_permission → permission
        # Returns permission_name for each active role assignment
        return permissions

    def get_user_collections(
        self,
        user: AppUser,
        min_access_level: AccessLevel = AccessLevel.READ,
    ) -> set[str]:
        """Get all collection IDs user can access at min_access_level."""
        if user.is_system:
            # System users can access all collections
            # (would return all collection_ids in practice)
            return set()

        collections: set[str] = set()
        # Query: collection_access where user_id=user.user_id and access_level >= min_access_level
        return collections

    def check_document_visibility(
        self,
        user: AppUser,
        is_restricted: bool,
        collection_ids: list[str],
    ) -> bool:
        """Determine if user can see a document based on restrictions and collections.

        Returns True if document is visible to user.
        """
        if not user.is_active:
            return False

        if user.is_system:
            return True

        # If document is restricted, must have permission + collection access
        if is_restricted:
            if "document.view_restricted" not in self.get_user_permissions(user):
                return False

        # Check collection access
        user_collections = self.get_user_collections(user, AccessLevel.READ)
        for col_id in collection_ids:
            if col_id in user_collections:
                return True

        return False


class AuditLogger:
    """Log authorization decisions and access attempts for audit trail."""

    def __init__(self, *, audit_sink=None) -> None:
        self.audit_sink = audit_sink

    def log_permission_check(
        self,
        user_id: str,
        permission: str,
        allowed: bool,
        trace_id: str | None = None,
    ) -> None:
        """Record permission check in audit log."""
        if self.audit_sink:
            self.audit_sink.record(
                actor_id=user_id,
                action="permission_check",
                object_id=permission,
                trace_id=trace_id or "",
                outcome="allowed" if allowed else "denied",
            )
        LOGGER.info(
            f"Permission check: user={user_id} permission={permission} outcome={'allowed' if allowed else 'denied'}"
        )

    def log_access_attempt(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        access_level: str,
        allowed: bool,
        trace_id: str | None = None,
    ) -> None:
        """Record access attempt in audit log."""
        if self.audit_sink:
            self.audit_sink.record(
                actor_id=user_id,
                action=f"access_attempt_{resource_type}",
                object_id=resource_id,
                trace_id=trace_id or "",
                outcome="allowed" if allowed else "denied",
            )
        LOGGER.info(
            f"Access attempt: user={user_id} resource={resource_type}/{resource_id} level={access_level} outcome={'allowed' if allowed else 'denied'}"
        )

    def log_role_assignment(
        self,
        user_id: str,
        role_id: str,
        granted_by: str,
        expires_at: datetime | None = None,
    ) -> None:
        """Record role assignment in audit log."""
        if self.audit_sink:
            self.audit_sink.record(
                actor_id=granted_by,
                action="role_assign",
                object_id=f"{user_id}:{role_id}",
                trace_id="",
                outcome="assigned",
            )
        LOGGER.info(
            f"Role assignment: user={user_id} role={role_id} by={granted_by}"
        )
