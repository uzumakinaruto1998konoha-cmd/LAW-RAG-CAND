"""Liveness and readiness endpoints (no authentication required)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..container import ApiContainer
from ..dependencies import get_container
from ..schemas import HealthResponse, ReadinessCheck, ReadinessResponse

router = APIRouter(tags=["operations"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health(container: Annotated[ApiContainer, Depends(get_container)]) -> HealthResponse:
    """Report process liveness plus the architecture version in use."""
    return HealthResponse(
        status="ok",
        phase=container.display_phase,
        architecture_version=container.architecture_version,
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
def ready(container: Annotated[ApiContainer, Depends(get_container)]) -> ReadinessResponse:
    """Report subsystem readiness and index sizes (no sensitive data)."""
    checks = tuple(
        ReadinessCheck(name=name, status=status, detail=detail)
        for name, status, detail in container.readiness_checks()
    )
    overall = "ready" if all(check.status == "ok" for check in checks) else "degraded"
    return ReadinessResponse(
        status=overall,
        checks=list(checks),
        indexed_chunk_count=container.retrieval.indexed_chunk_count,
        indexed_version_count=container.retrieval.indexed_version_count,
    )
