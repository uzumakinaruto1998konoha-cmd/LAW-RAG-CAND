"""Configurable rule set for the rule-based legal parser (ADR-006).

The rules describe *structure* (chapter/section/article numbering, metadata
labels, cross-reference wording). No legal content is embedded here; the
vocabulary of document-type labels and the rule list are injected through
`LegalParseConfig` so an approved corpus can extend them without code changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from .legal_models import MetadataField, NodeKind, RelationType

SearchScope = Literal["head", "document"]
ValueKind = Literal["text", "date", "fixed", "head_line_title"]

_ROMAN_VALUES: dict[str, int] = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Structural document-type labels only; used to classify a document, never to
# restate its legal content.
DEFAULT_DOCUMENT_TYPE_VOCABULARY: tuple[str, ...] = (
    "Bộ luật",
    "Luật",
    "Nghị quyết",
    "Nghị định",
    "Quyết định",
    "Thông tư liên tịch",
    "Thông tư",
    "Thông cáo",
    "Chỉ thị",
    "Công văn",
    "Quy chế",
)

_DOCUMENT_NUMBER = r"[0-9]{1,4}\w*(?:[/\-][\w\.]+){1,5}"
_DATE = r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
_DATE_WORDS = r"\d{1,2}\s*tháng\s*\d{1,2}\s*năm\s*\d{4}"
# Official documents write dates numerically or in words; both are accepted.
_DATE_ANY = rf"(?:{_DATE_WORDS}|{_DATE})"
_SCOPE_LABEL = r"(?:Chương|Mục|Điều|Khoản|Điểm|Phụ lục)\s+[0-9IVXLCDM]+[a-z]?"

SCOPE_LABEL_PATTERN = re.compile(_SCOPE_LABEL, re.IGNORECASE)
DOCUMENT_REFERENCE_PATTERN = re.compile(rf"(?<![\w/\-]){_DOCUMENT_NUMBER}(?![\w/\-])", re.IGNORECASE)
DATE_LIKE_PATTERN = re.compile(rf"^\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{2,4}}$")


def roman_to_int(value: str) -> int | None:
    text = value.strip().upper()
    if not text or any(char not in _ROMAN_VALUES for char in text):
        return None
    total = 0
    previous = 0
    for char in reversed(text):
        current = _ROMAN_VALUES[char]
        total = total - current if current < previous else total + current
        previous = max(previous, current)
    return total


def parse_vietnamese_date(raw: str) -> tuple[str | None, bool]:
    """Return an ISO date and whether day/month order was ambiguous.

    Both numeric (``15/11/2023``) and word-form (``15 tháng 11 năm 2023``) dates are
    accepted: official documents state the date in words on the signature line, and a
    rejected date would block the document at the review gate.
    """
    word_form = re.fullmatch(
        r"(?P<day>\d{1,2})\s*tháng\s*(?P<month>\d{1,2})\s*năm\s*(?P<year>\d{4})",
        raw.strip(),
        re.IGNORECASE,
    )
    if word_form is not None:
        day = int(word_form.group("day"))
        month = int(word_form.group("month"))
        year = int(word_form.group("year"))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None, True
        try:
            # Day and month are labelled, so the order is not ambiguous.
            return date(year, month, day).isoformat(), False
        except ValueError:
            return None, True
    parts = re.split(r"[/\-.]", raw.strip())
    if len(parts) != 3:
        return None, True
    day, month, year = (int(part) for part in parts)
    if year < 100:
        year += 2000 if year <= 60 else 1900
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None, True
    ambiguous = day <= 12 and month <= 12 and day != month
    try:
        return date(year, month, day).isoformat(), ambiguous
    except ValueError:
        return None, True


@dataclass(frozen=True, slots=True)
class HeadingRule:
    kind: NodeKind
    pattern: re.Pattern[str]
    ordinal_group: str
    confidence: float
    required_parent: NodeKind | None = None
    strict: bool = True
    label_group: str = "label"
    default_ordinal: str = ""


@dataclass(frozen=True, slots=True)
class MetadataRule:
    metadata_field: MetadataField
    detector: str
    confidence: float
    required: bool = False
    value_kind: ValueKind = "text"
    fixed_value: str | None = None
    search_scope: SearchScope = "head"
    pattern: re.Pattern[str] | None = None
    value_group: str = "value"


@dataclass(frozen=True, slots=True)
class RelationRule:
    relation_type: RelationType
    detector: str
    confidence: float
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class LegalParseConfig:
    parser_version: str
    heading_rules: tuple[HeadingRule, ...]
    metadata_rules: tuple[MetadataRule, ...]
    relation_rules: tuple[RelationRule, ...]
    head_line_limit: int = 40
    review_confidence_threshold: float = 0.85
    line_merge_tolerance: float = 3.0
    document_type_vocabulary: tuple[str, ...] = DEFAULT_DOCUMENT_TYPE_VOCABULARY
    source_label: str = "legal-parse-v1"

    def fingerprint(self) -> str:
        payload = {
            "parser_version": self.parser_version,
            "headings": [rule.pattern.pattern for rule in self.heading_rules],
            "metadata": [
                {"detector": rule.detector, "field": rule.metadata_field.value, "pattern": rule.pattern.pattern if rule.pattern else None, "fixed": rule.fixed_value}
                for rule in self.metadata_rules
            ],
            "relations": [rule.pattern.pattern for rule in self.relation_rules],
            "head_line_limit": self.head_line_limit,
            "review_confidence_threshold": self.review_confidence_threshold,
            "line_merge_tolerance": self.line_merge_tolerance,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _type_pattern(vocabulary: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(label) for label in sorted(vocabulary, key=len, reverse=True))
    return re.compile(rf"^\s*(?P<value>{alternatives})\b\s*", re.IGNORECASE)


def default_legal_parse_config() -> LegalParseConfig:
    """Structural rules for Vietnamese legal documents as required by docs/05."""
    heading_rules = (
        HeadingRule(NodeKind.APPENDIX, re.compile(r"^(?P<label>Phụ\s+lục)\s*(?P<ordinal>[0-9IVXLCDM]+)?", re.IGNORECASE), "ordinal", 0.9, default_ordinal="1"),
        HeadingRule(NodeKind.CHAPTER, re.compile(r"^(?P<label>Chương)\s+(?P<ordinal>[0-9IVXLCDM]+)\b", re.IGNORECASE), "ordinal", 0.95),
        HeadingRule(NodeKind.SECTION, re.compile(r"^(?P<label>Mục)\s+(?P<ordinal>[0-9IVXLCDM]+)\b", re.IGNORECASE), "ordinal", 0.9),
        HeadingRule(NodeKind.ARTICLE, re.compile(r"^(?P<label>Điều)\s+(?P<ordinal>\d+[a-zA-Z]?)\b", re.IGNORECASE), "ordinal", 0.95),
        HeadingRule(NodeKind.CLAUSE, re.compile(r"^(?P<label>Khoản)\s+(?P<ordinal>\d+)\b", re.IGNORECASE), "ordinal", 0.9, NodeKind.ARTICLE),
        HeadingRule(NodeKind.POINT, re.compile(r"^(?P<ordinal>[a-zA-Z])\)\s+\S"), "ordinal", 0.75, NodeKind.CLAUSE, strict=False),
        HeadingRule(NodeKind.CLAUSE, re.compile(r"^(?P<ordinal>\d+)[.)]\s+\S"), "ordinal", 0.6, NodeKind.ARTICLE, strict=False),
    )
    metadata_rules = (
        MetadataRule(
            MetadataField.DOCUMENT_TYPE, "document_type_label", 0.85, required=True,
            pattern=_type_pattern(DEFAULT_DOCUMENT_TYPE_VOCABULARY), search_scope="head",
        ),
        MetadataRule(
            MetadataField.DOCUMENT_NUMBER, "document_number_label", 0.8, required=True,
            pattern=re.compile(rf"(?:số\s+hiệu|số\s+ký\s+hiệu|số)\s*[:;#]?\s*(?P<value>{_DOCUMENT_NUMBER})", re.IGNORECASE),
            search_scope="head",
        ),
        MetadataRule(
            MetadataField.ISSUING_BODY, "issuing_body_label", 0.55, required=False,
            pattern=re.compile(r"(?:cơ\s+quan\s+ban\s+hành|ban\s+hành|do)\s*[:]?\s*(?P<value>[^\n.;]{3,80})", re.IGNORECASE),
            search_scope="head",
        ),
        MetadataRule(
            MetadataField.ISSUE_DATE, "issue_date_label", 0.8, required=True, value_kind="date",
            pattern=re.compile(rf"(?:ngày\s+ban\s+hành|ngày\s+ký|ngày)\s*[:]?\s*(?P<value>{_DATE_ANY})", re.IGNORECASE),
            search_scope="document",
        ),
        MetadataRule(
            MetadataField.EFFECTIVE_DATE, "effective_date_label", 0.8, value_kind="date",
            pattern=re.compile(rf"(?:có\s+hiệu\s+lực|hiệu\s+lực\s+từ|hiệu\s+lực\s+thi\s+hanh|từ\s+ngày)\s*[:]?\s*(?P<value>{_DATE_ANY})", re.IGNORECASE),
            search_scope="document",
        ),
        MetadataRule(
            MetadataField.EXPIRY_DATE, "expiry_date_label", 0.75, value_kind="date",
            pattern=re.compile(rf"(?:hết\s+hiệu\s+lực|ngừng\s+hiệu\s+lực|không\s+còn\s+hiệu\s+lực)\s*[:]?\s*(?P<value>{_DATE_ANY})", re.IGNORECASE),
            search_scope="document",
        ),
        MetadataRule(MetadataField.LANGUAGE, "vietnamese_diacritics", 0.9, value_kind="fixed", fixed_value="vie",
                     pattern=re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")),
        MetadataRule(MetadataField.TITLE, "head_line_title", 0.6, value_kind="head_line_title", search_scope="head",
                     pattern=re.compile(r"^\S.*\S$")),
    )
    relation_rules = (
        RelationRule(RelationType.AMENDS, "amends_wording", 0.7, re.compile(
            r"(?:được\s+sửa\s+đổi|sửa\s+đổi|được\s+bổ\s+sung|bổ\s+sung)\s+(?P<target>[^.\n]{1,120})", re.IGNORECASE)),
        RelationRule(RelationType.REPLACES, "replaces_wording", 0.7, re.compile(
            r"(?:thay\s+thế)\s+(?P<target>[^.\n]{1,120})", re.IGNORECASE)),
        RelationRule(RelationType.REPEALS, "repeals_wording", 0.7, re.compile(
            r"(?:bãi\s+bỏ|hủy\s+bỏ|ngưng\s+hiệu\s+lực)\s+(?P<target>[^.\n]{1,120})", re.IGNORECASE)),
        RelationRule(RelationType.GUIDES, "guides_wording", 0.7, re.compile(
            r"(?:hướng\s+dẫn|giải\s+đẩy|thông\s+tư\s+hướng\s+dẫn)\s+(?P<target>[^.\n]{1,120})", re.IGNORECASE)),
        RelationRule(RelationType.REFERENCES, "reference_wording", 0.65, re.compile(
            rf"(?:theo\s+quy\s+định\s+tại|quy\s+định\s+tại|theo)\s+(?P<target>{_SCOPE_LABEL}[^.\n;]{{1,120}})", re.IGNORECASE)),
    )
    return LegalParseConfig(
        parser_version="legal-parse-v1",
        heading_rules=heading_rules,
        metadata_rules=metadata_rules,
        relation_rules=relation_rules,
    )
