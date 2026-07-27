from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.workspace import (
    LibraryResponse,
    NotificationListResponse,
    NotificationMarkRequest,
    NotificationResponse,
    SavedOutputCreate,
    SavedOutputResponse,
    UnifiedSearchResponse,
    WorkspaceNavigationResponse,
    WorkspaceSummaryResponse,
)
from ..services.authorization import AuthorizationService
from ..services.workspace import WorkspaceService, navigation_for_role

router = APIRouter(prefix="/workspace", tags=["commercial unified workspace"])


@router.get("/navigation", response_model=WorkspaceNavigationResponse)
async def navigation(session: DatabaseSession, context: CurrentContext) -> dict:
    service = WorkspaceService(session, context)
    return navigation_for_role(context.role_code, await service.unread_notification_count())


@router.get("/summary", response_model=WorkspaceSummaryResponse)
async def summary(session: DatabaseSession, context: CurrentContext) -> dict:
    return await WorkspaceService(session, context).summary()


@router.get("/search", response_model=UnifiedSearchResponse)
async def unified_search(
    session: DatabaseSession,
    context: CurrentContext,
    q: str = Query(min_length=2, max_length=200),
    kinds: str = Query(default=""),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="workspace.search",
    )
    requested = {item.strip() for item in kinds.split(",") if item.strip()}
    try:
        results = await WorkspaceService(session, context).unified_search(q, requested, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"query": q, "total": len(results), "results": results}


@router.get("/library", response_model=LibraryResponse)
async def library(
    session: DatabaseSession,
    context: CurrentContext,
    view: str = Query(default="all", pattern="^(all|mine|institutional)$"),
    limit: int = Query(default=60, ge=1, le=250),
) -> dict:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="content.read",
    )
    items = await WorkspaceService(session, context).library_items(view=view, limit=limit)
    return {"total": len(items), "items": items}


@router.get("/files", response_model=LibraryResponse)
async def files(
    session: DatabaseSession,
    context: CurrentContext,
    view: str = Query(default="mine", pattern="^(all|mine|institutional)$"),
    limit: int = Query(default=60, ge=1, le=250),
) -> dict:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="content.read",
    )
    items = await WorkspaceService(session, context).library_items(view=view, limit=limit)
    return {"total": len(items), "items": items}


@router.get("/saved-outputs", response_model=list[SavedOutputResponse])
async def list_saved_outputs(
    session: DatabaseSession,
    context: CurrentContext,
    limit: int = Query(default=100, ge=1, le=250),
) -> list[dict]:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="saved_outputs.manage",
    )
    return await WorkspaceService(session, context).saved_outputs(limit)


@router.post("/saved-outputs", response_model=SavedOutputResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_output(
    payload: SavedOutputCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="saved_outputs.manage",
    )
    saved = await WorkspaceService(session, context).save_output(payload)
    rows = await WorkspaceService(session, context).saved_outputs(250)
    return next(item for item in rows if item["id"] == saved.id)


@router.delete("/saved-outputs/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_output(
    saved_id: UUID,
    session: DatabaseSession,
    context: CurrentContext,
) -> Response:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="saved_outputs.manage",
    )
    await WorkspaceService(session, context).delete_saved_output(saved_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notifications", response_model=NotificationListResponse)
async def notifications(
    session: DatabaseSession,
    context: CurrentContext,
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=250),
) -> dict:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="notifications.read",
    )
    service = WorkspaceService(session, context)
    items = await service.notifications(unread_only=unread_only, limit=limit)
    return {"unread_count": await service.unread_notification_count(), "total": len(items), "items": items}


@router.patch("/notifications/{notification_id}", response_model=NotificationResponse)
async def mark_notification(
    notification_id: UUID,
    payload: NotificationMarkRequest,
    session: DatabaseSession,
    context: CurrentContext,
):
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="notifications.read",
    )
    return await WorkspaceService(session, context).mark_notification(notification_id, payload.read)


@router.post("/notifications/read-all")
async def read_all_notifications(session: DatabaseSession, context: CurrentContext) -> dict:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="notifications.read",
    )
    count = await WorkspaceService(session, context).mark_all_notifications_read()
    return {"marked_read": count}
