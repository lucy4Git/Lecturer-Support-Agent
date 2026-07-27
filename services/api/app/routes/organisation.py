from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.organisation import (
    InstitutionSettingUpsert,
    OrganisationalUnitCreate,
    OrganisationalUnitMove,
    OrganisationalUnitResponse,
    OrganisationalUnitTypeCreate,
    OrganisationalUnitTypeResponse,
    OrganisationalUnitUpdate,
    TerminologyUpsert,
)
from ..services.authorization import AuthorizationService
from ..services.organisation import OrganisationService

router = APIRouter(prefix="/institution", tags=["institution structure"])


async def _require_configuration_permission(session, context) -> None:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="institution.configure",
    )


@router.post(
    "/unit-types",
    response_model=OrganisationalUnitTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_unit_type(
    payload: OrganisationalUnitTypeCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> OrganisationalUnitTypeResponse:
    await _require_configuration_permission(session, context)
    item = await OrganisationService(session, context).create_unit_type(payload)
    return OrganisationalUnitTypeResponse.model_validate(item)


@router.post(
    "/units",
    response_model=OrganisationalUnitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_unit(
    payload: OrganisationalUnitCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> OrganisationalUnitResponse:
    await _require_configuration_permission(session, context)
    item = await OrganisationService(session, context).create_unit(payload)
    return OrganisationalUnitResponse.model_validate(item)


@router.get("/units", response_model=list[OrganisationalUnitResponse])
async def list_units(
    session: DatabaseSession,
    context: CurrentContext,
    active_only: bool = True,
) -> list[OrganisationalUnitResponse]:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="academic.read",
    )
    items = await OrganisationService(session, context).list_units(active_only=active_only)
    return [OrganisationalUnitResponse.model_validate(item) for item in items]


@router.patch("/units/{unit_id}", response_model=OrganisationalUnitResponse)
async def update_unit(
    unit_id: UUID,
    payload: OrganisationalUnitUpdate,
    session: DatabaseSession,
    context: CurrentContext,
) -> OrganisationalUnitResponse:
    await _require_configuration_permission(session, context)
    item = await OrganisationService(session, context).update_unit(unit_id, payload)
    return OrganisationalUnitResponse.model_validate(item)


@router.post("/units/{unit_id}/move", response_model=OrganisationalUnitResponse)
async def move_unit(
    unit_id: UUID,
    payload: OrganisationalUnitMove,
    session: DatabaseSession,
    context: CurrentContext,
) -> OrganisationalUnitResponse:
    await _require_configuration_permission(session, context)
    item = await OrganisationService(session, context).move_unit(unit_id, payload)
    return OrganisationalUnitResponse.model_validate(item)


@router.put("/terminology/{term_key}")
async def upsert_terminology(
    term_key: str,
    payload: TerminologyUpsert,
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    await _require_configuration_permission(session, context)
    payload = payload.model_copy(update={"term_key": term_key})
    item = await OrganisationService(session, context).upsert_terminology(payload)
    return {"id": str(item.id), "term_key": item.term_key}


@router.put("/settings/{setting_key}")
async def upsert_setting(
    setting_key: str,
    payload: InstitutionSettingUpsert,
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    await _require_configuration_permission(session, context)
    payload = payload.model_copy(update={"setting_key": setting_key})
    item = await OrganisationService(session, context).upsert_setting(payload)
    return {"id": str(item.id), "setting_key": item.setting_key}
