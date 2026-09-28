"""Deployment bootstrap: wire identity, ACL, ingestion and the pipeline.

Configuration comes from a JSON file (path in ``LAW_RAG_CONFIG_FILE``) so that no
user, collection or credential is ever hard-coded in the source (AGENTS.md section 5,
docs/10). Tokens are read from the environment variable named by each user entry
(``token_env``); when that variable is empty a token is generated at start-up and
printed once to stdout so the operator can hand it to the user.

Environment variables:
- ``LAW_RAG_CONFIG_FILE``: JSON bootstrap file (see ``load_config_file``).
- ``LAW_RAG_BLOB_DIR``: filesystem location for immutable upload blobs.
- ``LAW_RAG_OCR_ENABLED``: ``1`` enables the local Tesseract OCR engine.
- ``LAW_RAG_TESSERACT_CMD`` / ``LAW_RAG_OCR_LANGUAGE``: OCR binary and language.

The default adapters are process-local (in-memory jobs, parse results and knowledge
base) with blobs on disk: the local deployment profile of ADR-003/ADR-013. Wiring
PostgreSQL and Qdrant replaces these adapters without changing this module's API.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from law_rag.ingestion.knowledge_models import AccessLevel, AppUser, DocumentCollection
from law_rag.ingestion.memory import (
    InMemoryAuditSink,
    InMemoryJobRepository,
    InMemoryKnowledgeBaseRepository,
    InMemoryLegalParseRepository,
)
from law_rag.ingestion.ocr import OCRProcessor, TesseractOCR
from law_rag.ingestion.pipeline import IngestionPipeline
from law_rag.ingestion.service import IngestionService
from law_rag.ingestion.storage import FileBlobStore
from law_rag.retrieval.models import Chunk
from law_rag.retrieval.search import DocumentMetadata

from .container import ApiContainer
from .security import RbacPolicy

LOGGER = logging.getLogger(__name__)

DEFAULT_BLOB_DIR = "data/blobs"
ARCHITECTURE_VERSION = "1.2-ingestion-pipeline"


@dataclass(frozen=True, slots=True)
class BootstrapUser:
    user_id: str
    username: str
    email: str
    display_name: str
    roles: tuple[str, ...] = ()
    token_env: str | None = None
    is_system: bool = False


@dataclass(frozen=True, slots=True)
class BootstrapCollection:
    collection_id: str
    name: str
    description: str | None = None
    is_public: bool = False


@dataclass(frozen=True, slots=True)
class BootstrapGrant:
    user_id: str
    collection_id: str
    access_level: str = "read"


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    users: tuple[BootstrapUser, ...] = ()
    collections: tuple[BootstrapCollection, ...] = ()
    grants: tuple[BootstrapGrant, ...] = ()
    blob_dir: str = DEFAULT_BLOB_DIR
    ocr_enabled: bool = False
    tesseract_executable: str = "tesseract"
    ocr_language: str = "vie"
    role_permissions: Mapping[str, Sequence[str]] | None = None


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    container: ApiContainer
    tokens: Mapping[str, str]
    generated_token_users: tuple[str, ...] = field(default_factory=tuple)


def _parse_access_level(value: str) -> AccessLevel:
    try:
        return AccessLevel(value)
    except ValueError as exc:
        raise ValueError(f"Unknown access level: {value}") from exc


def parse_config(payload: Mapping[str, object]) -> BootstrapConfig:
    """Validate a bootstrap mapping; unknown roles or dangling grants are rejected."""
    users = tuple(
        BootstrapUser(
            user_id=str(entry["user_id"]),
            username=str(entry["username"]),
            email=str(entry.get("email", f"{entry['username']}@example.invalid")),
            display_name=str(entry.get("display_name", entry["username"])),
            roles=tuple(str(role) for role in entry.get("roles", ())),
            token_env=str(entry["token_env"]) if entry.get("token_env") else None,
            is_system=bool(entry.get("is_system", False)),
        )
        for entry in payload.get("users", ())  # type: ignore[union-attr]
    )
    collections = tuple(
        BootstrapCollection(
            collection_id=str(entry["collection_id"]),
            name=str(entry["name"]),
            description=str(entry["description"]) if entry.get("description") else None,
            is_public=bool(entry.get("is_public", False)),
        )
        for entry in payload.get("collections", ())  # type: ignore[union-attr]
    )
    grants = tuple(
        BootstrapGrant(
            user_id=str(entry["user_id"]),
            collection_id=str(entry["collection_id"]),
            access_level=str(entry.get("access_level", "read")),
        )
        for entry in payload.get("grants", ())  # type: ignore[union-attr]
    )
    config = BootstrapConfig(
        users=users,
        collections=collections,
        grants=grants,
        blob_dir=str(payload.get("blob_dir", DEFAULT_BLOB_DIR)),
        ocr_enabled=bool(payload.get("ocr_enabled", False)),
        tesseract_executable=str(payload.get("tesseract_executable", "tesseract")),
        ocr_language=str(payload.get("ocr_language", "vie")),
    )
    _validate(config)
    return config


def _validate(config: BootstrapConfig) -> None:
    user_ids = [user.user_id for user in config.users]
    if len(set(user_ids)) != len(user_ids):
        raise ValueError("Bootstrap users must have unique user_id values")
    collection_ids = [collection.collection_id for collection in config.collections]
    if len(set(collection_ids)) != len(collection_ids):
        raise ValueError("Bootstrap collections must have unique collection_id values")
    rbac = RbacPolicy(role_permissions=config.role_permissions)
    for user in config.users:
        for role in user.roles:
            if not rbac.known_role(role):
                raise ValueError(f"Unknown role for user {user.user_id}: {role}")
    known_users = set(user_ids)
    known_collections = set(collection_ids)
    for grant in config.grants:
        if grant.user_id not in known_users:
            raise ValueError(f"Grant references an unknown user: {grant.user_id}")
        if grant.collection_id not in known_collections:
            raise ValueError(f"Grant references an unknown collection: {grant.collection_id}")
        _parse_access_level(grant.access_level)


def load_config_file(path: str | Path) -> BootstrapConfig:
    """Read and validate a JSON bootstrap file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Bootstrap file must contain a JSON object")
    return parse_config(payload)


def config_from_env(environ: Mapping[str, str] | None = None) -> BootstrapConfig | None:
    """Build the bootstrap config from the environment, or None when unset."""
    env = environ if environ is not None else os.environ
    config_file = env.get("LAW_RAG_CONFIG_FILE")
    if not config_file:
        return None
    config = load_config_file(config_file)
    overrides = {
        "blob_dir": env.get("LAW_RAG_BLOB_DIR"),
        "ocr_enabled": _env_flag(env.get("LAW_RAG_OCR_ENABLED")),
        "tesseract_executable": env.get("LAW_RAG_TESSERACT_CMD"),
        "ocr_language": env.get("LAW_RAG_OCR_LANGUAGE"),
    }
    return BootstrapConfig(
        users=config.users,
        collections=config.collections,
        grants=config.grants,
        blob_dir=overrides["blob_dir"] or config.blob_dir,
        ocr_enabled=config.ocr_enabled if overrides["ocr_enabled"] is None else overrides["ocr_enabled"],
        tesseract_executable=overrides["tesseract_executable"] or config.tesseract_executable,
        ocr_language=overrides["ocr_language"] or config.ocr_language,
        role_permissions=config.role_permissions,
    )


def _env_flag(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_ocr(config: BootstrapConfig) -> OCRProcessor | None:
    """Build the local OCR engine when enabled; extraction degrades to review without it."""
    if not config.ocr_enabled:
        return None
    return TesseractOCR(executable=config.tesseract_executable, language=config.ocr_language)


def build_container(
    config: BootstrapConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> BootstrapResult:
    """Create a fully wired container for the given bootstrap config."""
    env = environ if environ is not None else os.environ
    rbac = RbacPolicy(role_permissions=config.role_permissions)
    container = ApiContainer(rbac=rbac, architecture_version=ARCHITECTURE_VERSION)

    now = datetime.now(timezone.utc)
    tokens: dict[str, str] = {}
    generated: list[str] = []
    for entry in config.users:
        user = AppUser(
            user_id=entry.user_id,
            username=entry.username,
            email=entry.email,
            display_name=entry.display_name,
            is_active=True,
            is_system=entry.is_system,
            created_at=now,
            updated_at=now,
        )
        container.register_user(user)
        for role in entry.roles:
            container.assign_role(user_id=entry.user_id, role_name=role)
        token = env.get(entry.token_env) if entry.token_env else None
        if not token:
            token = secrets.token_urlsafe(32)
            generated.append(entry.user_id)
        container.register_token(user_id=entry.user_id, token=token)
        tokens[entry.user_id] = token

    created_by = config.users[0].user_id if config.users else "bootstrap"
    for collection in config.collections:
        container.register_collection(
            collection_id=collection.collection_id,
            collection_name=collection.name,
            description=collection.description,
            is_public=collection.is_public,
            created_by=created_by,
        )
    for grant in config.grants:
        container.grant_collection_access(
            user_id=grant.user_id,
            collection_id=grant.collection_id,
            access_level=_parse_access_level(grant.access_level),
            granted_by=created_by,
        )

    blob_store = FileBlobStore(Path(config.blob_dir))
    job_repository = InMemoryJobRepository()
    legal_repository = InMemoryLegalParseRepository()
    kb_repository = InMemoryKnowledgeBaseRepository()
    audit = InMemoryAuditSink()
    ingestion_service = IngestionService(
        repository=job_repository, blob_store=blob_store, audit=audit
    )

    def index_writer(
        *, version_id: str, metadata: DocumentMetadata, chunks: Sequence[Chunk]
    ) -> None:
        for chunk in chunks:
            container.retrieval.index_chunk(chunk, metadata)

    pipeline = IngestionPipeline(
        ingestion_service=ingestion_service,
        blob_store=blob_store,
        job_repository=job_repository,
        legal_repository=legal_repository,
        kb_repository=kb_repository,
        audit=audit,
        index_writer=index_writer,
        ocr=build_ocr(config),
    )
    container.ingestion_service = ingestion_service
    container.pipeline = pipeline
    container.kb_repository = kb_repository
    container.legal_repository = legal_repository
    # Exposed so audit-facing endpoints and tests can read the recorded events.
    container.audit = audit

    if not config.users:
        LOGGER.warning("Bootstrap config has no users: the API will reject every request")
    if config.users and not config.collections:
        LOGGER.warning(
            "Bootstrap config has no collections: approved documents cannot be released"
        )
    LOGGER.info(
        "Bootstrap ready users=%d collections=%d grants=%d blob_dir=%s ocr=%s",
        len(config.users),
        len(config.collections),
        len(config.grants),
        config.blob_dir,
        config.ocr_enabled,
    )
    return BootstrapResult(container=container, tokens=tokens, generated_token_users=tuple(generated))


def print_generated_tokens(result: BootstrapResult) -> None:
    """Print tokens that were generated at start-up (they are not logged elsewhere)."""
    if not result.generated_token_users:
        return
    print("=" * 72)
    print("Generated bearer tokens (store them now; they are not recoverable):")
    for user_id in result.generated_token_users:
        print(f"  {user_id}: {result.tokens[user_id]}")
    print("Set LAW_RAG_TOKEN_* environment variables to keep tokens stable.")
    print("=" * 72)
