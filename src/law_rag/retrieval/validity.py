"""Date-based validity status derivation (docs/06 section 4).

This is a calendar comparison only: it never interprets legal content, and any
status a reviewer sets explicitly overrides it at a later phase. Keeping the rule
in one function avoids a second, conflicting source of truth.
"""

from __future__ import annotations

from datetime import date

from law_rag.ingestion.knowledge_models import ValidityStatus


def derive_validity_status(
    *,
    effective_date: date | None,
    expiry_date: date | None,
    today: date,
) -> ValidityStatus:
    """Classify a released version from its dates alone.

    - ``not_yet_effective``: the effective date is in the future
    - ``expired``: the expiry date has passed
    - ``in_force``: effective now (or no effective date recorded)
    """
    if expiry_date is not None and expiry_date < today:
        return ValidityStatus.EXPIRED
    if effective_date is not None and effective_date > today:
        return ValidityStatus.NOT_YET_EFFECTIVE
    return ValidityStatus.IN_FORCE
