from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AcademicPeriod,
    LearningOutcome,
    LecturerAssignment,
    Module,
    ModuleContextSnapshot,
    ModuleOffering,
    Programme,
    ProgrammeModule,
    Qualification,
)

from ..core.request_context import RequestContext
from .authorization import AuthorizationService


@dataclass(frozen=True, slots=True)
class ModuleContextBundle:
    module_id: UUID
    module_offering_id: UUID
    module_code: str
    module_name: str
    offering_code: str
    academic_period_label: str
    qualification_level: str | None
    delivery_mode: str | None
    default_contact_hours: int | None
    learning_outcomes: list[dict]
    programmes: list[dict]
    module_attributes: dict

    def as_dict(self) -> dict:
        return {
            "module_id": str(self.module_id),
            "module_offering_id": str(self.module_offering_id),
            "module_code": self.module_code,
            "module_name": self.module_name,
            "offering_code": self.offering_code,
            "academic_period": self.academic_period_label,
            "qualification_level": self.qualification_level,
            "delivery_mode": self.delivery_mode,
            "default_contact_hours": self.default_contact_hours,
            "learning_outcomes": self.learning_outcomes,
            "programmes": self.programmes,
            "module_attributes": self.module_attributes,
        }

    def prompt_text(self) -> str:
        outcomes = "\n".join(
            f"- {row['code']}: {row['statement']}" for row in self.learning_outcomes
        ) or "- No approved learning outcomes are currently recorded."
        programmes = ", ".join(row["name"] for row in self.programmes) or "Not linked"
        return (
            f"Module: {self.module_code} — {self.module_name}\n"
            f"Offering: {self.offering_code}; period: {self.academic_period_label}; "
            f"delivery: {self.delivery_mode or 'not specified'}\n"
            f"Level: {self.qualification_level or 'not specified'}; programmes: {programmes}\n"
            f"Learning outcomes:\n{outcomes}"
        )


class ModuleContextService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)

    async def list_available(self) -> list[ModuleContextBundle]:
        now = datetime.now(timezone.utc)
        statement = (
            select(ModuleOffering.id)
            .join(Module, Module.id == ModuleOffering.module_id)
            .where(ModuleOffering.tenant_id == self.context.tenant_id)
            .order_by(Module.code, ModuleOffering.offering_code)
        )
        if self.context.role_code == "lecturer":
            statement = statement.join(
                LecturerAssignment, LecturerAssignment.module_offering_id == ModuleOffering.id
            ).where(
                LecturerAssignment.tenant_id == self.context.tenant_id,
                LecturerAssignment.user_id == self.context.user_id,
                LecturerAssignment.status == "active",
                LecturerAssignment.valid_from <= now,
                or_(LecturerAssignment.valid_until.is_(None), LecturerAssignment.valid_until > now),
            )
        ids = list(await self.session.scalars(statement.limit(200)))
        result: list[ModuleContextBundle] = []
        for offering_id in ids:
            try:
                result.append(await self.require(offering_id))
            except HTTPException:
                continue
        return result

    async def require(self, module_offering_id: UUID) -> ModuleContextBundle:
        row = (
            await self.session.execute(
                select(ModuleOffering, Module, AcademicPeriod)
                .join(Module, Module.id == ModuleOffering.module_id)
                .join(AcademicPeriod, AcademicPeriod.id == ModuleOffering.academic_period_id)
                .where(
                    ModuleOffering.tenant_id == self.context.tenant_id,
                    Module.id == ModuleOffering.module_id,
                    ModuleOffering.id == module_offering_id,
                )
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module offering not found.")
        offering, module, period = row
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="academic.read",
            scope_type="module_offering",
            scope_id=offering.id,
        )
        if self.context.role_code == "lecturer":
            now = datetime.now(timezone.utc)
            assignment = await self.session.scalar(
                select(LecturerAssignment.id).where(
                    LecturerAssignment.tenant_id == self.context.tenant_id,
                    LecturerAssignment.user_id == self.context.user_id,
                    LecturerAssignment.module_offering_id == offering.id,
                    LecturerAssignment.status == "active",
                    LecturerAssignment.valid_from <= now,
                    or_(LecturerAssignment.valid_until.is_(None), LecturerAssignment.valid_until > now),
                )
            )
            if assignment is None:
                raise HTTPException(status_code=403, detail="This module is not assigned to the active lecturer.")

        outcomes = [
            {"code": row.outcome_code, "statement": row.statement, "cognitive_level": row.cognitive_level}
            for row in await self.session.scalars(
                select(LearningOutcome)
                .where(
                    LearningOutcome.tenant_id == self.context.tenant_id,
                    LearningOutcome.module_id == module.id,
                )
                .order_by(LearningOutcome.sequence_order, LearningOutcome.outcome_code)
            )
        ]
        programme_rows = (
            await self.session.execute(
                select(Programme, Qualification)
                .join(ProgrammeModule, ProgrammeModule.programme_id == Programme.id)
                .outerjoin(Qualification, Qualification.id == Programme.qualification_id)
                .where(
                    Programme.tenant_id == self.context.tenant_id,
                    ProgrammeModule.tenant_id == self.context.tenant_id,
                    ProgrammeModule.module_id == module.id,
                )
            )
        ).all()
        programmes = [
            {
                "id": str(programme.id),
                "code": programme.code,
                "name": programme.name,
                "qualification": qualification.name if qualification else None,
                "qualification_level": qualification.level_value if qualification else None,
            }
            for programme, qualification in programme_rows
        ]
        level = module.level_value or next(
            (row["qualification_level"] for row in programmes if row["qualification_level"]), None
        )
        return ModuleContextBundle(
            module_id=module.id,
            module_offering_id=offering.id,
            module_code=module.code,
            module_name=module.name,
            offering_code=offering.offering_code,
            academic_period_label=f"{period.code} — {period.name}",
            qualification_level=level,
            delivery_mode=offering.delivery_mode or module.attributes.get("delivery_mode"),
            default_contact_hours=module.default_contact_hours,
            learning_outcomes=outcomes,
            programmes=programmes,
            module_attributes=module.attributes,
        )

    async def persist_snapshot(
        self,
        *,
        ai_request_id: UUID,
        conversation_id: UUID,
        bundle: ModuleContextBundle,
    ) -> ModuleContextSnapshot:
        row = ModuleContextSnapshot(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            ai_request_id=ai_request_id,
            conversation_id=conversation_id,
            requested_by_user_id=self.context.user_id,
            module_id=bundle.module_id,
            module_offering_id=bundle.module_offering_id,
            context_source="selected",
            module_code=bundle.module_code,
            module_name=bundle.module_name,
            offering_code=bundle.offering_code,
            academic_period_label=bundle.academic_period_label,
            qualification_level=bundle.qualification_level,
            delivery_mode=bundle.delivery_mode,
            default_contact_hours=bundle.default_contact_hours,
            learning_outcomes=bundle.learning_outcomes,
            programme_context=bundle.programmes,
            module_attributes=bundle.module_attributes,
        )
        self.session.add(row)
        await self.session.flush()
        return row
