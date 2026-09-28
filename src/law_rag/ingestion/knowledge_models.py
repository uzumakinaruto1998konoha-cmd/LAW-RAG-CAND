"""Domain models for PHASE 2 knowledge model: RBAC, ACL, and temporal features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ValidityStatus(str, Enum):
    """Legal document validity status per docs/06 section 4."""
    UNKNOWN = "unknown"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    IN_FORCE = "in_force"
    PARTIALLY_EFFECTIVE = "partially_effective"
    AMENDED = "amended"
    REPEALED = "repealed"
    EXPIRED = "expired"
    CONFLICT = "conflict"


class AccessLevel(str, Enum):
    """Collection access levels for ACL."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class AppUser:
    """System user with authentication and profile."""

    user_id: str
    username: str
    email: str
    display_name: str
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    locked_until: datetime | None = None

    def __post_init__(self) -> None:
        if not self.username or len(self.username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not self.email or "@" not in self.email:
            raise ValueError("Email must be valid")

    @property
    def is_locked(self) -> bool:
        """Check if user is temporarily locked."""
        if not self.locked_until:
            return False
        return self.locked_until > datetime.now(timezone.utc)

    @classmethod
    def new(
        cls,
        *,
        user_id: str,
        username: str,
        email: str,
        display_name: str,
        is_system: bool = False,
    ) -> AppUser:
        now = datetime.now(timezone.utc)
        return cls(
            user_id=user_id,
            username=username,
            email=email,
            display_name=display_name,
            is_active=True,
            is_system=is_system,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class Role:
    """RBAC role with assigned permissions."""

    role_id: str
    role_name: str
    description: str | None
    is_system: bool
    created_at: datetime
    updated_at: datetime
    permission_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role_name not in ("system_admin", "knowledge_admin", "reviewer", "user", "auditor"):
            raise ValueError(f"Invalid role name: {self.role_name}")


@dataclass(frozen=True, slots=True)
class Permission:
    """API permission for resource/action."""

    permission_id: str
    permission_name: str
    resource_type: str
    action: str
    description: str | None


@dataclass(frozen=True, slots=True)
class UserRole:
    """User-Role assignment with temporal constraints."""

    user_id: str
    role_id: str
    granted_by: str
    granted_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.expires_at and self.expires_at <= self.granted_at:
            raise ValueError("Expiry must be after grant date")

    @property
    def is_active(self) -> bool:
        """Check if role assignment is currently active."""
        if not self.expires_at:
            return True
        return self.expires_at > datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DocumentCollection:
    """Named collection of related documents for ACL scoping."""

    collection_id: str
    collection_name: str
    description: str | None
    is_public: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.collection_name or len(self.collection_name) < 1:
            raise ValueError("Collection name required")

    @classmethod
    def new(
        cls,
        *,
        collection_id: str,
        collection_name: str,
        description: str | None,
        is_public: bool,
        created_by: str,
    ) -> DocumentCollection:
        now = datetime.now(timezone.utc)
        return cls(
            collection_id=collection_id,
            collection_name=collection_name,
            description=description,
            is_public=is_public,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class CollectionAccess:
    """User access to a restricted collection."""

    collection_id: str
    user_id: str
    access_level: AccessLevel
    granted_by: str
    granted_at: datetime

    def __post_init__(self) -> None:
        if self.access_level not in AccessLevel:
            raise ValueError(f"Invalid access level: {self.access_level}")


@dataclass(frozen=True, slots=True)
class UserSession:
    """Authenticated user session."""

    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    is_revoked: bool = False

    def __post_init__(self) -> None:
        if self.expires_at <= self.created_at:
            raise ValueError("Session expiry must be after creation")

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if session is currently valid."""
        return not self.is_revoked and not self.is_expired

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
        created_at: datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        return cls(
            session_id=session_id,
            user_id=user_id,
            # Creation time is injectable so callers (and tests) can pin a clock
            # instead of mixing a real "now" with an explicit expiry.
            created_at=created_at or datetime.now(timezone.utc),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )


@dataclass(frozen=True, slots=True)
class PasswordResetToken:
    """Temporary token for password reset flow."""

    token_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.expires_at <= self.created_at:
            raise ValueError("Expiry must be after creation")

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid for use."""
        return not self.is_expired and not self.is_used

    @classmethod
    def new(
        cls,
        *,
        token_id: str,
        user_id: str,
        expires_in_hours: int = 1,
    ) -> PasswordResetToken:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires_at = now + timedelta(hours=expires_in_hours)
        return cls(
            token_id=token_id,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
        )
