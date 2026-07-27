from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AIRequest,
    AIUsageDaily,
    AIUsagePolicy,
    AnalyticsSnapshot,
    AssignedReviewTask,
    AuditEvent,
    AuditExportJob,
    Conversation,
    Document,
    GeneratedOutput,
    InsightAlert,
    ModelExecution,
    ModuleOffering,
    ModuleReadinessProfile,
    PlatformSetting,
    ReportDefinition,
    ReportRun,
    ReviewCycle,
    SecurityEvent,
    TeachingSession,
    WorkloadActivity,
)

from ..ai.contracts import TaskClassification
from ..core.request_context import RequestContext
from ..schemas.analytics import (
    AIUsagePolicyCreate,
    AuditExportCreate,
    PlatformSettingUpsert,
    ReportDefinitionCreate,
    ReportRunCreate,
)
from .audit import AuditService
from .authorization import AuthorizationService

PERSONAL_ANALYTICS_ROLES = {
    "lecturer",
    "internal_moderator",
    "external_moderator",
    "external_reviewer",
}
PROVIDER_NAMES = {"openai", "anthropic", "google_gemini", "deepseek", "ollama", "development_mock"}
SUPPORTED_REPORT_TYPES = {"teaching_operations_summary", "module_readiness_summary", "moderation_progress", "ai_usage_governance", "lecturer_activity_summary"}
SECRET_KEY_MARKERS = ("secret", "password", "api_key", "apikey", "token", "private_key", "credential")
SECRET_VALUE_PREFIXES = ("sk-", "AIza", "ghp_", "xoxb-", "sk-ant-")


@dataclass(frozen=True, slots=True)
class AnalyticsScopeDecision:
    scope_type: str
    scope_id: UUID | None
    permission_code: str


@dataclass(frozen=True, slots=True)
class AIUsageDecision:
    allowed_providers: tuple[str, ...]
    denied_providers: tuple[str, ...]
    local_only: bool
    source_required: bool
    hard_blocked: bool
    warning_codes: tuple[str, ...]
    policy_id: UUID | None
    currency_code: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed_providers": list(self.allowed_providers),
            "denied_providers": list(self.denied_providers),
            "local_only": self.local_only,
            "source_required": self.source_required,
            "hard_blocked": self.hard_blocked,
            "warning_codes": list(self.warning_codes),
            "policy_id": str(self.policy_id) if self.policy_id else None,
            "currency_code": self.currency_code,
        }


def month_bounds(day: date | None = None) -> tuple[date, date]:
    current = day or datetime.now(timezone.utc).date()
    start = current.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - timedelta(days=1)


def period_bounds(days: int, today: date | None = None) -> tuple[date, date]:
    if days < 1 or days > 366:
        raise ValueError("Analytics period must be between 1 and 366 days.")
    end = today or datetime.now(timezone.utc).date()
    return end - timedelta(days=days - 1), end


def resolve_analytics_scope(role_code: str, requested_type: str | None, requested_id: UUID | None, user_id: UUID) -> AnalyticsScopeDecision:
    """Fail-closed role-to-scope contract used by analytics and reports."""

    if role_code in PERSONAL_ANALYTICS_ROLES:
        return AnalyticsScopeDecision("user", user_id, "analytics.read_own")
    if role_code == "institution_administrator":
        if requested_type in {None, "institution"}:
            return AnalyticsScopeDecision("institution", None, "analytics.read_institution")
        if requested_type == "organisational_unit" and requested_id:
            return AnalyticsScopeDecision(requested_type, requested_id, "analytics.read_institution")
        raise ValueError("Institution administrators may request institution or organisational-unit analytics.")
    if role_code in {"head_of_department", "module_coordinator", "programme_coordinator"}:
        if requested_type != "organisational_unit" or requested_id is None:
            raise ValueError("This active role requires an authorised organisational-unit scope.")
        return AnalyticsScopeDecision(requested_type, requested_id, "analytics.read_department")
    raise ValueError("The active role does not have an analytics scope.")


def validate_setting_key_and_value(category: str, key: str, payload: PlatformSettingUpsert) -> tuple[bool, dict]:
    """Reject direct secrets while allowing an environment-variable reference."""

    normalised = f"{category}.{key}".lower()
    secret_marked = any(marker in normalised for marker in SECRET_KEY_MARKERS)
    serialised = json.dumps(payload.value, sort_keys=True)
    contains_secret_value = any(prefix in serialised for prefix in SECRET_VALUE_PREFIXES)
    if contains_secret_value:
        raise ValueError("A platform setting must not contain a live secret value.")
    if secret_marked and payload.value_type != "secret_reference":
        raise ValueError("Secret-backed settings may store only a secret reference.")
    if payload.value_type == "secret_reference":
        reference = str(payload.value.get("environment_variable", "")).strip()
        if not reference or not reference.replace("_", "").isalnum() or reference.upper() != reference:
            raise ValueError("A secret reference must name an uppercase environment variable.")
        return True, {"environment_variable": reference}
    return False, payload.value


def evaluate_usage_policy(
    *,
    policy: AIUsagePolicy | None,
    privacy_classification: str,
    task_type: str,
    usage: dict[str, Decimal | int],
) -> AIUsageDecision:
    if policy is None:
        return AIUsageDecision((), (), False, False, False, (), None, "GBP")

    warnings: list[str] = []
    hard_blocked = False
    metrics = (
        ("monthly_request_limit", "request_count"),
        ("monthly_input_token_limit", "input_tokens"),
        ("monthly_output_token_limit", "output_tokens"),
        ("monthly_cost_limit", "estimated_cost"),
    )
    for limit_name, usage_name in metrics:
        limit = getattr(policy, limit_name)
        if limit is None:
            continue
        current = Decimal(str(usage.get(usage_name, 0)))
        maximum = Decimal(str(limit))
        percent = Decimal("0") if maximum == 0 else (current / maximum * 100)
        if percent >= Decimal(str(policy.warning_threshold_percent)):
            warnings.append(f"{usage_name}_warning")
        if current >= maximum and policy.hard_limit_enabled:
            warnings.append(f"{usage_name}_limit_reached")
            hard_blocked = True

    local_only = privacy_classification in set(policy.local_only_privacy_classes or [])
    source_required = task_type in set(policy.source_required_for_tasks or [])
    allowed = tuple(item for item in (policy.allowed_providers or []) if item in PROVIDER_NAMES)
    denied = tuple(item for item in (policy.denied_providers or []) if item in PROVIDER_NAMES)
    if local_only:
        allowed = ("ollama",)
        denied = tuple(sorted(PROVIDER_NAMES - {"ollama", "development_mock"}))
    return AIUsageDecision(
        allowed,
        denied,
        local_only,
        source_required,
        hard_blocked,
        tuple(dict.fromkeys(warnings)),
        policy.id,
        policy.currency_code,
    )


class AnalyticsService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)

    async def require_scope(self, requested_type: str | None, requested_id: UUID | None) -> AnalyticsScopeDecision:
        try:
            decision = resolve_analytics_scope(self.context.role_code, requested_type, requested_id, self.context.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        kwargs: dict[str, Any] = {
            "tenant_id": self.context.tenant_id,
            "user_id": self.context.user_id,
            "permission_code": decision.permission_code,
        }
        if decision.scope_type == "organisational_unit":
            kwargs.update(scope_type="organisational_unit", scope_id=decision.scope_id)
        await self.authorization.require_permission(**kwargs)
        return decision

    def _conversation_scope(self, statement: Any, scope: AnalyticsScopeDecision) -> Any:
        if scope.scope_type == "user":
            return statement.where(Conversation.owner_user_id == scope.scope_id)
        if scope.scope_type == "organisational_unit":
            return statement.where(Conversation.org_unit_id == scope.scope_id)
        return statement

    def _offering_scope(self, statement: Any, scope: AnalyticsScopeDecision) -> Any:
        if scope.scope_type == "user":
            return statement
        if scope.scope_type == "organisational_unit":
            return statement.where(ModuleOffering.org_unit_id == scope.scope_id)
        return statement

    async def overview(
        self,
        *,
        requested_type: str | None,
        requested_id: UUID | None,
        days: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict:
        scope = await self.require_scope(requested_type, requested_id)
        if (period_start is None) != (period_end is None):
            raise HTTPException(status_code=422, detail="Both report period dates are required together.")
        if period_start is not None and period_end is not None:
            if period_start > period_end:
                raise HTTPException(status_code=422, detail="Period start must not be after the end.")
            if (period_end - period_start).days > 365:
                raise HTTPException(status_code=422, detail="Analytics period must not exceed 366 days.")
            start, end = period_start, period_end
        else:
            start, end = period_bounds(days)
        start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        conversation_stmt = select(func.count(Conversation.id)).where(
            Conversation.tenant_id == self.context.tenant_id,
            Conversation.created_at >= start_dt,
            Conversation.created_at < end_dt,
        )
        conversation_stmt = self._conversation_scope(conversation_stmt, scope)
        conversations = int(await self.session.scalar(conversation_stmt) or 0)

        output_stmt = (
            select(GeneratedOutput.output_type, func.count(GeneratedOutput.id))
            .join(Conversation, Conversation.id == GeneratedOutput.conversation_id)
            .where(
                GeneratedOutput.tenant_id == self.context.tenant_id,
                GeneratedOutput.created_at >= start_dt,
                GeneratedOutput.created_at < end_dt,
            )
            .group_by(GeneratedOutput.output_type)
        )
        output_stmt = self._conversation_scope(output_stmt, scope)
        output_rows = (await self.session.execute(output_stmt)).all()
        output_mix = [{"label": output_type.replace("_", " ").title(), "value": int(count)} for output_type, count in output_rows]
        outputs = sum(item["value"] for item in output_mix)

        document_stmt = select(func.count(Document.id)).where(
            Document.tenant_id == self.context.tenant_id,
            Document.created_at >= start_dt,
            Document.created_at < end_dt,
            Document.is_deleted.is_(False),
        )
        if scope.scope_type == "user":
            document_stmt = document_stmt.where(Document.owner_user_id == scope.scope_id)
        elif scope.scope_type == "organisational_unit":
            document_stmt = document_stmt.where(Document.org_unit_id == scope.scope_id)
        documents = int(await self.session.scalar(document_stmt) or 0)

        model_stmt = (
            select(ModelExecution.provider, func.count(ModelExecution.id))
            .join(AIRequest, AIRequest.id == ModelExecution.ai_request_id)
            .join(Conversation, Conversation.id == AIRequest.conversation_id)
            .where(
                ModelExecution.tenant_id == self.context.tenant_id,
                ModelExecution.created_at >= start_dt,
                ModelExecution.created_at < end_dt,
                ModelExecution.status == "completed",
            )
            .group_by(ModelExecution.provider)
        )
        model_stmt = self._conversation_scope(model_stmt, scope)
        provider_rows = (await self.session.execute(model_stmt)).all()
        provider_mix = [{"label": provider, "value": int(count)} for provider, count in provider_rows]

        session_stmt = (
            select(TeachingSession.status, func.count(TeachingSession.id))
            .join(ModuleOffering, ModuleOffering.id == TeachingSession.module_offering_id)
            .where(
                TeachingSession.tenant_id == self.context.tenant_id,
                TeachingSession.planned_start >= start_dt,
                TeachingSession.planned_start < end_dt,
            )
            .group_by(TeachingSession.status)
        )
        session_stmt = self._offering_scope(session_stmt, scope)
        if scope.scope_type == "user":
            session_stmt = session_stmt.where(TeachingSession.delivered_by_user_id == scope.scope_id)
        session_rows = {status_code: int(count) for status_code, count in (await self.session.execute(session_stmt)).all()}

        readiness_stmt = (
            select(ModuleReadinessProfile.status, func.count(ModuleReadinessProfile.id))
            .where(ModuleReadinessProfile.tenant_id == self.context.tenant_id)
            .group_by(ModuleReadinessProfile.status)
        )
        if scope.scope_type == "user":
            readiness_stmt = readiness_stmt.where(ModuleReadinessProfile.owner_user_id == scope.scope_id)
        elif scope.scope_type == "organisational_unit":
            readiness_stmt = readiness_stmt.where(ModuleReadinessProfile.organisational_unit_id == scope.scope_id)
        readiness_rows = {status_code: int(count) for status_code, count in (await self.session.execute(readiness_stmt)).all()}

        if scope.scope_type == "user" and self.context.role_code in {
            "internal_moderator", "external_moderator", "external_reviewer"
        }:
            review_stmt = (
                select(AssignedReviewTask.status, func.count(AssignedReviewTask.id))
                .where(
                    AssignedReviewTask.tenant_id == self.context.tenant_id,
                    AssignedReviewTask.assigned_user_id == scope.scope_id,
                )
                .group_by(AssignedReviewTask.status)
            )
        else:
            review_stmt = select(ReviewCycle.status, func.count(ReviewCycle.id)).where(
                ReviewCycle.tenant_id == self.context.tenant_id
            ).group_by(ReviewCycle.status)
            if scope.scope_type == "user":
                review_stmt = review_stmt.where(ReviewCycle.initiated_by_user_id == scope.scope_id)
            elif scope.scope_type == "organisational_unit":
                review_stmt = review_stmt.join(ModuleOffering, ModuleOffering.id == ReviewCycle.module_offering_id).where(
                    ModuleOffering.org_unit_id == scope.scope_id
                )
        review_rows = {status_code: int(count) for status_code, count in (await self.session.execute(review_stmt)).all()}

        workload_stmt = select(func.coalesce(func.sum(WorkloadActivity.allocated_hours * WorkloadActivity.weighting_factor), 0)).where(
            WorkloadActivity.tenant_id == self.context.tenant_id,
            WorkloadActivity.status == "active",
        )
        if scope.scope_type == "user":
            workload_stmt = workload_stmt.where(WorkloadActivity.user_id == scope.scope_id)
        elif scope.scope_type == "organisational_unit":
            workload_stmt = workload_stmt.join(ModuleOffering, ModuleOffering.id == WorkloadActivity.module_offering_id, isouter=True).where(
                or_(ModuleOffering.org_unit_id == scope.scope_id, WorkloadActivity.module_offering_id.is_(None))
            )
        workload_hours = float(await self.session.scalar(workload_stmt) or 0)

        alerts_stmt = select(InsightAlert).where(
            InsightAlert.tenant_id == self.context.tenant_id,
            InsightAlert.status == "open",
        ).order_by(InsightAlert.severity.desc(), InsightAlert.detected_at.desc()).limit(10)
        if scope.scope_type == "user":
            alerts_stmt = alerts_stmt.where(InsightAlert.scope_type == "user", InsightAlert.scope_id == scope.scope_id)
        elif scope.scope_type == "organisational_unit":
            alerts_stmt = alerts_stmt.where(
                InsightAlert.scope_type == "organisational_unit",
                InsightAlert.scope_id == scope.scope_id,
            )
        alerts = list(await self.session.scalars(alerts_stmt))

        cards = [
            {"key": "conversations", "label": "AI conversations", "value": conversations, "status": "neutral", "description": "New conversations in the selected period."},
            {"key": "outputs", "label": "Teaching outputs", "value": outputs, "status": "positive", "description": "Structured outputs generated in the unified workspace."},
            {"key": "documents", "label": "Materials added", "value": documents, "status": "neutral", "description": "New authorised documents and files."},
            {"key": "open_alerts", "label": "Open insights", "value": len(alerts), "status": "warning" if alerts else "positive", "description": "Operational or governance alerts requiring attention."},
        ]
        result = {
            "scope": {"scope_type": scope.scope_type, "scope_id": scope.scope_id},
            "period_start": start,
            "period_end": end,
            "generated_at": datetime.now(timezone.utc),
            "cards": cards,
            "output_mix": output_mix,
            "provider_mix": provider_mix,
            "teaching_delivery": session_rows,
            "readiness": readiness_rows,
            "moderation": review_rows,
            "workload": {"weighted_hours": workload_hours},
            "alerts": [
                {"id": str(item.id), "severity": item.severity, "title": item.title, "message": item.message, "action_path": item.action_path}
                for item in alerts
            ],
            "data_notes": [
                "Analytics are tenant-filtered and additionally constrained by the active role scope.",
                "Runtime totals require the owner-machine database validation before acceptance.",
            ],
        }
        snapshot = AnalyticsSnapshot(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            snapshot_type="commercial_overview",
            scope_type=scope.scope_type,
            scope_id=scope.scope_id,
            period_start=start,
            period_end=end,
            metrics=json.loads(json.dumps(result, default=str)),
            source_watermark={"generated_at": result["generated_at"].isoformat()},
            generated_by_user_id=self.context.user_id,
            generated_at=result["generated_at"],
        )
        self.session.add(snapshot)
        await self.audit.record(
            action="analytics.snapshot.generated",
            resource_type="analytics_snapshot",
            resource_id=snapshot.id,
            after_state={"scope_type": scope.scope_type, "scope_id": str(scope.scope_id) if scope.scope_id else None},
        )
        await self.session.flush()
        return result

    async def usage_summary(self, *, requested_type: str | None, requested_id: UUID | None) -> dict:
        scope = await self.require_scope(requested_type, requested_id)
        start, end = month_bounds()
        statement = select(
            func.coalesce(func.sum(AIUsageDaily.request_count), 0),
            func.coalesce(func.sum(AIUsageDaily.successful_count), 0),
            func.coalesce(func.sum(AIUsageDaily.failed_count), 0),
            func.coalesce(func.sum(AIUsageDaily.input_tokens), 0),
            func.coalesce(func.sum(AIUsageDaily.output_tokens), 0),
            func.coalesce(func.sum(AIUsageDaily.estimated_cost), 0),
            func.coalesce(func.sum(AIUsageDaily.latency_total_ms), 0),
        ).where(
            AIUsageDaily.tenant_id == self.context.tenant_id,
            AIUsageDaily.usage_date >= start,
            AIUsageDaily.usage_date <= end,
        )
        if scope.scope_type == "user":
            statement = statement.where(AIUsageDaily.user_id == scope.scope_id)
        totals = (await self.session.execute(statement)).one()
        request_count = int(totals[0] or 0)
        provider_stmt = select(
            AIUsageDaily.provider,
            func.sum(AIUsageDaily.request_count),
            func.sum(AIUsageDaily.input_tokens),
            func.sum(AIUsageDaily.output_tokens),
            func.sum(AIUsageDaily.estimated_cost),
        ).where(
            AIUsageDaily.tenant_id == self.context.tenant_id,
            AIUsageDaily.usage_date >= start,
            AIUsageDaily.usage_date <= end,
        ).group_by(AIUsageDaily.provider)
        providers = [
            {"provider": provider, "requests": int(requests or 0), "input_tokens": int(input_tokens or 0), "output_tokens": int(output_tokens or 0), "estimated_cost": str(cost or 0)}
            for provider, requests, input_tokens, output_tokens, cost in (await self.session.execute(provider_stmt)).all()
        ]
        policy = await AIUsageGovernanceService(self.session, self.context).resolve_policy(scope.scope_type, scope.scope_id)
        decision = evaluate_usage_policy(
            policy=policy,
            privacy_classification="internal",
            task_type="summary",
            usage={"request_count": request_count, "input_tokens": int(totals[3] or 0), "output_tokens": int(totals[4] or 0), "estimated_cost": Decimal(str(totals[5] or 0))},
        )
        return {
            "scope": {"scope_type": scope.scope_type, "scope_id": scope.scope_id},
            "period_start": start,
            "period_end": end,
            "request_count": request_count,
            "successful_count": int(totals[1] or 0),
            "failed_count": int(totals[2] or 0),
            "input_tokens": int(totals[3] or 0),
            "output_tokens": int(totals[4] or 0),
            "estimated_cost": Decimal(str(totals[5] or 0)),
            "currency_code": policy.currency_code if policy else "GBP",
            "average_latency_ms": (float(totals[6]) / request_count if request_count else None),
            "providers": providers,
            "policy_status": decision.as_dict(),
        }

    async def create_report_definition(self, payload: ReportDefinitionCreate) -> ReportDefinition:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="reports.manage",
        )
        definition = ReportDefinition(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            code=payload.code,
            name=payload.name,
            report_type=payload.report_type,
            description=payload.description,
            default_scope_type=payload.default_scope_type,
            default_parameters=payload.default_parameters,
            allowed_formats=payload.allowed_formats,
            owner_user_id=self.context.user_id,
            shared=payload.shared,
            is_active=True,
        )
        self.session.add(definition)
        await self.audit.record(action="report.definition.created", resource_type="report_definition", resource_id=definition.id)
        await self.session.flush()
        return definition

    async def list_report_definitions(self) -> list[ReportDefinition]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="reports.generate",
        )
        return list(await self.session.scalars(
            select(ReportDefinition).where(
                ReportDefinition.tenant_id == self.context.tenant_id,
                ReportDefinition.is_active.is_(True),
                or_(ReportDefinition.shared.is_(True), ReportDefinition.owner_user_id == self.context.user_id),
            ).order_by(ReportDefinition.name)
        ))

    async def run_report(self, payload: ReportRunCreate) -> ReportRun:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="reports.generate",
        )
        scope = await self.require_scope(payload.scope_type, payload.scope_id)
        definition = None
        if payload.report_definition_id is not None:
            definition = await self.session.scalar(
                select(ReportDefinition).where(
                    ReportDefinition.tenant_id == self.context.tenant_id,
                    ReportDefinition.id == payload.report_definition_id,
                    ReportDefinition.is_active.is_(True),
                    or_(ReportDefinition.shared.is_(True), ReportDefinition.owner_user_id == self.context.user_id),
                )
            )
            if definition is None:
                raise HTTPException(status_code=404, detail="Report definition not found or not authorised.")
            if payload.output_format not in set(definition.allowed_formats or []):
                raise HTTPException(status_code=422, detail="The selected report definition does not permit this format.")
            report_type = definition.report_type
        else:
            report_type = payload.report_type
            if report_type not in SUPPORTED_REPORT_TYPES:
                raise HTTPException(status_code=422, detail="Unsupported report type.")
        start = payload.period_start or period_bounds(30)[0]
        end = payload.period_end or period_bounds(30)[1]
        if start > end:
            raise HTTPException(status_code=422, detail="Report period start must not be after the end.")
        run = ReportRun(
            id=uuid4(), tenant_id=self.context.tenant_id,
            report_definition_id=payload.report_definition_id,
            report_type=report_type,
            requested_by_user_id=self.context.user_id,
            scope_type=scope.scope_type, scope_id=scope.scope_id,
            parameters={**payload.parameters, "period_start": start.isoformat(), "period_end": end.isoformat()},
            output_format=payload.output_format, status="running", result_payload={},
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.flush()
        overview = await self.overview(
            requested_type=scope.scope_type,
            requested_id=scope.scope_id,
            days=(end - start).days + 1,
            period_start=start,
            period_end=end,
        )
        payload_data = {"report_type": report_type, "scope": overview["scope"], "period_start": start.isoformat(), "period_end": end.isoformat(), "overview": overview}
        encoded = json.dumps(payload_data, default=str, sort_keys=True).encode("utf-8")
        run.result_payload = json.loads(json.dumps(payload_data, default=str))
        run.result_sha256 = hashlib.sha256(encoded).hexdigest()
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await self.audit.record(action="report.generated", resource_type="report_run", resource_id=run.id, after_state={"report_type": run.report_type, "format": run.output_format})
        await self.session.flush()
        return run

    async def list_report_runs(self, limit: int = 50) -> list[ReportRun]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="reports.generate"
        )
        statement = select(ReportRun).where(ReportRun.tenant_id == self.context.tenant_id)
        if self.context.role_code != "institution_administrator":
            statement = statement.where(ReportRun.requested_by_user_id == self.context.user_id)
        return list(await self.session.scalars(statement.order_by(ReportRun.created_at.desc()).limit(limit)))

    async def list_alerts(
        self, *, status_filter: str = "open", limit: int = 50,
        requested_type: str | None = None, requested_id: UUID | None = None,
    ) -> list[InsightAlert]:
        scope = await self.require_scope(requested_type, requested_id)
        statement = select(InsightAlert).where(InsightAlert.tenant_id == self.context.tenant_id)
        if status_filter:
            statement = statement.where(InsightAlert.status == status_filter)
        if scope.scope_type == "user":
            statement = statement.where(InsightAlert.scope_type == "user", InsightAlert.scope_id == scope.scope_id)
        elif scope.scope_type == "organisational_unit":
            statement = statement.where(
                InsightAlert.scope_type == "organisational_unit",
                InsightAlert.scope_id == scope.scope_id,
            )
        return list(await self.session.scalars(statement.order_by(InsightAlert.detected_at.desc()).limit(limit)))

    async def act_on_alert(self, alert_id: UUID, action: str) -> InsightAlert:
        alert = await self.session.scalar(select(InsightAlert).where(InsightAlert.tenant_id == self.context.tenant_id, InsightAlert.id == alert_id))
        if alert is None:
            raise HTTPException(status_code=404, detail="Insight alert not found.")
        await self.require_scope(alert.scope_type, alert.scope_id)
        now = datetime.now(timezone.utc)
        if action == "acknowledge":
            alert.status = "acknowledged"; alert.acknowledged_by_user_id = self.context.user_id; alert.acknowledged_at = now
        elif action == "resolve":
            alert.status = "resolved"; alert.resolved_by_user_id = self.context.user_id; alert.resolved_at = now
        elif action == "reopen":
            alert.status = "open"; alert.resolved_by_user_id = None; alert.resolved_at = None
        else:
            raise HTTPException(status_code=422, detail="Unsupported alert action.")
        await self.audit.record(action=f"insight_alert.{action}", resource_type="insight_alert", resource_id=alert.id)
        await self.session.flush()
        return alert


class AIUsageGovernanceService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)

    async def resolve_policy(self, scope_type: str = "institution", scope_id: UUID | None = None) -> AIUsagePolicy | None:
        exact = await self.session.scalar(
            select(AIUsagePolicy).where(
                AIUsagePolicy.tenant_id == self.context.tenant_id,
                AIUsagePolicy.is_active.is_(True),
                AIUsagePolicy.scope_type == scope_type,
                AIUsagePolicy.scope_id == scope_id,
            ).order_by(AIUsagePolicy.updated_at.desc())
        )
        if exact:
            return exact
        return await self.session.scalar(
            select(AIUsagePolicy).where(
                AIUsagePolicy.tenant_id == self.context.tenant_id,
                AIUsagePolicy.is_active.is_(True),
                AIUsagePolicy.scope_type == "institution",
                AIUsagePolicy.scope_id.is_(None),
            ).order_by(AIUsagePolicy.updated_at.desc())
        )

    async def current_usage(self) -> dict[str, Decimal | int]:
        start, end = month_bounds()
        row = (await self.session.execute(
            select(
                func.coalesce(func.sum(AIUsageDaily.request_count), 0),
                func.coalesce(func.sum(AIUsageDaily.input_tokens), 0),
                func.coalesce(func.sum(AIUsageDaily.output_tokens), 0),
                func.coalesce(func.sum(AIUsageDaily.estimated_cost), 0),
            ).where(
                AIUsageDaily.tenant_id == self.context.tenant_id,
                AIUsageDaily.usage_date >= start,
                AIUsageDaily.usage_date <= end,
            )
        )).one()
        return {"request_count": int(row[0]), "input_tokens": int(row[1]), "output_tokens": int(row[2]), "estimated_cost": Decimal(str(row[3]))}

    async def preflight(self, classification: TaskClassification) -> AIUsageDecision:
        policy = await self.resolve_policy()
        decision = evaluate_usage_policy(
            policy=policy,
            privacy_classification=classification.privacy_classification.value,
            task_type=classification.task_type.value,
            usage=await self.current_usage(),
        )
        if decision.hard_blocked:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="The institution's governed AI usage limit has been reached.")
        return decision

    async def record_usage(
        self, *, provider: str, model_id: str, task_type: str, status_code: str,
        input_tokens: int | None, output_tokens: int | None, latency_ms: int | None,
        estimated_cost: Decimal | None = None, currency_code: str = "GBP",
    ) -> None:
        """Atomically increment the governed daily ledger under concurrent requests."""

        today = datetime.now(timezone.utc).date()
        values = {
            "id": uuid4(),
            "tenant_id": self.context.tenant_id,
            "usage_date": today,
            "user_id": self.context.user_id,
            "provider": provider,
            "model_id": model_id,
            "role_code": self.context.role_code,
            "task_type": task_type,
            "request_count": 1,
            "successful_count": int(status_code == "completed"),
            "failed_count": int(status_code != "completed"),
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "estimated_cost": Decimal(str(estimated_cost or 0)),
            "currency_code": currency_code,
            "latency_total_ms": int(latency_ms or 0),
        }
        statement = insert(AIUsageDaily).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[
                AIUsageDaily.tenant_id,
                AIUsageDaily.usage_date,
                AIUsageDaily.user_id,
                AIUsageDaily.provider,
                AIUsageDaily.model_id,
                AIUsageDaily.role_code,
                AIUsageDaily.task_type,
            ],
            set_={
                "request_count": AIUsageDaily.request_count + statement.excluded.request_count,
                "successful_count": AIUsageDaily.successful_count + statement.excluded.successful_count,
                "failed_count": AIUsageDaily.failed_count + statement.excluded.failed_count,
                "input_tokens": AIUsageDaily.input_tokens + statement.excluded.input_tokens,
                "output_tokens": AIUsageDaily.output_tokens + statement.excluded.output_tokens,
                "estimated_cost": AIUsageDaily.estimated_cost + statement.excluded.estimated_cost,
                "latency_total_ms": AIUsageDaily.latency_total_ms + statement.excluded.latency_total_ms,
                "currency_code": statement.excluded.currency_code,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def list_policies(self) -> list[AIUsagePolicy]:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="ai_governance.read")
        return list(await self.session.scalars(select(AIUsagePolicy).where(AIUsagePolicy.tenant_id == self.context.tenant_id).order_by(AIUsagePolicy.updated_at.desc())))

    async def create_policy(self, payload: AIUsagePolicyCreate) -> AIUsagePolicy:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="ai_governance.manage")
        if set(payload.allowed_providers) & set(payload.denied_providers):
            raise HTTPException(status_code=422, detail="A provider cannot be both allowed and denied.")
        if payload.scope_type != "institution" and payload.scope_id is None:
            raise HTTPException(status_code=422, detail="A scoped policy requires a scope identifier.")
        policy = AIUsagePolicy(
            id=uuid4(), tenant_id=self.context.tenant_id, name=payload.name,
            scope_type=payload.scope_type, scope_id=payload.scope_id,
            allowed_providers=payload.allowed_providers, denied_providers=payload.denied_providers,
            local_only_privacy_classes=payload.local_only_privacy_classes,
            source_required_for_tasks=payload.source_required_for_tasks,
            monthly_request_limit=payload.monthly_request_limit,
            monthly_input_token_limit=payload.monthly_input_token_limit,
            monthly_output_token_limit=payload.monthly_output_token_limit,
            monthly_cost_limit=payload.monthly_cost_limit,
            currency_code=payload.currency_code.upper(),
            warning_threshold_percent=payload.warning_threshold_percent,
            hard_limit_enabled=payload.hard_limit_enabled,
            is_active=payload.is_active, policy_metadata=payload.policy_metadata,
            created_by_user_id=self.context.user_id,
        )
        self.session.add(policy)
        await self.audit.record(action="ai_usage_policy.created", resource_type="ai_usage_policy", resource_id=policy.id)
        await self.session.flush()
        return policy


class AuditCentreService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)

    async def search_events(
        self, *, start_at: datetime | None, end_at: datetime | None, actor_user_id: UUID | None,
        action: str | None, resource_type: str | None, limit: int,
    ) -> list[AuditEvent]:
        if self.context.role_code != "institution_administrator":
            raise HTTPException(status_code=403, detail="The Audit Centre is restricted to the Institution Administrator role.")
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="audit.centre.read")
        statement = select(AuditEvent).where(AuditEvent.tenant_id == self.context.tenant_id)
        if start_at: statement = statement.where(AuditEvent.occurred_at >= start_at)
        if end_at: statement = statement.where(AuditEvent.occurred_at <= end_at)
        if actor_user_id: statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
        if action: statement = statement.where(AuditEvent.action.ilike(f"%{action.strip()}%"))
        if resource_type: statement = statement.where(AuditEvent.resource_type == resource_type)
        return list(await self.session.scalars(statement.order_by(AuditEvent.occurred_at.desc()).limit(limit)))

    async def security_events(self, *, severity: str | None, limit: int) -> list[SecurityEvent]:
        if self.context.role_code != "institution_administrator":
            raise HTTPException(status_code=403, detail="The Audit Centre is restricted to the Institution Administrator role.")
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="audit.centre.read")
        statement = select(SecurityEvent).where(SecurityEvent.tenant_id == self.context.tenant_id)
        if severity: statement = statement.where(SecurityEvent.severity == severity)
        return list(await self.session.scalars(statement.order_by(SecurityEvent.occurred_at.desc()).limit(limit)))

    async def export(self, payload: AuditExportCreate) -> AuditExportJob:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="audit.export")
        events = await self.search_events(start_at=payload.start_at, end_at=payload.end_at, actor_user_id=payload.actor_user_id, action=payload.action, resource_type=payload.resource_type, limit=5000)
        serialised = [{"id": str(item.id), "occurred_at": item.occurred_at.isoformat(), "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None, "actor_role_code": item.actor_role_code, "action": item.action, "resource_type": item.resource_type, "resource_id": str(item.resource_id) if item.resource_id else None, "correlation_id": item.correlation_id, "metadata": item.metadata_payload} for item in events]
        if payload.output_format == "csv":
            buffer = io.StringIO(); writer = csv.DictWriter(buffer, fieldnames=["id", "occurred_at", "actor_user_id", "actor_role_code", "action", "resource_type", "resource_id", "correlation_id"]); writer.writeheader(); writer.writerows([{key: row[key] for key in writer.fieldnames} for row in serialised])
            result = {"encoding": "utf-8", "content": buffer.getvalue()}
        else:
            result = {"events": serialised}
        digest = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
        job = AuditExportJob(
            id=uuid4(), tenant_id=self.context.tenant_id, requested_by_user_id=self.context.user_id,
            filters=payload.model_dump(mode="json"), output_format=payload.output_format,
            status="completed", record_count=len(events), result_payload=result,
            result_sha256=digest, generated_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        await self.audit.record(action="audit.export.generated", resource_type="audit_export_job", resource_id=job.id, after_state={"record_count": len(events), "format": payload.output_format})
        await self.session.flush()
        return job


class PlatformSettingsService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)

    async def list_settings(self, category: str | None = None) -> list[PlatformSetting]:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="settings.read")
        statement = select(PlatformSetting).where(PlatformSetting.tenant_id == self.context.tenant_id)
        if category: statement = statement.where(PlatformSetting.category == category)
        return list(await self.session.scalars(statement.order_by(PlatformSetting.category, PlatformSetting.setting_key)))

    async def upsert(self, category: str, key: str, payload: PlatformSettingUpsert) -> PlatformSetting:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="settings.manage")
        if payload.scope_type != "institution" and payload.scope_id is None:
            raise HTTPException(status_code=422, detail="A scoped setting requires a scope identifier.")
        try:
            secret_reference, safe_value = validate_setting_key_and_value(category, key, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        setting = await self.session.scalar(select(PlatformSetting).where(
            PlatformSetting.tenant_id == self.context.tenant_id,
            PlatformSetting.scope_type == payload.scope_type,
            PlatformSetting.scope_id == payload.scope_id,
            PlatformSetting.category == category,
            PlatformSetting.setting_key == key,
        ))
        before = None
        if setting is None:
            setting = PlatformSetting(
                id=uuid4(), tenant_id=self.context.tenant_id,
                scope_type=payload.scope_type, scope_id=payload.scope_id,
                category=category, setting_key=key, value=safe_value,
                value_type=payload.value_type, description=payload.description,
                secret_reference_only=secret_reference, locked=False,
                version_number=1, updated_by_user_id=self.context.user_id,
            )
            self.session.add(setting)
        else:
            if setting.locked:
                raise HTTPException(status_code=409, detail="This platform setting is locked.")
            before = {"value": setting.value, "version_number": setting.version_number}
            setting.value = safe_value; setting.value_type = payload.value_type; setting.description = payload.description
            setting.secret_reference_only = secret_reference; setting.version_number += 1; setting.updated_by_user_id = self.context.user_id
        await self.audit.record(action="platform_setting.updated", resource_type="platform_setting", resource_id=setting.id, before_state=before, after_state={"category": category, "key": key, "version_number": setting.version_number, "secret_reference_only": secret_reference})
        await self.session.flush()
        return setting
