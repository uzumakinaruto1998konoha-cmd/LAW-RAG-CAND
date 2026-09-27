-- PHASE 2 Knowledge Model: ACL (RBAC), effective dates, and user management
-- Migration 0004: Complete knowledge model with RBAC and temporal features

-- ============================================
-- USER AND AUTHENTICATION
-- ============================================

CREATE TABLE IF NOT EXISTS app_user (
    user_id text PRIMARY KEY,
    username varchar(128) NOT NULL UNIQUE,
    email varchar(255) NOT NULL UNIQUE,
    display_name varchar(255) NOT NULL,
    password_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    is_system boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    last_login_at timestamptz,
    locked_until timestamptz,
    CHECK (username ~* '^[a-zA-Z][a-zA-Z0-9_]{2,127}$')
);

CREATE INDEX IF NOT EXISTS app_user_username_idx ON app_user (username);
CREATE INDEX IF NOT EXISTS app_user_email_idx ON app_user (email);
CREATE INDEX IF NOT EXISTS app_user_active_idx ON app_user (is_active) WHERE is_active = true;

-- ============================================
-- ROLES AND PERMISSIONS (RBAC)
-- ============================================

CREATE TABLE IF NOT EXISTS role (
    role_id text PRIMARY KEY,
    role_name varchar(64) NOT NULL UNIQUE,
    description text,
    is_system boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT role_name_check CHECK (
        role_name IN ('system_admin', 'knowledge_admin', 'reviewer', 'user', 'auditor')
    )
);

CREATE TABLE IF NOT EXISTS permission (
    permission_id text PRIMARY KEY,
    permission_name varchar(64) NOT NULL UNIQUE,
    resource_type varchar(32) NOT NULL,
    action varchar(32) NOT NULL,
    description text,
    CONSTRAINT permission_unique UNIQUE (resource_type, action)
);

-- Default permissions per docs/10_SECURITY_SPECIFICATION.md section 2
INSERT INTO permission (permission_id, permission_name, resource_type, action, description) VALUES
    ('perm_doc_upload', 'document.upload', 'document', 'upload', 'Upload new documents'),
    ('perm_doc_view', 'document.view', 'document', 'view', 'View document metadata and content'),
    ('perm_doc_view_restricted', 'document.view_restricted', 'document', 'view_restricted', 'View restricted documents'),
    ('perm_doc_edit_metadata', 'document.edit_metadata', 'document', 'edit_metadata', 'Edit document metadata'),
    ('perm_doc_approve', 'document.approve', 'document', 'approve', 'Approve and release documents'),
    ('perm_doc_delete', 'document.delete', 'document', 'delete', 'Delete/archive documents'),
    ('perm_version_view', 'version.view', 'version', 'view', 'View document versions'),
    ('perm_version_manage', 'version.manage', 'version', 'manage', 'Manage version lifecycle'),
    ('perm_relation_manage', 'relation.manage', 'relation', 'manage', 'Manage document relations'),
    ('perm_user_manage', 'user.manage', 'user', 'manage', 'Create/modify users'),
    ('perm_role_manage', 'role.manage', 'role', 'manage', 'Manage roles and permissions'),
    ('perm_audit_view', 'audit.view', 'audit', 'view', 'View audit events'),
    ('perm_index_manage', 'index.manage', 'index', 'manage', 'Manage search index'),
    ('perm_collection_manage', 'collection.manage', 'collection', 'manage', 'Manage document collections')
ON CONFLICT DO NOTHING;

-- Default roles per docs/10_SECURITY_SPECIFICATION.md section 2
INSERT INTO role (role_id, role_name, description, is_system) VALUES
    ('role_system_admin', 'system_admin', 'Full system administration access', true),
    ('role_knowledge_admin', 'knowledge_admin', 'Knowledge base management and approval', true),
    ('role_reviewer', 'reviewer', 'Review and approve documents', true),
    ('role_user', 'user', 'Standard user access', true),
    ('role_auditor', 'auditor', 'Read-only audit access', true)
ON CONFLICT DO NOTHING;

-- Role-Permission assignments (default per spec)
INSERT INTO role_permission (role_id, permission_id) VALUES
    -- System Admin: all permissions
    ('role_system_admin', 'perm_doc_upload'), ('role_system_admin', 'perm_doc_view'),
    ('role_system_admin', 'perm_doc_view_restricted'), ('role_system_admin', 'perm_doc_edit_metadata'),
    ('role_system_admin', 'perm_doc_approve'), ('role_system_admin', 'perm_doc_delete'),
    ('role_system_admin', 'perm_version_view'), ('role_system_admin', 'perm_version_manage'),
    ('role_system_admin', 'perm_relation_manage'), ('role_system_admin', 'perm_user_manage'),
    ('role_system_admin', 'perm_role_manage'), ('role_system_admin', 'perm_audit_view'),
    ('role_system_admin', 'perm_index_manage'), ('role_system_admin', 'perm_collection_manage'),
    -- Knowledge Admin: document management + index
    ('role_knowledge_admin', 'perm_doc_upload'), ('role_knowledge_admin', 'perm_doc_view'),
    ('role_knowledge_admin', 'perm_doc_view_restricted'), ('role_knowledge_admin', 'perm_doc_edit_metadata'),
    ('role_knowledge_admin', 'perm_doc_approve'), ('role_knowledge_admin', 'perm_version_view'),
    ('role_knowledge_admin', 'perm_version_manage'), ('role_knowledge_admin', 'perm_relation_manage'),
    ('role_knowledge_admin', 'perm_audit_view'), ('role_knowledge_admin', 'perm_index_manage'),
    ('role_knowledge_admin', 'perm_collection_manage'),
    -- Reviewer: view + approve
    ('role_reviewer', 'perm_doc_view'), ('role_reviewer', 'perm_doc_approve'),
    ('role_reviewer', 'perm_version_view'), ('role_reviewer', 'perm_audit_view'),
    -- User: basic access
    ('role_user', 'perm_doc_view'), ('role_user', 'perm_version_view'),
    -- Auditor: read-only audit
    ('role_auditor', 'perm_audit_view')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS user_role (
    user_id text NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    role_id text NOT NULL REFERENCES role(role_id) ON DELETE CASCADE,
    granted_by text REFERENCES app_user(user_id),
    granted_at timestamptz NOT NULL,
    expires_at timestamptz,
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS user_role_user_idx ON user_role (user_id);
CREATE INDEX IF NOT EXISTS user_role_role_idx ON user_role (role_id);
CREATE INDEX IF NOT EXISTS user_role_expires_idx ON user_role (expires_at) WHERE expires_at IS NOT NULL;

-- ============================================
-- DOCUMENT COLLECTIONS (for ACL scoping)
-- ============================================

CREATE TABLE IF NOT EXISTS document_collection (
    collection_id text PRIMARY KEY,
    collection_name varchar(128) NOT NULL UNIQUE,
    description text,
    is_public boolean NOT NULL DEFAULT true,
    created_by text NOT NULL REFERENCES app_user(user_id),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS document_collection_name_idx ON document_collection (collection_name);

-- Collection-User access (for restricted collections)
CREATE TABLE IF NOT EXISTS collection_access (
    collection_id text NOT NULL REFERENCES document_collection(collection_id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    access_level varchar(16) NOT NULL CHECK (access_level IN ('read', 'write', 'admin')),
    granted_by text REFERENCES app_user(user_id),
    granted_at timestamptz NOT NULL,
    PRIMARY KEY (collection_id, user_id),
    CHECK (access_level IN ('read', 'write', 'admin'))
);

-- ============================================
-- DOCUMENT-COLLECTION MAPPING
-- ============================================

CREATE TABLE IF NOT EXISTS document_collection_member (
    document_id text NOT NULL REFERENCES document(document_id) ON DELETE CASCADE,
    collection_id text NOT NULL REFERENCES document_collection(collection_id) ON DELETE CASCADE,
    added_by text NOT NULL REFERENCES app_user(user_id),
    added_at timestamptz NOT NULL,
    PRIMARY KEY (document_id, collection_id)
);

CREATE INDEX IF NOT EXISTS document_collection_member_doc_idx ON document_collection_member (document_id);
CREATE INDEX IF NOT EXISTS document_collection_member_coll_idx ON document_collection_member (collection_id);

-- ============================================
-- EFFECTIVE DATE LOGIC
-- ============================================

-- Add validity status to document_version if not exists (from PHASE 1 migration 0003)
-- Already have effective_date and expiry_date, now add computed status tracking

ALTER TABLE document_version ADD COLUMN IF NOT EXISTS validity_status varchar(32) NOT NULL DEFAULT 'unknown';
ALTER TABLE document_version ADD COLUMN IF NOT EXISTS validity_checked_at timestamptz;

-- Validity status enum: UNKNOWN, NOT_YET_EFFECTIVE, IN_FORCE, PARTIALLY_EFFECTIVE, AMENDED, REPEALED, EXPIRED, CONFLICT
-- Per docs/06 section 4

CREATE INDEX IF NOT EXISTS document_version_validity_idx ON document_version (validity_status, effective_date, expiry_date) 
    WHERE validity_status IN ('in_force', 'partially_effective', 'not_yet_effective');

-- ============================================
-- SESSION MANAGEMENT
-- ============================================

CREATE TABLE IF NOT EXISTS user_session (
    session_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    refresh_token_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    last_used_at timestamptz,
    ip_address inet,
    user_agent text,
    is_revoked boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS user_session_user_idx ON user_session (user_id, expires_at) WHERE is_revoked = false;
CREATE INDEX IF NOT EXISTS user_session_expires_idx ON user_session (expires_at) WHERE is_revoked = false;

-- ============================================
-- PASSWORD RESET TOKENS
-- ============================================

CREATE TABLE IF NOT EXISTS password_reset_token (
    token_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    token_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    used_at timestamptz
);

CREATE INDEX IF NOT EXISTS password_reset_token_user_idx ON password_reset_token (user_id, used_at) WHERE used_at IS NULL;