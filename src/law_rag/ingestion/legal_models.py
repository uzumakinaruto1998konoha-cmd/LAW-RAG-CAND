"""Domain models for legal metadata, structural hierarchy and relation candidates.

The parser only proposes values; every item carries provenance and confidence and
stays unverified until a reviewer records a decision (see legal_review).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NodeKind(str, Enum):
    DOCUMENT = "document"
    APPENDIX = "appendix"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"
    CLAUSE = "clause"
    POINT = "point"


LEVEL_ORDER: dict[NodeKind, int] = {
    NodeKind.DOCUMENT: 0,
    NodeKind.APPENDIX: 1,
    NodeKind.CHAPTER: 1,
    NodeKind.SECTION: 2,
    NodeKind.ARTICLE: 3,
    NodeKind.CLAUSE: 4,
    NodeKind.POINT: 5,
}


class MetadataField(str, Enum):
    DOCUMENT_TYPE = "document_type"
    TITLE = "title"
    DOCUMENT_NUMBER = "document_number"
    ISSUING_BODY = "issuing_body"
    ISSUE_DATE = "issue_date"
    EFFECTIVE_DATE = "effective_date"
    EXPIRY_DATE = "expiry_date"
    LANGUAGE = "language"
    SOURCE = "source"


REQUIRED_METADATA_FIELDS: frozenset[MetadataField] = frozenset({
    MetadataField.DOCUMENT_TYPE,
    MetadataField.DOCUMENT_NUMBER,
    MetadataField.ISSUE_DATE,
})


class RelationType(str, Enum):
    AMENDS = "amends"
    SUPPLEMENTS = "supplements"
    REPLACES = "replaces"
    REPEALS = "repeals"
    GUIDES = "guides"
    REFERENCES = "references"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a parsed value came from inside the immutable source document."""

    source_locator: str
    page_number: int | None
    method: str
    detector: str

    def __post_init__(self) -> None:
        if not self.source_locator:
            raise ValueError("Provenance requires a source locator")
        if not self.detector:
            raise ValueError("Provenance requires the detector that produced the value")


@dataclass(frozen=True, slots=True)
class MetadataAssertion:
    assertion_id: str
    field: MetadataField
    value: str
    raw_value: str
    confidence: float
    provenance: Provenance
    required: bool
    requires_verification: bool = False
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Metadata confidence must be between 0 and 1")
        if not self.raw_value.strip():
            raise ValueError("Metadata assertion requires the original source text")
        if self.verification is not VerificationStatus.UNVERIFIED and not self.reviewer_id:
            raise ValueError("Verified metadata requires a reviewer identity")

    @property
    def is_pending(self) -> bool:
        return self.requires_verification and self.verification is VerificationStatus.UNVERIFIED


@dataclass(frozen=True, slots=True)
class LegalNode:
    node_id: str
    kind: NodeKind
    label: str
    ordinal: str
    title: str | None
    content: str
    parent_id: str | None
    child_ids: tuple[str, ...]
    provenance: Provenance
    confidence: float
    page_numbers: tuple[int, ...]
    source_locators: tuple[str, ...]
    requires_verification: bool = False
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Node confidence must be between 0 and 1")
        if not self.source_locators:
            raise ValueError("Every legal node requires at least one source locator")
        if self.verification is not VerificationStatus.UNVERIFIED and not self.reviewer_id:
            raise ValueError("Verified node requires a reviewer identity")

    @property
    def level(self) -> int:
        return LEVEL_ORDER[self.kind]

    @property
    def is_pending(self) -> bool:
        return self.requires_verification and self.verification is VerificationStatus.UNVERIFIED


@dataclass(frozen=True, slots=True)
class RelationCandidate:
    """Unverified cross reference; it never changes effective status by itself."""

    relation_id: str
    relation_type: RelationType
    target_reference: str
    provenance: Provenance
    confidence: float
    source_node_id: str | None
    target_document_number: str | None = None
    target_scope_label: str | None = None
    requires_verification: bool = True
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Relation confidence must be between 0 and 1")
        if not self.target_reference.strip():
            raise ValueError("Relation candidate requires the referenced text")
        if self.verification is not VerificationStatus.UNVERIFIED and not self.reviewer_id:
            raise ValueError("Verified relation requires a reviewer identity")

    @property
    def is_pending(self) -> bool:
        return self.verification is VerificationStatus.UNVERIFIED

    @property
    def is_resolved(self) -> bool:
        """Only verified relations may target a document version or node."""
        return self.verification in (VerificationStatus.ACCEPTED, VerificationStatus.CORRECTED) and bool(
            self.target_document_number or self.target_scope_label
        )


@dataclass(frozen=True, slots=True)
class LegalParseResult:
    job_id: str
    pipeline_version: str
    parser_version: str
    parser_config_hash: str
    nodes: tuple[LegalNode, ...]
    metadata: tuple[MetadataAssertion, ...]
    relations: tuple[RelationCandidate, ...]
    warnings: tuple[str, ...]
    review_required: bool
    page_count: int | None

    def node(self, node_id: str) -> LegalNode | None:
        return next((node for node in self.nodes if node.node_id == node_id), None)

    def root_nodes(self) -> tuple[LegalNode, ...]:
        return tuple(node for node in self.nodes if node.parent_id is None)

    def nodes_of_kind(self, kind: NodeKind) -> tuple[LegalNode, ...]:
        return tuple(node for node in self.nodes if node.kind is kind)

    def metadata_for(self, field: MetadataField) -> tuple[MetadataAssertion, ...]:
        return tuple(item for item in self.metadata if item.field is field)

    def verified_metadata_value(self, field: MetadataField) -> str | None:
        for item in self.metadata:
            if item.field is field and item.verification in (
                VerificationStatus.ACCEPTED,
                VerificationStatus.CORRECTED,
            ):
                return item.value
        return None

    def pending_items(self) -> tuple[str, ...]:
        pending = [item.assertion_id for item in self.metadata if item.is_pending]
        pending.extend(node.node_id for node in self.nodes if node.is_pending)
        pending.extend(relation.relation_id for relation in self.relations if relation.is_pending)
        return tuple(pending)
