from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import EvaluationCampaign, EvaluationResponse, UserFeedback

from ..core.request_context import RequestContext
from ..schemas.completion import EvaluationCampaignCreate, EvaluationResponseCreate, UserFeedbackCreate
from .audit import AuditService


class EvaluationCaptureService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)

    async def create_feedback(self, payload: UserFeedbackCreate) -> UserFeedback:
        item = UserFeedback(
            id=uuid4(), tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            target_type=payload.target_type, target_id=payload.target_id,
            rating=payload.rating, feedback_type=payload.feedback_type,
            comment=payload.comment, issue_codes=payload.issue_codes,
            consent_for_research=payload.consent_for_research,
        )
        self.session.add(item); await self.session.flush()
        await self.audit.record(
            action="evaluation.feedback_submitted", resource_type="user_feedback", resource_id=item.id,
            after_state={"target_type": item.target_type, "rating": item.rating, "issue_codes": item.issue_codes},
        )
        return item

    async def create_campaign(self, payload: EvaluationCampaignCreate) -> EvaluationCampaign:
        if await self.session.scalar(select(EvaluationCampaign.id).where(
            EvaluationCampaign.tenant_id == self.context.tenant_id,
            EvaluationCampaign.code == payload.code,
        )):
            raise HTTPException(status_code=409, detail="Evaluation campaign code already exists.")
        item = EvaluationCampaign(
            id=uuid4(), tenant_id=self.context.tenant_id, code=payload.code,
            name=payload.name, description=payload.description, status="draft",
            starts_at=payload.starts_at, ends_at=payload.ends_at,
            instrument_definition=payload.instrument_definition,
            created_by_user_id=self.context.user_id,
        )
        self.session.add(item); await self.session.flush()
        return item

    async def submit_response(self, campaign_id, payload: EvaluationResponseCreate) -> EvaluationResponse:
        campaign = await self.session.scalar(select(EvaluationCampaign).where(
            EvaluationCampaign.tenant_id == self.context.tenant_id,
            EvaluationCampaign.id == campaign_id,
        ))
        if campaign is None:
            raise HTTPException(status_code=404, detail="Evaluation campaign was not found.")
        scores = self._score(campaign.instrument_definition, payload.responses)
        item = EvaluationResponse(
            id=uuid4(), tenant_id=self.context.tenant_id, campaign_id=campaign.id,
            participant_user_id=self.context.user_id, task_reference=payload.task_reference,
            role_code=self.context.role_code, responses=payload.responses,
            computed_scores=scores, submitted_at=datetime.now(timezone.utc),
        )
        self.session.add(item); await self.session.flush()
        return item

    @staticmethod
    def _score(instrument: dict, responses: dict) -> dict:
        dimensions = instrument.get("dimensions") or []
        result: dict[str, float] = {}
        for dimension in dimensions:
            code = dimension.get("code")
            items = dimension.get("items") or []
            values = [float(responses[item]) for item in items if item in responses and isinstance(responses[item], (int, float))]
            if code and values:
                result[str(code)] = round(sum(values) / len(values), 3)
        return result
