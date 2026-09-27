"""PostgreSQL adapter for legal parse runs, reviewer decisions and approvals.

The connection factory is injected from deployment wiring (ADR-003) so this
module adds no database driver dependency of its own.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from .errors import IngestionError
from .legal_models import (
    LegalNode,
    LegalParseResult,
    MetadataAssertion,
    MetadataField,
    NodeKind,
    Provenance,
    RelationCandidate,
    RelationType,
    VerificationStatus,
)
from .legal_review import ApprovedLegalDocument, ReviewDecision
from .postgres import ConnectionFactory


def _node(row: Sequence[Any], child_ids: dict[str, list[str]]) -> LegalNode:
    return LegalNode(
        node_id=str(row[0]), kind=NodeKind(row[1]), label=str(row[2]), ordinal=str(row[3]), title=row[4],
        content=str(row[5]), parent_id=row[6], child_ids=tuple(child_ids.get(str(row[0]), ())),
        confidence=float(row[7]), page_numbers=tuple(int(page) for page in (row[8] or ())),
        source_locators=tuple(str(item) for item in (row[9] or ())),
        provenance=Provenance(source_locator=str(row[10]), page_number=row[11], method=str(row[12]), detector=str(row[13])),
        requires_verification=bool(row[14]), verification=VerificationStatus(row[15]),
        reviewer_id=row[16], reviewed_at=row[17],
    )


def _metadata(row: Sequence[Any]) -> MetadataAssertion:
    return MetadataAssertion(
        assertion_id=str(row[0]), field=MetadataField(row[1]), value=str(row[2]), raw_value=str(row[3]),
        confidence=float(row[4]), required=bool(row[5]), requires_verification=bool(row[6]),
        verification=VerificationStatus(row[7]),
        provenance=Provenance(source_locator=str(row[8]), page_number=row[9], method=str(row[11]), detector=str(row[10])),
        reviewer_id=row[12], reviewed_at=row[13],
    )


def _relation(row: Sequence[Any]) -> RelationCandidate:
    return RelationCandidate(
        relation_id=str(row[0]), relation_type=RelationType(row[1]), target_reference=str(row[3]),
        confidence=float(row[6]), source_node_id=row[2], target_document_number=row[4], target_scope_label=row[5],
        provenance=Provenance(source_locator=str(row[9]), page_number=row[10], method=str(row[12]), detector=str(row[11])),
        requires_verification=bool(row[7]), verification=VerificationStatus(row[8]),
        reviewer_id=row[13], reviewed_at=row[14],
    )


class PostgresLegalParseRepository:
    """Each save creates a new immutable parse run; reviews update that run."""

    def __init__(self, connect: ConnectionFactory) -> None:
        self._connect = connect

    def save_result(self, result: LegalParseResult) -> LegalParseResult:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO legal_parse_run
                       (parse_run_id, job_id, pipeline_version, parser_version, parser_config_hash,
                        page_count, review_required, warnings, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        run_id, result.job_id, result.pipeline_version, result.parser_version,
                        result.parser_config_hash, result.page_count, result.review_required,
                        list(result.warnings), now, now,
                    ),
                )
                for node in result.nodes:
                    self._insert_node(connection, run_id, node)
                for item in result.metadata:
                    self._insert_metadata(connection, run_id, item)
                for relation in result.relations:
                    self._insert_relation(connection, run_id, relation)
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError("Legal parse result could not be recorded") from exc
        return result

    def _insert_node(self, connection: Any, run_id: str, node: LegalNode) -> None:
        connection.execute(
            """INSERT INTO legal_node
               (node_id, parse_run_id, kind, label, ordinal, title, content, parent_id, confidence,
                page_numbers, source_locators, source_locator, source_page, source_method, source_detector,
                requires_verification, verification, reviewer_id, reviewed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (parse_run_id, node_id) DO UPDATE SET
                 title = EXCLUDED.title, content = EXCLUDED.content, parent_id = EXCLUDED.parent_id,
                 requires_verification = EXCLUDED.requires_verification, verification = EXCLUDED.verification,
                 reviewer_id = EXCLUDED.reviewer_id, reviewed_at = EXCLUDED.reviewed_at""",
            (
                node.node_id, run_id, node.kind.value, node.label, node.ordinal, node.title, node.content,
                node.parent_id, node.confidence, list(node.page_numbers), list(node.source_locators),
                node.provenance.source_locator, node.provenance.page_number, node.provenance.method,
                node.provenance.detector, node.requires_verification, node.verification.value,
                node.reviewer_id, node.reviewed_at,
            ),
        )

    def _insert_metadata(self, connection: Any, run_id: str, item: MetadataAssertion) -> None:
        connection.execute(
            """INSERT INTO metadata_assertion
               (assertion_id, parse_run_id, field, value, raw_value, confidence, required,
                requires_verification, verification, source_locator, source_page, detector, method,
                reviewer_id, reviewed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (parse_run_id, assertion_id) DO UPDATE SET
                 value = EXCLUDED.value, requires_verification = EXCLUDED.requires_verification,
                 verification = EXCLUDED.verification, reviewer_id = EXCLUDED.reviewer_id,
                 reviewed_at = EXCLUDED.reviewed_at""",
            (
                item.assertion_id, run_id, item.field.value, item.value, item.raw_value, item.confidence,
                item.required, item.requires_verification, item.verification.value,
                item.provenance.source_locator, item.provenance.page_number, item.provenance.detector,
                item.provenance.method, item.reviewer_id, item.reviewed_at,
            ),
        )

    def _insert_relation(self, connection: Any, run_id: str, relation: RelationCandidate) -> None:
        connection.execute(
            """INSERT INTO document_relation_candidate
               (relation_id, parse_run_id, relation_type, source_node_id, target_reference,
                target_document_number, target_scope_label, confidence, requires_verification, verification,
                source_locator, source_page, detector, method, reviewer_id, reviewed_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (parse_run_id, relation_id) DO UPDATE SET
                 target_reference = EXCLUDED.target_reference,
                 target_document_number = EXCLUDED.target_document_number,
                 target_scope_label = EXCLUDED.target_scope_label,
                 requires_verification = EXCLUDED.requires_verification,
                 verification = EXCLUDED.verification, reviewer_id = EXCLUDED.reviewer_id,
                 reviewed_at = EXCLUDED.reviewed_at""",
            (
                relation.relation_id, run_id, relation.relation_type.value, relation.source_node_id,
                relation.target_reference, relation.target_document_number, relation.target_scope_label,
                relation.confidence, relation.requires_verification, relation.verification.value,
                relation.provenance.source_locator, relation.provenance.page_number,
                relation.provenance.detector, relation.provenance.method, relation.reviewer_id, relation.reviewed_at,
            ),
        )

    def get_latest(self, job_id: str) -> LegalParseResult | None:
        try:
            with self._connect() as connection:
                run = connection.execute(
                    """SELECT parse_run_id, pipeline_version, parser_version, parser_config_hash, page_count,
                              review_required, warnings
                       FROM legal_parse_run WHERE job_id = %s ORDER BY created_at DESC LIMIT 1""",
                    (job_id,),
                ).fetchone()
                if run is None:
                    return None
                run_id = str(run[0])
                nodes = connection.execute(
                    """SELECT node_id, kind, label, ordinal, title, content, parent_id, confidence,
                              page_numbers, source_locators, source_locator, source_page, source_method,
                              source_detector, requires_verification, verification, reviewer_id, reviewed_at
                       FROM legal_node WHERE parse_run_id = %s ORDER BY node_id""",
                    (run_id,),
                ).fetchall()
                metadata = connection.execute(
                    """SELECT assertion_id, field, value, raw_value, confidence, required,
                              requires_verification, verification, source_locator, source_page,
                              detector, method, reviewer_id, reviewed_at
                       FROM metadata_assertion WHERE parse_run_id = %s ORDER BY assertion_id""",
                    (run_id,),
                ).fetchall()
                relations = connection.execute(
                    """SELECT relation_id, relation_type, source_node_id, target_reference,
                              target_document_number, target_scope_label, confidence, requires_verification,
                              verification, source_locator, source_page, detector, method, reviewer_id, reviewed_at
                       FROM document_relation_candidate WHERE parse_run_id = %s ORDER BY relation_id""",
                    (run_id,),
                ).fetchall()
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError("Legal parse result could not be loaded") from exc
        child_ids: dict[str, list[str]] = {}
        for row in nodes:
            if row[6] is not None:
                child_ids.setdefault(str(row[6]), []).append(str(row[0]))
        return LegalParseResult(
            job_id=job_id,
            pipeline_version=str(run[1]),
            parser_version=str(run[2]),
            parser_config_hash=str(run[3]),
            page_count=int(run[4]) if run[4] is not None else None,
            review_required=bool(run[5]),
            warnings=tuple(str(item) for item in (run[6] or ())),
            nodes=tuple(_node(row, child_ids) for row in nodes),
            metadata=tuple(_metadata(row) for row in metadata),
            relations=tuple(_relation(row) for row in relations),
        )

    def save_decisions(self, job_id: str, decisions: Sequence[ReviewDecision]) -> None:
        if not decisions:
            return
        try:
            with self._connect() as connection:
                run = connection.execute(
                    "SELECT parse_run_id FROM legal_parse_run WHERE job_id = %s ORDER BY created_at DESC LIMIT 1",
                    (job_id,),
                ).fetchone()
                if run is None:
                    raise IngestionError("Legal parse result was not found")
                for decision in decisions:
                    connection.execute(
                        """INSERT INTO review_decision
                           (job_id, parse_run_id, item_kind, item_id, action, reviewer_id, corrected_value,
                            target_document_number, target_scope_label, comment, decided_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""",
                        (
                            job_id, str(run[0]), decision.item_kind.value, decision.item_id, decision.action.value,
                            decision.reviewer_id, decision.value, decision.target_document_number,
                            decision.target_scope_label, decision.comment,
                        ),
                    )
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError("Review decisions could not be recorded") from exc

    def save_approval(self, approval: ApprovedLegalDocument) -> None:
        try:
            with self._connect() as connection:
                run = connection.execute(
                    "SELECT parse_run_id FROM legal_parse_run WHERE job_id = %s ORDER BY created_at DESC LIMIT 1",
                    (approval.job_id,),
                ).fetchone()
                if run is None:
                    raise IngestionError("Legal parse result was not found")
                connection.execute(
                    """INSERT INTO document_approval (job_id, parse_run_id, approved_by, approved_at, acknowledged_warnings)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (job_id) DO UPDATE SET parse_run_id = EXCLUDED.parse_run_id,
                         approved_by = EXCLUDED.approved_by, approved_at = EXCLUDED.approved_at,
                         acknowledged_warnings = EXCLUDED.acknowledged_warnings""",
                    (
                        approval.job_id, str(run[0]), approval.approved_by, approval.approved_at,
                        list(approval.acknowledged_warnings),
                    ),
                )
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError("Document approval could not be recorded") from exc
