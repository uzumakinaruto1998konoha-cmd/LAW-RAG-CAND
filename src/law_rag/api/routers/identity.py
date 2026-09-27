"""Identity endpoints: the caller's own profile and effective permissions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from law_rag.ingestion.knowledge_models import AppUser

from ..container import ApiContainer
from ..dependencies import get_container, get_current_user
from ..schemas import UserModel

router = APIRouter(tags=["identity"])


@router.get("/me", response_model=UserModel, summary="Current user and permissions")
def me(
    user: Annotated[AppUser, Depends(get_current_user)],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> UserModel:
    """Return the authenticated user with the permissions the server resolved."""
    return UserModel(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        is_system=user.is_system,
        permissions=list(container.permissions_for(user)),
    )
