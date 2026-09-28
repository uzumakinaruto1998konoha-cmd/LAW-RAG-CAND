"""Manual review workflow for parsed legal documents.

Only a reviewed and explicitly approved parse may be released to retrieval
(docs/05 section 2 step 7-8). Confidence never approves a document by itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Callable, Sequence

from .errors import ReviewIncompleteError, ReviewItemNotFoundError
from .legal_models import (
    LegalNode,
    LegalParseResult,
    MetadataAssertion,
    RelationCandidate,
    VerificationStatus,
)

if TYPE_CHECKING:
    from .repository import AuditSink, LegalParseRepository

LOGGER = logging.getLogger(__name__)


class ReviewItemKind(str, Enum):
    METADATA = "metadata"
    NODE = "node"
    RELATION = "relation"
    WARNING = "warning"


class ReviewAction(str, Enum):
    ACCEPT = "accept"
    CORRECT = "correct"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    item_kind: ReviewItemKind
    item_id: str
    action: ReviewAction
    reviewer_id: str
    value: str | None = None
    target_document_number: str | None = None
    target_scope_label: str | None = None
    comment: str | None = None

    def __post_init__(self) -> None:
        if not self.reviewer_id.strip():
            raise ValueError("Review decisions require a reviewer identity")
        if self.action is ReviewAction.CORRECT and not (self.value or "").strip():
            raise ValueError("A correction requires the corrected value")
        if self.item_kind is ReviewItemKind.RELATION and self.action is not ReviewAction.REJECT:
            if not (self.target_document_number or self.target_scope_label):
                raise ValueError("Accepted relations must reference a target document number or scope label")

    @property
    def verification(self) -> VerificationStatus:
        if self.action is ReviewAction.ACCEPT:
            return VerificationStatus.ACCEPTED
        if self.action is ReviewAction.CORRECT:
            return VerificationStatus.CORRECTED
        return VerificationStatus.REJECTED


@dataclass(frozen=True, slots=True)
class ReviewTask:
    item_kind: ReviewItemKind
    item_id: str
    summary: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ApprovedLegalDocument:
    job_id: str
    parse_result: LegalParseResult
    approved_by: str
    approved_at: datetime
    acknowledged_warnings: tuple[str, ...]

    @property
    def retrievable(self) -> bool:
        return True

    def blocking_warnings(self) -> tuple[str, ...]:
        return self.acknowledged_warnings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def pending_tasks(result: LegalParseResult) -> tuple[ReviewTask, ...]:
    """Items a reviewer must resolve before the document can be approved."""
    tasks: list[ReviewTask] = [
        ReviewTask(ReviewItemKind.METADATA, item.assertion_id, f"{item.field.value}={item.value}", item.confidence)
        for item in result.metadata if item.is_pending
    ]
    tasks.extend(
        ReviewTask(ReviewItemKind.NODE, node.node_id, f"{node.kind.value} {node.ordinal} {node.title or ''}".strip(), node.confidence)
        for node in result.nodes if node.is_pending
    )
    tasks.extend(
        ReviewTask(ReviewItemKind.RELATION, relation.relation_id, f"{relation.relation_type.value} -> {relation.target_reference}", relation.confidence)
        for relation in result.relations if relation.is_pending
    )
    tasks.extend(ReviewTask(ReviewItemKind.WARNING, warning, warning) for warning in result.warnings)
    return tuple(tasks)


def apply_decisions(
    result: LegalParseResult,
    decisions: Sequence[ReviewDecision],
    *,
    now: datetime,
) -> LegalParseResult:
    """Return a new parse result with reviewer decisions recorded."""
    metadata: list[MetadataAssertion] = list(result.metadata)
    nodes: list[LegalNode] = list(result.nodes)
    relations: list[RelationCandidate] = list(result.relations)
    node_index = {node.node_id: position for position, node in enumerate(nodes)}
    rejected_nodes: set[str] = set()
    for decision in decisions:
        if decision.item_kind is ReviewItemKind.METADATA:
            position = _locate(metadata, decision.item_id, lambda item: item.assertion_id)
            current = metadata[position]
            metadata[position] = replace(
                current,
                value=decision.value if decision.action is ReviewAction.CORRECT and decision.value else current.value,
                verification=decision.verification,
                requires_verification=False,
                reviewer_id=decision.reviewer_id,
                reviewed_at=now,
            )
        elif decision.item_kind is ReviewItemKind.NODE:
            position = _locate_node(nodes, node_index, decision.item_id)
            current = nodes[position]
            if decision.action is ReviewAction.REJECT:
                rejected_nodes.add(decision.item_id)
                nodes[position] = replace(
                    current, verification=VerificationStatus.REJECTED, requires_verification=False,
                    reviewer_id=decision.reviewer_id, reviewed_at=now,
                )
            else:
                nodes[position] = replace(
                    current,
                    title=decision.value if decision.action is ReviewAction.CORRECT and decision.value else current.title,
                    verification=decision.verification,
                    requires_verification=False,
                    reviewer_id=decision.reviewer_id,
                    reviewed_at=now,
                )
        elif decision.item_kind is ReviewItemKind.RELATION:
            position = _locate(relations, decision.item_id, lambda item: item.relation_id)
            current = relations[position]
            relations[position] = replace(
                current,
                target_reference=decision.value if decision.action is ReviewAction.CORRECT and decision.value else current.target_reference,
                target_document_number=decision.target_document_number or current.target_document_number,
                target_scope_label=decision.target_scope_label or current.target_scope_label,
                verification=decision.verification,
                requires_verification=False,
                reviewer_id=decision.reviewer_id,
                reviewed_at=now,
            )
        else:
            raise ReviewItemNotFoundError("Warnings are acknowledged during approval, not decided individually")
    if rejected_nodes:
        kept = [node for node in nodes if node.node_id not in rejected_nodes]
        kept_ids = {node.node_id for node in kept}
        nodes = [replace(node, child_ids=tuple(child for child in node.child_ids if child in kept_ids)) for node in kept]
    return replace(result, nodes=tuple(nodes), metadata=tuple(metadata), relations=tuple(relations))


def _locate(items: Sequence[object], item_id: str, key: Callable[[object], str]) -> int:
    for position, item in enumerate(items):
        if key(item) == item_id:
            return position
    raise ReviewItemNotFoundError("Review item was not found in the parse result")


def _locate_node(nodes: Sequence[LegalNode], node_index: dict[str, int], node_id: str) -> int:
    if node_id not in node_index:
        raise ReviewItemNotFoundError("Review item was not found in the parse result")
    return node_index[node_id]


def confirm_rule_matches(
    result: LegalParseResult, *, reviewer_id: str, now: datetime
) -> LegalParseResult:
    """Sign items that did not require individual review with the approver's identity.

    Rule matches at or above the review threshold never appear in the reviewer's task
    list (docs/05), so without this step a released document would keep them as
    ``unverified`` and the release gate could never read its metadata. Approving the
    document therefore confirms those items on the approver's behalf; rejected items
    are left untouched.
    """
    def _confirm(item):
        if item.verification is not VerificationStatus.UNVERIFIED:
            return item
        return replace(
            item,
            verification=VerificationStatus.ACCEPTED,
            requires_verification=False,
            reviewer_id=reviewer_id,
            reviewed_at=now,
        )

    return replace(
        result,
        metadata=tuple(_confirm(item) for item in result.metadata),
        nodes=tuple(_confirm(node) for node in result.nodes),
        relations=tuple(_confirm(relation) for relation in result.relations),
    )


def require_approval(
    result: LegalParseResult,
    *,
    reviewer_id: str,
    acknowledged_warnings: Sequence[str],
    now: datetime,
) -> ApprovedLegalDocument:
    """Approve a fully reviewed parse or fail with the exact blocking items."""
    if not reviewer_id.strip():
        raise ReviewIncompleteError("Approval requires a reviewer identity")
    pending = result.pending_items()
    if pending:
        raise ReviewIncompleteError(f"Parse result still has unverified items: {', '.join(pending)}")
    unacknowledged = [warning for warning in result.warnings if warning not in set(acknowledged_warnings)]
    if unacknowledged:
        raise ReviewIncompleteError(f"Warnings must be acknowledged before approval: {', '.join(unacknowledged)}")
    if not result.metadata:
        raise ReviewIncompleteError("Approval requires at least one metadata assertion")
    approved_result = confirm_rule_matches(result, reviewer_id=reviewer_id, now=now)
    return ApprovedLegalDocument(
        job_id=approved_result.job_id,
        parse_result=approved_result,
        approved_by=reviewer_id,
        approved_at=now,
        acknowledged_warnings=tuple(approved_result.warnings),
    )


class LegalReviewService:
    """Applies reviewer decisions, persists them and enforces the release gate."""

    def __init__(
        self,
        *,
        repository: "LegalParseRepository",
        audit: "AuditSink",
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.repository = repository
        self.audit = audit
        self.clock = clock

    def review(self, result: LegalParseResult, decisions: Sequence[ReviewDecision]) -> LegalParseResult:
        updated = apply_decisions(result, decisions, now=self.clock())
        self.repository.save_result(updated)
        self.repository.save_decisions(result.job_id, decisions)
        for decision in decisions:
            self.audit.record(
                actor_id=decision.reviewer_id,
                action=f"review_{decision.item_kind.value}",
                object_id=decision.item_id,
                trace_id=result.job_id,
                outcome=decision.action.value,
            )
        LOGGER.info(
            "Legal review recorded job_id=%s decisions=%d pending=%d",
            result.job_id, len(decisions), len(updated.pending_items()),
        )
        return updated

    def approve(
        self,
        result: LegalParseResult,
        *,
        reviewer_id: str,
        acknowledged_warnings: Sequence[str] = (),
    ) -> ApprovedLegalDocument:
        approval = require_approval(
            result, reviewer_id=reviewer_id, acknowledged_warnings=acknowledged_warnings, now=self.clock(),
        )
        self.repository.save_result(approval.parse_result)
        self.repository.save_approval(approval)
        self.audit.record(
            actor_id=reviewer_id,
            action="approve_document",
            object_id=result.job_id,
            trace_id=result.job_id,
            outcome="approved",
        )
        LOGGER.info("Legal document approved job_id=%s reviewer=%s", result.job_id, reviewer_id)
        return approval
