from __future__ import annotations

from fastapi import APIRouter

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.teaching_outputs import ModuleContextRead
from ..services.module_context import ModuleContextService

router = APIRouter(prefix="/teaching-contexts", tags=["lecturer module context"])


@router.get("", response_model=list[ModuleContextRead])
async def list_teaching_contexts(
    session: DatabaseSession,
    context: CurrentContext,
) -> list[ModuleContextRead]:
    bundles = await ModuleContextService(session, context).list_available()
    return [ModuleContextRead.model_validate(bundle.as_dict()) for bundle in bundles]
