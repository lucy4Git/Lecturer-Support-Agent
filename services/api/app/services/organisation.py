from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    OrganisationalUnit,
    OrganisationalUnitClosure,
    OrganisationalUnitType,
    TenantSetting,
    TenantTerminology,
)

from ..core.request_context import RequestContext
from ..schemas.organisation import (
    InstitutionSettingUpsert,
    OrganisationalUnitCreate,
    OrganisationalUnitMove,
    OrganisationalUnitTypeCreate,
    OrganisationalUnitUpdate,
    TerminologyUpsert,
)
from .audit import AuditService


class OrganisationService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)

    async def create_unit_type(
        self, payload: OrganisationalUnitTypeCreate
    ) -> OrganisationalUnitType:
        existing = await self.session.scalar(
            select(OrganisationalUnitType).where(
                OrganisationalUnitType.tenant_id == self.context.tenant_id,
                OrganisationalUnitType.code == payload.code,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Organisational unit type already exists.")
        unit_type = OrganisationalUnitType(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            **payload.model_dump(),
        )
        self.session.add(unit_type)
        await self.session.flush()
        await self.audit.record(
            action="institution.unit_type_created",
            resource_type="organisational_unit_type",
            resource_id=unit_type.id,
            after_state={"code": unit_type.code, "level_order": unit_type.level_order},
        )
        return unit_type

    async def create_unit(self, payload: OrganisationalUnitCreate) -> OrganisationalUnit:
        unit_type = await self.session.scalar(
            select(OrganisationalUnitType).where(
                OrganisationalUnitType.tenant_id == self.context.tenant_id,
                OrganisationalUnitType.id == payload.unit_type_id,
            )
        )
        if unit_type is None:
            raise HTTPException(status_code=404, detail="Organisational unit type was not found.")
        parent: OrganisationalUnit | None = None
        if payload.parent_id:
            parent = await self._get_unit(payload.parent_id)
            parent_type = await self.session.get(OrganisationalUnitType, parent.unit_type_id)
            if parent_type and not parent_type.allows_children:
                raise HTTPException(status_code=409, detail="The selected parent does not allow children.")
        duplicate = await self.session.scalar(
            select(OrganisationalUnit.id).where(
                OrganisationalUnit.tenant_id == self.context.tenant_id,
                OrganisationalUnit.code == payload.code,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Organisational unit code already exists.")

        unit_id = uuid4()
        path = f"{parent.materialized_path}/{unit_id}" if parent else str(unit_id)
        unit = OrganisationalUnit(
            id=unit_id,
            tenant_id=self.context.tenant_id,
            unit_type_id=payload.unit_type_id,
            parent_id=payload.parent_id,
            code=payload.code,
            name=payload.name,
            short_name=payload.short_name,
            materialized_path=path,
            depth=(parent.depth + 1) if parent else 0,
            is_active=True,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            attributes=payload.attributes,
        )
        self.session.add(unit)
        await self.session.flush()
        self.session.add(
            OrganisationalUnitClosure(
                tenant_id=self.context.tenant_id,
                ancestor_id=unit.id,
                descendant_id=unit.id,
                depth=0,
            )
        )
        if parent:
            ancestors = (
                await self.session.scalars(
                    select(OrganisationalUnitClosure).where(
                        OrganisationalUnitClosure.tenant_id == self.context.tenant_id,
                        OrganisationalUnitClosure.descendant_id == parent.id,
                    )
                )
            ).all()
            for ancestor in ancestors:
                self.session.add(
                    OrganisationalUnitClosure(
                        tenant_id=self.context.tenant_id,
                        ancestor_id=ancestor.ancestor_id,
                        descendant_id=unit.id,
                        depth=ancestor.depth + 1,
                    )
                )
        await self.audit.record(
            action="institution.org_unit_created",
            resource_type="organisational_unit",
            resource_id=unit.id,
            after_state={
                "code": unit.code,
                "name": unit.name,
                "parent_id": str(unit.parent_id) if unit.parent_id else None,
            },
        )
        return unit

    async def update_unit(
        self, unit_id: UUID, payload: OrganisationalUnitUpdate
    ) -> OrganisationalUnit:
        unit = await self._get_unit(unit_id, for_update=True)
        before = {
            "name": unit.name,
            "short_name": unit.short_name,
            "is_active": unit.is_active,
            "valid_to": unit.valid_to.isoformat() if unit.valid_to else None,
            "attributes": unit.attributes,
        }
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(unit, key, value)
        await self.audit.record(
            action="institution.org_unit_updated",
            resource_type="organisational_unit",
            resource_id=unit.id,
            before_state=before,
            after_state=updates,
        )
        return unit

    async def move_unit(
        self, unit_id: UUID, payload: OrganisationalUnitMove
    ) -> OrganisationalUnit:
        unit = await self._get_unit(unit_id, for_update=True)
        old_parent_id = unit.parent_id
        old_prefix = unit.materialized_path
        new_parent: OrganisationalUnit | None = None
        if payload.new_parent_id:
            new_parent = await self._get_unit(payload.new_parent_id, for_update=True)

        subtree_rows = (
            await self.session.scalars(
                select(OrganisationalUnitClosure).where(
                    OrganisationalUnitClosure.tenant_id == self.context.tenant_id,
                    OrganisationalUnitClosure.ancestor_id == unit.id,
                )
            )
        ).all()
        subtree_depth = {item.descendant_id: item.depth for item in subtree_rows}
        if new_parent and new_parent.id in subtree_depth:
            raise HTTPException(status_code=409, detail="An organisational unit cannot move below itself.")

        subtree_ids = set(subtree_depth)
        await self.session.execute(
            delete(OrganisationalUnitClosure).where(
                OrganisationalUnitClosure.tenant_id == self.context.tenant_id,
                OrganisationalUnitClosure.descendant_id.in_(subtree_ids),
                OrganisationalUnitClosure.ancestor_id.not_in(subtree_ids),
            )
        )
        if new_parent:
            new_ancestors = (
                await self.session.scalars(
                    select(OrganisationalUnitClosure).where(
                        OrganisationalUnitClosure.tenant_id == self.context.tenant_id,
                        OrganisationalUnitClosure.descendant_id == new_parent.id,
                    )
                )
            ).all()
            for parent_ancestor in new_ancestors:
                for descendant_id, depth_from_unit in subtree_depth.items():
                    self.session.add(
                        OrganisationalUnitClosure(
                            tenant_id=self.context.tenant_id,
                            ancestor_id=parent_ancestor.ancestor_id,
                            descendant_id=descendant_id,
                            depth=parent_ancestor.depth + 1 + depth_from_unit,
                        )
                    )

        units = (
            await self.session.scalars(
                select(OrganisationalUnit).where(
                    OrganisationalUnit.tenant_id == self.context.tenant_id,
                    OrganisationalUnit.id.in_(subtree_ids),
                )
            )
        ).all()
        new_prefix = f"{new_parent.materialized_path}/{unit.id}" if new_parent else str(unit.id)
        new_base_depth = (new_parent.depth + 1) if new_parent else 0
        for descendant in units:
            suffix = descendant.materialized_path[len(old_prefix) :]
            descendant.materialized_path = f"{new_prefix}{suffix}"
            descendant.depth = new_base_depth + subtree_depth[descendant.id]
        unit.parent_id = payload.new_parent_id
        await self.audit.record(
            action="institution.org_unit_moved",
            resource_type="organisational_unit",
            resource_id=unit.id,
            before_state={"parent_id": str(old_parent_id) if old_parent_id else None},
            after_state={
                "parent_id": str(payload.new_parent_id) if payload.new_parent_id else None,
                "reason": payload.reason,
            },
        )
        return unit

    async def list_units(self, *, active_only: bool = True) -> list[OrganisationalUnit]:
        statement = select(OrganisationalUnit).where(
            OrganisationalUnit.tenant_id == self.context.tenant_id
        )
        if active_only:
            statement = statement.where(OrganisationalUnit.is_active.is_(True))
        statement = statement.order_by(
            OrganisationalUnit.materialized_path, OrganisationalUnit.name
        )
        return list((await self.session.scalars(statement)).all())

    async def upsert_terminology(self, payload: TerminologyUpsert) -> TenantTerminology:
        item = await self.session.scalar(
            select(TenantTerminology).where(
                TenantTerminology.tenant_id == self.context.tenant_id,
                TenantTerminology.term_key == payload.term_key,
            )
        )
        if item is None:
            item = TenantTerminology(
                id=uuid4(), tenant_id=self.context.tenant_id, **payload.model_dump()
            )
            self.session.add(item)
        else:
            item.singular_value = payload.singular_value
            item.plural_value = payload.plural_value
            item.locale = payload.locale
        await self.session.flush()
        await self.audit.record(
            action="institution.terminology_upserted",
            resource_type="tenant_terminology",
            resource_id=item.id,
            after_state=payload.model_dump(),
        )
        return item

    async def upsert_setting(self, payload: InstitutionSettingUpsert) -> TenantSetting:
        if payload.is_secret_reference and "value" in payload.setting_value:
            raise HTTPException(
                status_code=400,
                detail="Secret settings must store only an external secret reference, not a value.",
            )
        item = await self.session.scalar(
            select(TenantSetting).where(
                TenantSetting.tenant_id == self.context.tenant_id,
                TenantSetting.setting_key == payload.setting_key,
            )
        )
        if item is None:
            item = TenantSetting(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                setting_key=payload.setting_key,
                setting_value=payload.setting_value,
                is_secret_reference=payload.is_secret_reference,
            )
            self.session.add(item)
        else:
            item.setting_value = payload.setting_value
            item.is_secret_reference = payload.is_secret_reference
        await self.session.flush()
        await self.audit.record(
            action="institution.setting_upserted",
            resource_type="tenant_setting",
            resource_id=item.id,
            after_state={
                "setting_key": item.setting_key,
                "is_secret_reference": item.is_secret_reference,
            },
        )
        return item

    async def _get_unit(
        self, unit_id: UUID, *, for_update: bool = False
    ) -> OrganisationalUnit:
        statement = select(OrganisationalUnit).where(
            OrganisationalUnit.tenant_id == self.context.tenant_id,
            OrganisationalUnit.id == unit_id,
        )
        if for_update:
            statement = statement.with_for_update()
        unit = await self.session.scalar(statement)
        if unit is None:
            raise HTTPException(status_code=404, detail="Organisational unit was not found.")
        return unit
