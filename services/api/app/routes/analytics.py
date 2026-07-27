from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.analytics import (
    AIUsagePolicyCreate,
    AIUsagePolicyResponse,
    AIUsageSummaryResponse,
    AlertActionRequest,
    AnalyticsOverviewResponse,
    AuditExportCreate,
    AuditExportResponse,
    AuditSearchResponse,
    InsightAlertResponse,
    PlatformSettingResponse,
    PlatformSettingUpsert,
    ReportDefinitionCreate,
    ReportDefinitionResponse,
    ReportRunCreate,
    ReportRunResponse,
)
from ..services.commercial_analytics import (
    AIUsageGovernanceService,
    AnalyticsService,
    AuditCentreService,
    PlatformSettingsService,
)

analytics_router = APIRouter(prefix="/analytics", tags=["commercial analytics and reports"])
audit_router = APIRouter(prefix="/audit-centre", tags=["audit centre"])
settings_router = APIRouter(prefix="/platform-settings", tags=["commercial platform settings"])
ai_governance_router = APIRouter(prefix="/ai-governance", tags=["AI usage governance"])


@analytics_router.get("/overview", response_model=AnalyticsOverviewResponse)
async def analytics_overview(
    session: DatabaseSession,
    context: CurrentContext,
    scope_type: str | None = Query(default=None),
    scope_id: UUID | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=366),
) -> dict:
    return await AnalyticsService(session, context).overview(
        requested_type=scope_type,
        requested_id=scope_id,
        days=days,
    )


@analytics_router.get("/ai-usage", response_model=AIUsageSummaryResponse)
async def ai_usage_summary(
    session: DatabaseSession,
    context: CurrentContext,
    scope_type: str | None = Query(default=None),
    scope_id: UUID | None = Query(default=None),
) -> dict:
    return await AnalyticsService(session, context).usage_summary(
        requested_type=scope_type,
        requested_id=scope_id,
    )


@analytics_router.get("/report-definitions", response_model=list[ReportDefinitionResponse])
async def report_definitions(session: DatabaseSession, context: CurrentContext):
    return await AnalyticsService(session, context).list_report_definitions()


@analytics_router.post("/report-definitions", response_model=ReportDefinitionResponse, status_code=201)
async def create_report_definition(
    payload: ReportDefinitionCreate,
    session: DatabaseSession,
    context: CurrentContext,
):
    return await AnalyticsService(session, context).create_report_definition(payload)


@analytics_router.get("/report-runs", response_model=list[ReportRunResponse])
async def report_runs(
    session: DatabaseSession,
    context: CurrentContext,
    limit: int = Query(default=50, ge=1, le=100),
):
    return await AnalyticsService(session, context).list_report_runs(limit)


@analytics_router.post("/report-runs", response_model=ReportRunResponse, status_code=201)
async def run_report(payload: ReportRunCreate, session: DatabaseSession, context: CurrentContext):
    return await AnalyticsService(session, context).run_report(payload)


@analytics_router.get("/alerts", response_model=list[InsightAlertResponse])
async def insight_alerts(
    session: DatabaseSession,
    context: CurrentContext,
    status_filter: str = Query(default="open", alias="status"),
    scope_type: str | None = Query(default=None),
    scope_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await AnalyticsService(session, context).list_alerts(
        status_filter=status_filter,
        limit=limit,
        requested_type=scope_type,
        requested_id=scope_id,
    )


@analytics_router.post("/alerts/{alert_id}/action", response_model=InsightAlertResponse)
async def act_on_alert(
    alert_id: UUID,
    payload: AlertActionRequest,
    session: DatabaseSession,
    context: CurrentContext,
):
    return await AnalyticsService(session, context).act_on_alert(alert_id, payload.action)


@ai_governance_router.get("/policies", response_model=list[AIUsagePolicyResponse])
async def list_ai_usage_policies(session: DatabaseSession, context: CurrentContext):
    return await AIUsageGovernanceService(session, context).list_policies()


@ai_governance_router.post("/policies", response_model=AIUsagePolicyResponse, status_code=201)
async def create_ai_usage_policy(
    payload: AIUsagePolicyCreate,
    session: DatabaseSession,
    context: CurrentContext,
):
    return await AIUsageGovernanceService(session, context).create_policy(payload)


@audit_router.get("/events", response_model=AuditSearchResponse)
async def audit_events(
    session: DatabaseSession,
    context: CurrentContext,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    events = await AuditCentreService(session, context).search_events(
        start_at=start_at,
        end_at=end_at,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
    )
    return {
        "total": len(events),
        "events": [
            {
                "id": item.id,
                "occurred_at": item.occurred_at,
                "actor_user_id": item.actor_user_id,
                "actor_role_code": item.actor_role_code,
                "action": item.action,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "correlation_id": item.correlation_id,
                "metadata": item.metadata_payload,
            }
            for item in events
        ],
    }


@audit_router.get("/security-events")
async def security_events(
    session: DatabaseSession,
    context: CurrentContext,
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    items = await AuditCentreService(session, context).security_events(severity=severity, limit=limit)
    return {
        "total": len(items),
        "events": [
            {
                "id": item.id,
                "occurred_at": item.occurred_at,
                "severity": item.severity,
                "event_type": item.event_type,
                "actor_user_id": item.actor_user_id,
                "description": item.description,
                "details": item.details,
                "resolved_at": item.resolved_at,
            }
            for item in items
        ],
    }


@audit_router.post("/exports", response_model=AuditExportResponse, status_code=201)
async def export_audit_events(
    payload: AuditExportCreate,
    session: DatabaseSession,
    context: CurrentContext,
):
    return await AuditCentreService(session, context).export(payload)


@settings_router.get("", response_model=list[PlatformSettingResponse])
async def list_platform_settings(
    session: DatabaseSession,
    context: CurrentContext,
    category: str | None = Query(default=None),
):
    return await PlatformSettingsService(session, context).list_settings(category)


@settings_router.put("/{category}/{setting_key}", response_model=PlatformSettingResponse)
async def upsert_platform_setting(
    category: str,
    setting_key: str,
    payload: PlatformSettingUpsert,
    session: DatabaseSession,
    context: CurrentContext,
):
    return await PlatformSettingsService(session, context).upsert(category, setting_key, payload)
