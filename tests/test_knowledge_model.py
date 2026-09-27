"""Unit tests for PHASE 2 knowledge model: RBAC, ACL, and temporal features."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from law_rag.ingestion.authorization import (
    AccessDeniedError,
    AuthorizationError,
    AuthorizationService,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from law_rag.ingestion.knowledge_models import (
    AccessLevel,
    AppUser,
    CollectionAccess,
    DocumentCollection,
    PasswordResetToken,
    Role,
    UserRole,
    UserSession,
    ValidityStatus,
)

NOW = datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc)


class AppUserTests(unittest.TestCase):
    def test_requires_valid_username(self) -> None:
        with self.assertRaises(ValueError):
            AppUser.new(
                user_id="u1",
                username="ab",
                email="test@example.com",
                display_name="Test User",
            )

    def test_requires_valid_email(self) -> None:
        with self.assertRaises(ValueError):
            AppUser.new(
                user_id="u1",
                username="testuser",
                email="invalid-email",
                display_name="Test User",
            )

    def test_creates_active_user(self) -> None:
        user = AppUser.new(
            user_id="u1",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
        )

        self.assertTrue(user.is_active)
        self.assertFalse(user.is_system)
        self.assertIsNotNone(user.created_at)

    def test_locked_user_property(self) -> None:
        locked_until = NOW + timedelta(hours=1)
        user = AppUser(
            user_id="u1",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            is_active=True,
            is_system=False,
            created_at=NOW,
            updated_at=NOW,
            locked_until=locked_until,
        )

        self.assertTrue(user.is_locked)


class RoleTests(unittest.TestCase):
    def test_requires_valid_role_name(self) -> None:
        with self.assertRaises(ValueError):
            Role(
                role_id="r1",
                role_name="invalid_role",
                description=None,
                is_system=False,
                created_at=NOW,
                updated_at=NOW,
            )

    def test_creates_system_admin_role(self) -> None:
        role = Role(
            role_id="r1",
            role_name="system_admin",
            description="Full system access",
            is_system=True,
            created_at=NOW,
            updated_at=NOW,
            permission_ids=(
                "perm_doc_upload",
                "perm_doc_approve",
                "perm_user_manage",
            ),
        )

        self.assertEqual(role.role_name, "system_admin")
        self.assertTrue(role.is_system)
        self.assertEqual(len(role.permission_ids), 3)


class UserRoleTests(unittest.TestCase):
    def test_role_expiry_must_be_after_grant(self) -> None:
        with self.assertRaises(ValueError):
            UserRole(
                user_id="u1",
                role_id="r1",
                granted_by="admin",
                granted_at=NOW,
                expires_at=NOW - timedelta(hours=1),
            )

    def test_active_role_without_expiry(self) -> None:
        user_role = UserRole(
            user_id="u1",
            role_id="r1",
            granted_by="admin",
            granted_at=NOW,
        )

        self.assertTrue(user_role.is_active)

    def test_active_role_with_future_expiry(self) -> None:
        user_role = UserRole(
            user_id="u1",
            role_id="r1",
            granted_by="admin",
            granted_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )

        self.assertTrue(user_role.is_active)

    def test_inactive_role_after_expiry(self) -> None:
        user_role = UserRole(
            user_id="u1",
            role_id="r1",
            granted_by="admin",
            granted_at=NOW - timedelta(days=31),
            expires_at=NOW - timedelta(days=1),
        )

        self.assertFalse(user_role.is_active)


class DocumentCollectionTests(unittest.TestCase):
    def test_requires_collection_name(self) -> None:
        with self.assertRaises(ValueError):
            DocumentCollection.new(
                collection_id="c1",
                collection_name="",
                description=None,
                is_public=True,
                created_by="user1",
            )

    def test_creates_public_collection(self) -> None:
        collection = DocumentCollection.new(
            collection_id="c1",
            collection_name="Public Documents",
            description="Publicly accessible documents",
            is_public=True,
            created_by="user1",
        )

        self.assertTrue(collection.is_public)
        self.assertEqual(collection.collection_name, "Public Documents")

    def test_creates_restricted_collection(self) -> None:
        collection = DocumentCollection.new(
            collection_id="c2",
            collection_name="Confidential",
            description="Restricted access documents",
            is_public=False,
            created_by="admin",
        )

        self.assertFalse(collection.is_public)


class CollectionAccessTests(unittest.TestCase):
    def test_requires_valid_access_level(self) -> None:
        with self.assertRaises(ValueError):
            CollectionAccess(
                collection_id="c1",
                user_id="u1",
                access_level="invalid",  # type: ignore
                granted_by="admin",
                granted_at=NOW,
            )

    def test_creates_read_access(self) -> None:
        access = CollectionAccess(
            collection_id="c1",
            user_id="u1",
            access_level=AccessLevel.READ,
            granted_by="admin",
            granted_at=NOW,
        )

        self.assertEqual(access.access_level, AccessLevel.READ)


class UserSessionTests(unittest.TestCase):
    def test_requires_expiry_after_creation(self) -> None:
        with self.assertRaises(ValueError):
            UserSession(
                session_id="s1",
                user_id="u1",
                created_at=NOW,
                expires_at=NOW - timedelta(hours=1),
            )

    def test_new_session_is_valid(self) -> None:
        session = UserSession.new(
            session_id="s1",
            user_id="u1",
            expires_at=NOW + timedelta(hours=8),
        )

        self.assertTrue(session.is_valid)
        self.assertFalse(session.is_expired)

    def test_revoked_session_is_invalid(self) -> None:
        session = UserSession.new(
            session_id="s1",
            user_id="u1",
            expires_at=NOW + timedelta(hours=8),
        )

        from dataclasses import replace
        revoked = replace(session, is_revoked=True)
        self.assertFalse(revoked.is_valid)


class PasswordResetTokenTests(unittest.TestCase):
    def test_new_token_is_valid(self) -> None:
        token = PasswordResetToken.new(
            token_id="t1",
            user_id="u1",
            expires_in_hours=1,
        )

        self.assertFalse(token.is_expired)
        self.assertFalse(token.is_used)
        self.assertTrue(token.is_valid)

    def test_used_token_is_invalid(self) -> None:
        token = PasswordResetToken.new(
            token_id="t1",
            user_id="u1",
            expires_in_hours=1,
        )

        from dataclasses import replace
        used = replace(token, used_at=NOW)
        self.assertFalse(used.is_valid)

    def test_expired_token_is_invalid(self) -> None:
        past = NOW - timedelta(hours=2)
        token = PasswordResetToken(
            token_id="t1",
            user_id="u1",
            created_at=past,
            expires_at=NOW - timedelta(hours=1),
        )

        self.assertTrue(token.is_expired)
        self.assertFalse(token.is_valid)


class AuthorizationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AuthorizationService(clock=lambda: NOW)

    def test_system_user_passes_permission_check(self) -> None:
        user = AppUser(
            user_id="u1",
            username="sysadmin",
            email="admin@example.com",
            display_name="System Admin",
            is_active=True,
            is_system=True,
            created_at=NOW,
            updated_at=NOW,
        )

        # Should not raise
        self.service.check_permission(user, "document.approve")

    def test_inactive_user_fails_permission_check(self) -> None:
        user = AppUser(
            user_id="u1",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            is_active=False,
            is_system=False,
            created_at=NOW,
            updated_at=NOW,
        )

        with self.assertRaises(PermissionDeniedError):
            self.service.check_permission(user, "document.view")

    def test_system_user_passes_collection_access_check(self) -> None:
        user = AppUser(
            user_id="u1",
            username="sysadmin",
            email="admin@example.com",
            display_name="System Admin",
            is_active=True,
            is_system=True,
            created_at=NOW,
            updated_at=NOW,
        )

        # Should not raise
        self.service.check_collection_access(user, "c1", AccessLevel.ADMIN)

    def test_inactive_user_fails_document_access_check(self) -> None:
        user = AppUser(
            user_id="u1",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            is_active=False,
            is_system=False,
            created_at=NOW,
            updated_at=NOW,
        )

        with self.assertRaises(ResourceNotFoundError):
            self.service.check_document_access(user, "doc1")

    def test_system_user_gets_all_permissions(self) -> None:
        user = AppUser(
            user_id="u1",
            username="sysadmin",
            email="admin@example.com",
            display_name="System Admin",
            is_active=True,
            is_system=True,
            created_at=NOW,
            updated_at=NOW,
        )

        permissions = self.service.get_user_permissions(user)
        self.assertIn("document.upload", permissions)
        self.assertIn("document.approve", permissions)
        self.assertIn("role.manage", permissions)


class ValidityStatusTests(unittest.TestCase):
    def test_validity_status_enum(self) -> None:
        self.assertEqual(ValidityStatus.UNKNOWN.value, "unknown")
        self.assertEqual(ValidityStatus.IN_FORCE.value, "in_force")
        self.assertEqual(ValidityStatus.REPEALED.value, "repealed")


if __name__ == "__main__":
    unittest.main()
