"""Rule-based parser for legal structure, metadata and relation candidates.

The parser works on extracted text only: it never invents content, always keeps
provenance (page/locator) and routes ambiguous results to manual review
(ADR-006, docs/05 section 6). Confidence is a routing signal, not a statement
about legal correctness.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .extraction import ExtractionResult, SourceSpan
from .legal_models import (
    LEVEL_ORDER,
    LegalNode,
    LegalParseResult,
    MetadataAssertion,
    MetadataField,
    NodeKind,
    Provenance,
    RelationCandidate,
    REQUIRED_METADATA_FIELDS,
)
from .legal_rules import (
    DATE_LIKE_PATTERN,
    DOCUMENT_REFERENCE_PATTERN,
    SCOPE_LABEL_PATTERN,
    HeadingRule,
    LegalParseConfig,
    MetadataRule,
    default_legal_parse_config,
    parse_vietnamese_date,
    roman_to_int,
)

LOGGER = logging.getLogger(__name__)
_WARNING_CODE_RE = re.compile(r"^[A-Z0-9_]{2,64}$")
_SANITIZE_RE = re.compile(r"[^A-Z0-9]+")
_MAX_TITLE_LENGTH = 200
_MAX_REFERENCE_LENGTH = 300
_AMBIGUOUS_DATE_PENALTY = 0.7
_TITLE_CONTINUATION_PENALTY = 0.9


@dataclass(frozen=True, slots=True)
class DocumentLine:
    index: int
    page_number: int | None
    text: str
    source_locators: tuple[str, ...]
    bbox: tuple[float, float, float, float] | None
    ocr_confidence: float | None

    @property
    def locator(self) -> str:
        if len(self.source_locators) == 1:
            return self.source_locators[0]
        return f"{self.source_locators[0]}+{len(self.source_locators) - 1}"


@dataclass(slots=True)
class _NodeDraft:
    node_id: str
    kind: NodeKind
    label: str
    ordinal: str
    title: str | None
    parent_id: str | None
    child_ids: list[str]
    provenance: Provenance
    confidence: float
    content_lines: list[str] = field(default_factory=list)
    source_locators: list[str] = field(default_factory=list)
    page_numbers: set[int] = field(default_factory=set)
    requires_verification: bool = False


@dataclass(frozen=True, slots=True)
class _HeadingMatch:
    rule: HeadingRule
    label: str
    ordinal: str
    remainder: str
    implicit_ordinal: bool = False


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def _sanitize_code(value: str) -> str:
    return _SANITIZE_RE.sub("_", value.upper()).strip("_")


def _normalize_confidence(value: float | None) -> float | None:
    """Accept both the 0-1 and the 0-100 OCR confidence scales used upstream."""
    if value is None:
        return None
    return value / 100.0 if value > 1.0 else value


def _line_confidence(spans: Sequence[SourceSpan]) -> float | None:
    values = [span.confidence for span in spans if span.confidence is not None]
    if not values:
        return None
    return _normalize_confidence(min(values))


def assemble_lines(spans: Iterable[SourceSpan], *, tolerance: float) -> tuple[DocumentLine, ...]:
    """Merge layout spans into reading-order lines while keeping every locator."""
    lines: list[DocumentLine] = []
    positioned = [span for span in spans if span.bbox is not None]
    flowing = [span for span in spans if span.bbox is None]
    pages: dict[int | None, list[SourceSpan]] = {}
    for span in positioned:
        pages.setdefault(span.page_number, []).append(span)
    for page_number in sorted(pages, key=lambda value: -1 if value is None else value):
        ordered = sorted(pages[page_number], key=lambda span: (span.bbox[1] if span.bbox else 0.0, span.bbox[0] if span.bbox else 0.0))
        group: list[SourceSpan] = []
        group_top: float | None = None
        for span in ordered:
            top = span.bbox[1] if span.bbox else 0.0
            if group and group_top is not None and abs(top - group_top) > tolerance:
                lines.append(_line_from_group(group, len(lines), page_number))
                group, group_top = [], None
            if not group:
                group_top = top
            group.append(span)
        if group:
            lines.append(_line_from_group(group, len(lines), page_number))
    for span in flowing:
        text = _normalize(span.text)
        if text:
            lines.append(DocumentLine(
                index=len(lines), page_number=span.page_number, text=text,
                source_locators=(span.source_locator,), bbox=None,
                ocr_confidence=_normalize_confidence(span.confidence),
            ))
    return tuple(lines)


def _line_from_group(group: list[SourceSpan], index: int, page_number: int | None) -> DocumentLine:
    parts: list[str] = []
    for span in group:
        text = _normalize(span.text)
        if not text:
            continue
        if parts and not parts[-1].endswith((" ", "-", "\u2013")):
            parts.append(" ")
        parts.append(text)
    boxes = [span.bbox for span in group if span.bbox is not None]
    bbox: tuple[float, float, float, float] | None = None
    if boxes:
        bbox = (
            min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes),
        )
    return DocumentLine(
        index=index,
        page_number=page_number,
        text="".join(parts).strip(),
        source_locators=tuple(span.source_locator for span in group),
        bbox=bbox,
        ocr_confidence=_line_confidence(group),
    )


def _canonical_ordinal(rule: HeadingRule, ordinal: str) -> str:
    if rule.kind in (NodeKind.CHAPTER, NodeKind.SECTION) and not ordinal.isdigit():
        value = roman_to_int(ordinal)
        return str(value) if value is not None else ordinal.upper()
    return ordinal.lower()


def _match_heading(line: DocumentLine, config: LegalParseConfig, open_kinds: tuple[NodeKind, ...]) -> _HeadingMatch | None:
    for rule in config.heading_rules:
        match = rule.pattern.match(line.text)
        if match is None:
            continue
        if rule.required_parent is not None and rule.required_parent not in open_kinds:
            continue
        ordinal = _normalize(match.group(rule.ordinal_group) or "")
        implicit = not ordinal
        if implicit:
            ordinal = rule.default_ordinal
        if not ordinal:
            continue
        label = _normalize(match.group(rule.label_group)) if rule.label_group in match.re.groupindex else rule.kind.value
        return _HeadingMatch(rule, label, ordinal, line.text[match.end():].strip(" .:\u2013-"), implicit)
    return None


def _has_orphan_marker(line: DocumentLine, config: LegalParseConfig, open_kinds: tuple[NodeKind, ...]) -> bool:
    for rule in config.heading_rules:
        if rule.strict:
            continue
        if rule.required_parent is not None and rule.required_parent in open_kinds:
            continue
        if rule.pattern.match(line.text):
            return True
    return False


def _build_hierarchy(
    lines: Sequence[DocumentLine],
    config: LegalParseConfig,
) -> tuple[
    list[_NodeDraft],
    dict[int, str | None],
    list[str],
    list[tuple[int, DocumentLine]],
    set[int],
    set[int],
]:
    drafts: list[_NodeDraft] = []
    open_nodes: list[_NodeDraft] = []
    node_for_line: dict[int, str | None] = {}
    warnings: list[str] = []
    seen_siblings: dict[tuple[str | None, str, str], int] = {}
    last_numeric: dict[str | None, int] = {}
    pending_titles: list[tuple[int, DocumentLine]] = []
    heading_indices: set[int] = set()
    inline_content_indices: set[int] = set()
    for line in lines:
        open_kinds = tuple(draft.kind for draft in open_nodes)
        match = _match_heading(line, config, open_kinds)
        if match is None:
            if not open_nodes and _has_orphan_marker(line, config, open_kinds):
                warnings.append("HIERARCHY_ORPHAN_MARKER")
            node_for_line[line.index] = open_nodes[-1].node_id if open_nodes else None
            continue
        level = LEVEL_ORDER[match.rule.kind]
        while open_nodes and LEVEL_ORDER[open_nodes[-1].kind] >= level:
            open_nodes.pop()
        parent = open_nodes[-1] if open_nodes else None
        ordinal = _canonical_ordinal(match.rule, match.ordinal)
        confidence = match.rule.confidence
        if line.ocr_confidence is not None:
            confidence = min(confidence, line.ocr_confidence)
        if match.rule.kind in (NodeKind.CHAPTER, NodeKind.SECTION) and roman_to_int(match.ordinal) is None:
            confidence = min(confidence, 0.5)
        remainder = match.remainder if match.rule.strict and len(match.remainder) <= _MAX_TITLE_LENGTH else ""
        draft = _NodeDraft(
            node_id=f"node-{len(drafts) + 1:04d}",
            kind=match.rule.kind,
            label=match.label,
            ordinal=ordinal,
            title=remainder or None,
            parent_id=parent.node_id if parent else None,
            child_ids=[],
            provenance=Provenance(line.locator, line.page_number, "layout_line", config.source_label),
            confidence=round(confidence, 4),
            source_locators=list(line.source_locators),
            page_numbers={line.page_number} if line.page_number is not None else set(),
        )
        drafts.append(draft)
        if parent is not None:
            parent.child_ids.append(draft.node_id)
        if match.implicit_ordinal:
            draft.requires_verification = True
            warnings.append(f"HIERARCHY_IMPLICIT_ORDINAL_{match.rule.kind.value.upper()}_{_sanitize_code(ordinal)}")
        key = (draft.parent_id, match.rule.kind.value, ordinal)
        if key in seen_siblings:
            draft.requires_verification = True
            drafts[seen_siblings[key]].requires_verification = True
            warnings.append(f"HIERARCHY_DUPLICATE_{match.rule.kind.value.upper()}_{_sanitize_code(ordinal)}")
        else:
            seen_siblings[key] = len(drafts) - 1
        if match.rule.kind is NodeKind.ARTICLE and ordinal.isdigit():
            parent_key = draft.parent_id
            previous = last_numeric.get(parent_key)
            if previous is not None and int(ordinal) <= previous:
                draft.requires_verification = True
                warnings.append(
                    f"HIERARCHY_UNEXPECTED_ORDINAL_{_sanitize_code(parent.ordinal if parent else 'ROOT')}_{_sanitize_code(ordinal)}"
                )
            last_numeric[parent_key] = int(ordinal)
        open_nodes.append(draft)
        node_for_line[line.index] = draft.node_id
        heading_indices.add(line.index)
        if not match.rule.strict:
            inline_content_indices.add(line.index)
        if match.rule.strict and not draft.title and line.index + 1 < len(lines):
            candidate = lines[line.index + 1]
            if len(candidate.text) <= _MAX_TITLE_LENGTH and not _is_heading(candidate.text, config):
                pending_titles.append((len(drafts) - 1, candidate))
    if not drafts:
        warnings.append("HIERARCHY_NO_NODES")
    return drafts, node_for_line, warnings, pending_titles, heading_indices, inline_content_indices


def _is_heading(text: str, config: LegalParseConfig) -> bool:
    return any(rule.pattern.match(text) for rule in config.heading_rules)


def _apply_continuation_titles(drafts: list[_NodeDraft], pending_titles: list[tuple[int, DocumentLine]]) -> None:
    for draft_index, line in pending_titles:
        draft = drafts[draft_index]
        if draft.title is not None:
            continue
        draft.title = line.text[:_MAX_TITLE_LENGTH]
        draft.confidence = round(draft.confidence * _TITLE_CONTINUATION_PENALTY, 4)
        draft.source_locators.extend(line.source_locators)
        if line.page_number is not None:
            draft.page_numbers.add(line.page_number)


def _fill_content(
    drafts: list[_NodeDraft],
    lines: Sequence[DocumentLine],
    node_for_line: dict[int, str | None],
    heading_indices: set[int],
    inline_content_indices: set[int],
) -> None:
    by_id = {draft.node_id: draft for draft in drafts}
    for line in lines:
        if line.index in heading_indices and line.index not in inline_content_indices:
            continue
        node_id = node_for_line.get(line.index)
        draft = by_id.get(node_id) if node_id else None
        if draft is None or not line.text or line.text == draft.title:
            continue
        draft.content_lines.append(line.text)
        draft.source_locators.extend(line.source_locators)
        if line.page_number is not None:
            draft.page_numbers.add(line.page_number)
        if line.ocr_confidence is not None:
            draft.confidence = min(draft.confidence, line.ocr_confidence)


def _finalize_nodes(drafts: list[_NodeDraft], config: LegalParseConfig) -> tuple[LegalNode, ...]:
    nodes: list[LegalNode] = []
    for draft in drafts:
        nodes.append(LegalNode(
            node_id=draft.node_id,
            kind=draft.kind,
            label=draft.label,
            ordinal=draft.ordinal,
            title=draft.title,
            content="\n".join(draft.content_lines),
            parent_id=draft.parent_id,
            child_ids=tuple(draft.child_ids),
            provenance=draft.provenance,
            confidence=round(draft.confidence, 4),
            page_numbers=tuple(sorted(draft.page_numbers)),
            source_locators=tuple(dict.fromkeys(draft.source_locators)),
            requires_verification=draft.requires_verification or draft.confidence < config.review_confidence_threshold,
        ))
    return tuple(nodes)


def _rule_lines(rule: MetadataRule, lines: Sequence[DocumentLine], config: LegalParseConfig) -> Sequence[DocumentLine]:
    return lines[:config.head_line_limit] if rule.search_scope == "head" else lines


def _rule_value(rule: MetadataRule, line: DocumentLine, warnings: list[str]) -> tuple[str, str, float] | None:
    """Return (normalized value, raw source text, confidence) for a matched line."""
    if rule.value_kind == "fixed":
        assert rule.pattern is not None
        match = rule.pattern.search(line.text)
        if match is None or not rule.fixed_value:
            return None
        return rule.fixed_value, match.group(0), rule.confidence
    assert rule.pattern is not None
    match = rule.pattern.search(line.text)
    if match is None:
        return None
    raw = _normalize(match.group(rule.value_group))
    if not raw:
        return None
    if rule.value_kind == "date":
        iso_value, ambiguous = parse_vietnamese_date(raw)
        if iso_value is None:
            warnings.append(f"METADATA_INVALID_{rule.metadata_field.value.upper()}")
            return None
        confidence = rule.confidence
        if ambiguous:
            confidence *= _AMBIGUOUS_DATE_PENALTY
            warnings.append(f"METADATA_AMBIGUOUS_{rule.metadata_field.value.upper()}")
        return iso_value, match.group(0), confidence
    if rule.metadata_field is not MetadataField.DOCUMENT_NUMBER and DATE_LIKE_PATTERN.match(raw):
        return None
    return raw[:_MAX_TITLE_LENGTH], match.group(0), rule.confidence


def _extract_metadata(
    lines: Sequence[DocumentLine],
    config: LegalParseConfig,
    heading_indices: set[int],
    *,
    source: str | None,
) -> tuple[tuple[MetadataAssertion, ...], list[str]]:
    warnings: list[str] = []
    assertions: list[MetadataAssertion] = []
    # line index -> metadata fields already sourced from that line. A line may feed both
    # halves of a document header ("Luật số: 31/2024/QH15"), but it is spent for every
    # other field so loose detectors cannot re-read the same text.
    used_lines: dict[int, set[MetadataField]] = {}
    header_pair = {MetadataField.DOCUMENT_TYPE, MetadataField.DOCUMENT_NUMBER}
    for rule in config.metadata_rules:
        if rule.value_kind == "head_line_title":
            continue
        for line in _rule_lines(rule, lines, config):
            previous_fields = used_lines.get(line.index)
            if rule.value_kind != "fixed" and previous_fields:
                same_field = rule.metadata_field in previous_fields
                header_reuse = rule.metadata_field in header_pair and previous_fields <= header_pair
                if same_field or not header_reuse:
                    continue
            value = _rule_value(rule, line, warnings)
            if value is None:
                continue
            normalized, raw, confidence = value
            if line.ocr_confidence is not None:
                confidence = min(confidence, line.ocr_confidence)
            if rule.value_kind != "fixed":
                used_lines.setdefault(line.index, set()).add(rule.metadata_field)
            assertions.append(MetadataAssertion(
                assertion_id=f"meta-{rule.metadata_field.value}-{len(assertions) + 1:03d}",
                field=rule.metadata_field,
                value=normalized,
                raw_value=raw,
                confidence=round(confidence, 4),
                provenance=Provenance(line.locator, line.page_number, "rule_match", rule.detector),
                required=rule.required,
                requires_verification=confidence < config.review_confidence_threshold,
            ))
            break
    title = _title_assertion(lines, config, heading_indices, used_lines)
    if title is not None:
        assertions.insert(0, title)
    if source:
        assertions.append(MetadataAssertion(
            assertion_id=f"meta-{MetadataField.SOURCE.value}-src",
            field=MetadataField.SOURCE,
            value=source,
            raw_value=source,
            confidence=1.0,
            provenance=Provenance("ingestion:source", None, "ingestion_context", "upload_source"),
            required=False,
            requires_verification=False,
        ))
    best: dict[MetadataField, MetadataAssertion] = {}
    for item in assertions:
        current = best.get(item.field)
        if current is None or item.confidence > current.confidence:
            best[item.field] = item
    for item in assertions:
        if best[item.field] is not item and item.value.casefold() != best[item.field].value.casefold():
            warnings.append(f"METADATA_CONFLICT_{item.field.value.upper()}")
    for required_field in sorted(REQUIRED_METADATA_FIELDS, key=lambda value: value.value):
        if required_field not in best:
            warnings.append(f"METADATA_MISSING_{required_field.value.upper()}")
    return tuple(assertions), warnings


def _title_assertion(
    lines: Sequence[DocumentLine],
    config: LegalParseConfig,
    heading_indices: set[int],
    used_lines: set[int],
) -> MetadataAssertion | None:
    for line in lines[:config.head_line_limit]:
        if line.index in used_lines or line.index in heading_indices or len(line.text) < 8:
            continue
        return MetadataAssertion(
            assertion_id="meta-title-001",
            field=MetadataField.TITLE,
            value=line.text[:_MAX_TITLE_LENGTH],
            raw_value=line.text,
            confidence=0.6,
            provenance=Provenance(line.locator, line.page_number, "head_line", "head_line_title"),
            required=False,
            requires_verification=True,
        )
    return None


def _extract_relations(
    lines: Sequence[DocumentLine],
    config: LegalParseConfig,
    node_for_line: dict[int, str | None],
) -> tuple[tuple[RelationCandidate, ...], list[str]]:
    relations: list[RelationCandidate] = []
    warnings: list[str] = []
    for line in lines:
        for rule in config.relation_rules:
            for match in rule.pattern.finditer(line.text):
                target = _normalize(match.group("target"))[:_MAX_REFERENCE_LENGTH]
                if not target:
                    continue
                scope_match = SCOPE_LABEL_PATTERN.search(target)
                document_number = _document_reference(target)
                confidence = rule.confidence
                if line.ocr_confidence is not None:
                    confidence = min(confidence, line.ocr_confidence)
                relations.append(RelationCandidate(
                    relation_id=f"rel-{len(relations) + 1:03d}",
                    relation_type=rule.relation_type,
                    target_reference=target,
                    provenance=Provenance(line.locator, line.page_number, "rule_match", rule.detector),
                    confidence=round(confidence, 4),
                    source_node_id=node_for_line.get(line.index),
                    target_document_number=document_number,
                    target_scope_label=_normalize(scope_match.group(0)) if scope_match else None,
                ))
                if document_number is None and scope_match is None:
                    warnings.append(f"RELATION_TARGET_UNRESOLVED_{len(relations):03d}")
    return tuple(relations), warnings


def _document_reference(text: str) -> str | None:
    for match in DOCUMENT_REFERENCE_PATTERN.finditer(text):
        candidate = match.group(0)
        if not DATE_LIKE_PATTERN.match(candidate):
            return candidate
    return None


def _dedupe(warnings: Sequence[str]) -> tuple[str, ...]:
    unique: list[str] = []
    for warning in warnings:
        code = _sanitize_code(warning)
        if not _WARNING_CODE_RE.match(code):
            raise ValueError(f"Parser produced an unstable warning code: {warning!r}")
        if code not in unique:
            unique.append(code)
    return tuple(unique)


def parse_legal_document(
    extraction: ExtractionResult,
    *,
    job_id: str,
    config: LegalParseConfig | None = None,
    source: str | None = None,
) -> LegalParseResult:
    """Parse extracted text into hierarchy, metadata assertions and relation candidates."""
    settings = config or default_legal_parse_config()
    lines = assemble_lines(extraction.spans, tolerance=settings.line_merge_tolerance)
    drafts, node_for_line, hierarchy_warnings, pending_titles, heading_indices, inline_content_indices = _build_hierarchy(lines, settings)
    _apply_continuation_titles(drafts, pending_titles)
    _fill_content(drafts, lines, node_for_line, heading_indices, inline_content_indices)
    nodes = _finalize_nodes(drafts, settings)
    metadata, metadata_warnings = _extract_metadata(lines, settings, heading_indices, source=source)
    relations, relation_warnings = _extract_relations(lines, settings, node_for_line)
    warnings = _dedupe([*hierarchy_warnings, *metadata_warnings, *relation_warnings, *extraction.warnings])
    pending = (
        any(item.is_pending for item in metadata)
        or any(node.is_pending for node in nodes)
        or any(relation.is_pending for relation in relations)
    )
    result = LegalParseResult(
        job_id=job_id,
        pipeline_version=extraction.pipeline_version,
        parser_version=settings.parser_version,
        parser_config_hash=settings.fingerprint(),
        nodes=nodes,
        metadata=metadata,
        relations=relations,
        warnings=warnings,
        review_required=extraction.review_required or bool(warnings) or pending,
        page_count=extraction.page_count,
    )
    LOGGER.info(
        "Legal parse completed job_id=%s lines=%d nodes=%d metadata=%d relations=%d review_required=%s parser=%s",
        job_id, len(lines), len(nodes), len(metadata), len(relations), result.review_required, settings.parser_version,
    )
    return result
