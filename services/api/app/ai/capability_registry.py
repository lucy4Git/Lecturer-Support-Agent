"""Hidden capability registry.

Classifies natural-language prompts into READ or WRITE capabilities and
returns structured data for the orchestrator — never exposing capability
names, selectors, or internal routing to the user.

READ  → query real DB → inject data as `institutional_context`
WRITE → resolve entities → store server-side pending action → return token
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..core.request_context import RequestContext


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class CapabilityResult:
    matched: bool = False
    institutional_context: str = ""
    pending_action_token: str | None = None   # non-None → WRITE capability queued
    pending_action_label: str = ""
    pending_action_details: list[dict] = field(default_factory=list)
    extra_context: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

_WORKLOAD_RE = re.compile(
    r"\b(workload|work load|work-load|teaching load|contact hours|"
    r"show workload|my workload|lecturer workload|"
    r"who is assigned|assigned modules?|module assignments?|"
    r"department workload|staff workload|overloaded|underloaded|"
    r"no lecturer|unassigned module|modules? without)\b",
    re.IGNORECASE,
)

_ASSIGN_LECTURER_RE = re.compile(
    r"\b(assign|allocate|appoint)\b.{0,100}\b(lecturer|staff)\b",
    re.IGNORECASE,
)

_STRUCTURE_QUERY_RE = re.compile(
    r"\b(show|list|display|what are).{0,60}\b(institution|faculty|faculties|"
    r"department|school|programme|module|structure|units?)\b",
    re.IGNORECASE,
)

_CREATE_UNIT_RE = re.compile(
    r"\bcreate\b.{0,80}\b(department|faculty|school|division|unit|centre)\b",
    re.IGNORECASE,
)

_MY_MODULES_RE = re.compile(
    r"\b(my modules?|modules? i (coordinate|teach|am assigned|manage)|"
    r"show my modules?|list my modules?)\b",
    re.IGNORECASE,
)

_MY_REVIEWS_RE = re.compile(
    r"\b(my (moderation|review|assigned review|tasks?)|"
    r"show (my )?(moderation|review|assigned))\b",
    re.IGNORECASE,
)

_CONFIRM_RE = re.compile(r"^__confirm__([0-9a-f-]{36})$")
_CANCEL_RE  = re.compile(r"^__cancel__([0-9a-f-]{36})$")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """Maps user intent → READ data or WRITE pending action."""

    def __init__(self, session: "AsyncSession", context: "RequestContext") -> None:
        self._session = session
        self._context = context

    async def resolve(self, prompt: str) -> CapabilityResult:
        role = self._context.role_code
        prompt_stripped = prompt.strip()

        # Confirmation / cancellation intercepts
        m = _CONFIRM_RE.match(prompt_stripped)
        if m:
            return await self._execute_pending(m.group(1))

        m = _CANCEL_RE.match(prompt_stripped)
        if m:
            return await self._cancel_pending(m.group(1))

        # READ capabilities
        if _WORKLOAD_RE.search(prompt):
            if role in ("head_of_department", "module_coordinator", "programme_coordinator"):
                return await self._read_workload()

        if _MY_MODULES_RE.search(prompt):
            if role in ("module_coordinator", "programme_coordinator", "lecturer"):
                return await self._read_my_modules()

        if _STRUCTURE_QUERY_RE.search(prompt):
            if role in ("institution_administrator", "head_of_department"):
                return await self._read_structure()

        if _MY_REVIEWS_RE.search(prompt):
            if role in ("internal_moderator", "external_moderator", "external_reviewer"):
                return await self._read_my_reviews()

        # WRITE capabilities
        if _ASSIGN_LECTURER_RE.search(prompt):
            if role == "head_of_department":
                return await self._write_assign_lecturer(prompt)

        if _CREATE_UNIT_RE.search(prompt):
            if role == "institution_administrator":
                return await self._write_create_unit(prompt)

        return CapabilityResult(matched=False)

    # ------------------------------------------------------------------
    # Pending action execution
    # ------------------------------------------------------------------

    async def _execute_pending(self, token: str) -> CapabilityResult:
        from ..services.pending_actions import PendingActionStore
        store = PendingActionStore.get()
        action = await store.claim(
            token=token,
            user_id=self._context.user_id,
            tenant_id=self._context.tenant_id,
        )
        if action is None:
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    "SYSTEM: The confirmation token is invalid, expired, or was already used. "
                    "Inform the user that the action could not be completed and they should try again."
                ),
            )

        if action.action_type == "assign_lecturer":
            return await self._exec_assign_lecturer(action.payload)
        if action.action_type == "create_org_unit":
            return await self._exec_create_org_unit(action.payload)

        return CapabilityResult(
            matched=True,
            institutional_context=(
                f"SYSTEM: Unknown pending action type '{action.action_type}'. "
                "Inform the user that this action is not yet executable from the chat."
            ),
        )

    async def _cancel_pending(self, token: str) -> CapabilityResult:
        from ..services.pending_actions import PendingActionStore
        store = PendingActionStore.get()
        ok = await store.cancel(
            token=token,
            user_id=self._context.user_id,
            tenant_id=self._context.tenant_id,
        )
        return CapabilityResult(
            matched=True,
            institutional_context=(
                "SYSTEM: The action was cancelled and NO database changes were made. "
                "Inform the user clearly that the operation was cancelled."
                if ok else
                "SYSTEM: Cancel token not found — the action may have already expired. "
                "Inform the user that no changes were made."
            ),
        )

    # ------------------------------------------------------------------
    # READ: workload
    # ------------------------------------------------------------------

    async def _read_workload(self) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.academics import Module, ModuleOffering, LecturerAssignment
        from services.database.models.identity import User

        try:
            rows = list(await self._session.execute(
                select(
                    Module.code,
                    Module.name,
                    Module.credit_value,
                    Module.default_contact_hours,
                    User.display_name,
                    User.email,
                    LecturerAssignment.workload_percentage,
                )
                .join(ModuleOffering, ModuleOffering.module_id == Module.id)
                .join(
                    LecturerAssignment,
                    (LecturerAssignment.module_offering_id == ModuleOffering.id)
                    & (LecturerAssignment.tenant_id == self._context.tenant_id)
                    & (LecturerAssignment.status == "active"),
                    isouter=True,
                )
                .join(User, User.id == LecturerAssignment.user_id, isouter=True)
                .where(
                    Module.tenant_id == self._context.tenant_id,
                    ModuleOffering.tenant_id == self._context.tenant_id,
                )
                .distinct()
                .order_by(Module.code)
                .limit(80)
            ))

            if not rows:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        "REAL DATABASE DATA — WORKLOAD QUERY:\n"
                        "No module offerings found for this institution. "
                        "Advise the user that modules may not be configured for the current period."
                    ),
                )

            by_lecturer: dict[str, list[str]] = {}
            unassigned: list[str] = []

            for code, name, credits, hrs, display_name, email, wp in rows:
                info = f"{code} — {name}  (credits: {credits or '?'}, contact hrs/wk: {hrs or '?'})"
                if display_name:
                    pct = f", workload: {wp}%" if wp else ""
                    by_lecturer.setdefault(f"{display_name} <{email}>", []).append(f"{info}{pct}")
                else:
                    unassigned.append(info)

            lines = [
                "REAL DATABASE DATA — LECTURER WORKLOAD",
                f"Tenant: {self._context.tenant_id}",
                "",
            ]
            if by_lecturer:
                lines.append("ASSIGNED MODULES BY LECTURER:")
                for lecturer, modules in sorted(by_lecturer.items()):
                    lines.append(f"\n  {lecturer}")
                    for m in modules:
                        lines.append(f"    • {m}")
            if unassigned:
                lines.append("\nUNASSIGNED MODULES (no active lecturer):")
                for m in unassigned:
                    lines.append(f"  • {m}")
            lines.append(
                "\nINSTRUCTION: Present as structured table. "
                "Do NOT invent any data. Flag unassigned modules as requiring action."
            )
            return CapabilityResult(matched=True, institutional_context="\n".join(lines))

        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=f"WORKLOAD DATA ERROR: {exc}. Inform user to retry.",
            )

    # ------------------------------------------------------------------
    # READ: structure
    # ------------------------------------------------------------------

    async def _read_structure(self) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models import OrganisationalUnit

        try:
            units = list(await self._session.scalars(
                select(OrganisationalUnit)
                .where(OrganisationalUnit.tenant_id == self._context.tenant_id)
                .order_by(OrganisationalUnit.materialized_path)
                .limit(100)
            ))
            if not units:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        "REAL DATABASE DATA — STRUCTURE QUERY:\n"
                        "No organisational units found for this institution."
                    ),
                )
            lines = [
                "REAL DATABASE DATA — INSTITUTIONAL STRUCTURE",
                f"Tenant: {self._context.tenant_id}",
                "",
            ]
            for u in units:
                depth = u.materialized_path.count("/")
                indent = "  " * depth
                lines.append(f"{indent}• {u.code}: {u.name}")
            lines.append(
                "\nINSTRUCTION: Present as a clear hierarchy. Do not fabricate units."
            )
            return CapabilityResult(matched=True, institutional_context="\n".join(lines))

        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=f"STRUCTURE DATA ERROR: {exc}. Inform user to retry.",
            )

    # ------------------------------------------------------------------
    # READ: coordinator/lecturer modules
    # ------------------------------------------------------------------

    async def _read_my_modules(self) -> CapabilityResult:
        from sqlalchemy import select, or_
        from datetime import date
        from services.database.models.academics import (
            Module, ModuleOffering, LecturerAssignment, CoordinatorAssignment,
        )

        try:
            now_dt = datetime.now(timezone.utc)
            now_d  = date.today()
            uid = self._context.user_id
            tid = self._context.tenant_id

            # Lecturer assignments
            lec_rows = list(await self._session.execute(
                select(Module.code, Module.name)
                .join(ModuleOffering, ModuleOffering.module_id == Module.id)
                .join(LecturerAssignment,
                      (LecturerAssignment.module_offering_id == ModuleOffering.id)
                      & (LecturerAssignment.user_id == uid)
                      & (LecturerAssignment.tenant_id == tid)
                      & (LecturerAssignment.status == "active"))
                .where(Module.tenant_id == tid, ModuleOffering.tenant_id == tid)
                .distinct().limit(30)
            ))

            # Coordinator assignments
            coord_rows = list(await self._session.execute(
                select(Module.code, Module.name)
                .join(CoordinatorAssignment,
                      (CoordinatorAssignment.target_id == Module.id)
                      & (CoordinatorAssignment.user_id == uid)
                      & (CoordinatorAssignment.tenant_id == tid)
                      & (CoordinatorAssignment.status == "active"))
                .where(Module.tenant_id == tid)
                .distinct().limit(30)
            ))

            all_modules = {(r[0], r[1]) for r in [*lec_rows, *coord_rows]}

            if not all_modules:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        "REAL DATABASE DATA — MY MODULES:\n"
                        "No modules currently assigned to you in the database."
                    ),
                )

            lines = [
                "REAL DATABASE DATA — YOUR ASSIGNED MODULES",
                f"User: {uid} | Tenant: {tid}",
                "",
            ]
            for code, name in sorted(all_modules):
                lines.append(f"  • {code} — {name}")
            lines.append(
                "\nINSTRUCTION: List these modules. Do not fabricate additional modules."
            )
            return CapabilityResult(matched=True, institutional_context="\n".join(lines))

        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=f"MODULES DATA ERROR: {exc}. Inform user to retry.",
            )

    # ------------------------------------------------------------------
    # READ: moderation/review tasks
    # ------------------------------------------------------------------

    async def _read_my_reviews(self) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.external_access import AssignedReviewTask, ExternalAccessGrant

        try:
            uid = self._context.user_id
            tid = self._context.tenant_id
            role = self._context.role_code

            tasks = list(await self._session.scalars(
                select(AssignedReviewTask)
                .where(
                    AssignedReviewTask.tenant_id == tid,
                    AssignedReviewTask.assigned_user_id == uid,
                    AssignedReviewTask.status.in_(["assigned", "accepted", "in_progress"]),
                )
                .order_by(AssignedReviewTask.created_at.desc())
                .limit(20)
            ))

            if not tasks:
                lines = [
                    "REAL DATABASE DATA — YOUR REVIEW TASKS",
                    f"User: {uid} | Role: {role}",
                    "",
                    "No active review tasks currently assigned to you.",
                ]
            else:
                lines = [
                    "REAL DATABASE DATA — YOUR ASSIGNED REVIEW TASKS",
                    f"User: {uid} | Role: {role}",
                    "",
                ]
                for t in tasks:
                    lines.append(
                        f"  • Task {t.id} | Type: {t.task_type} | "
                        f"Status: {t.status} | Created: {t.created_at.date()}"
                    )

            lines.append(
                "\nINSTRUCTION: List these review tasks. Do not fabricate additional assignments."
            )
            return CapabilityResult(matched=True, institutional_context="\n".join(lines))

        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=f"REVIEW DATA ERROR: {exc}. Inform user to retry.",
            )

    # ------------------------------------------------------------------
    # WRITE: assign lecturer (pending confirmation)
    # ------------------------------------------------------------------

    async def _write_assign_lecturer(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.academics import Module, ModuleOffering, LecturerAssignment
        from services.database.models.identity import User, Membership

        try:
            tid = self._context.tenant_id

            # Fetch lecturers in this tenant via Membership join
            user_rows = list(await self._session.execute(
                select(User.id, User.display_name, User.email)
                .join(Membership, (Membership.user_id == User.id) & (Membership.tenant_id == tid))
                .where(User.is_active.is_(True))
                .order_by(User.display_name)
                .limit(40)
            ))

            unassigned_rows = list(await self._session.execute(
                select(Module.code, Module.name, ModuleOffering.id)
                .join(ModuleOffering, ModuleOffering.module_id == Module.id)
                .outerjoin(
                    LecturerAssignment,
                    (LecturerAssignment.module_offering_id == ModuleOffering.id)
                    & (LecturerAssignment.tenant_id == tid)
                    & (LecturerAssignment.status == "active"),
                )
                .where(
                    Module.tenant_id == tid,
                    ModuleOffering.tenant_id == tid,
                    LecturerAssignment.id.is_(None),
                )
                .distinct().limit(30)
            ))

            user_list = "\n".join(f"  [{uid}] {name} ({email})" for uid, name, email in user_rows) or "  (no users)"
            mod_list = "\n".join(
                f"  [{r[2]}] {r[0]} — {r[1]}" for r in unassigned_rows
            ) or "  (all modules assigned)"

            return CapabilityResult(
                matched=True,
                institutional_context=(
                    "WRITE CAPABILITY — LECTURER ASSIGNMENT\n"
                    "The LLM must NOT perform the assignment. It must build a confirmation card.\n\n"
                    f"Users in institution (ID | name | email):\n{user_list}\n\n"
                    f"Unassigned module offerings (offering_id | code — name):\n{mod_list}\n\n"
                    "INSTRUCTION:\n"
                    "1. Identify the lecturer and module from the user's prompt using the lists above.\n"
                    "2. If ambiguous, ask a clarifying question — do NOT guess.\n"
                    "3. When both are clearly identified, respond ONLY with a confirmation card in "
                    "this EXACT format (do not add prose around it):\n\n"
                    "```pending_action\n"
                    "action: assign_lecturer\n"
                    "lecturer_id: <UUID from list above>\n"
                    "lecturer_name: <full name>\n"
                    "module_offering_id: <offering UUID from list above>\n"
                    "module_label: <code — name>\n"
                    "```\n\n"
                    "The system will extract the block and store the action server-side. "
                    "The user will be shown a confirmation card and must click Confirm."
                ),
            )

        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=f"ASSIGNMENT DATA ERROR: {exc}. Inform user to retry.",
            )

    # ------------------------------------------------------------------
    # WRITE: create org unit (pending confirmation)
    # ------------------------------------------------------------------

    async def _write_create_unit(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models import OrganisationalUnit
        from services.database.models.tenancy import OrganisationalUnitType

        try:
            tid = self._context.tenant_id
            units = list(await self._session.scalars(
                select(OrganisationalUnit)
                .where(OrganisationalUnit.tenant_id == tid)
                .order_by(OrganisationalUnit.materialized_path)
                .limit(60)
            ))
            types = list(await self._session.scalars(
                select(OrganisationalUnitType)
                .where(OrganisationalUnitType.tenant_id == tid)
                .limit(20)
            ))

            unit_list = "\n".join(
                f"  [{u.id}] {u.code}: {u.name}" for u in units
            ) or "  (no units yet)"
            type_list = "\n".join(
                f"  [{t.id}] {t.name} (allows_children={t.allows_children})"
                for t in types
            ) or "  (no unit types)"

            return CapabilityResult(
                matched=True,
                institutional_context=(
                    "WRITE CAPABILITY — CREATE ORGANISATIONAL UNIT\n"
                    "The LLM must NOT create the unit. It must build a confirmation card.\n\n"
                    f"Existing units:\n{unit_list}\n\n"
                    f"Available unit types:\n{type_list}\n\n"
                    "INSTRUCTION:\n"
                    "1. Identify the name, code, parent unit, and type from the user prompt.\n"
                    "2. If ambiguous, ask clarifying questions.\n"
                    "3. When clear, respond ONLY with a confirmation card in EXACT format:\n\n"
                    "```pending_action\n"
                    "action: create_org_unit\n"
                    "unit_type_id: <UUID from type list>\n"
                    "parent_id: <UUID from unit list, or NONE>\n"
                    "code: <short_code>\n"
                    "name: <full name>\n"
                    "```\n\n"
                    "The user will see a confirmation card before any database write occurs."
                ),
            )

        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=f"STRUCTURE DATA ERROR: {exc}. Inform user to retry.",
            )

    # ------------------------------------------------------------------
    # Execute confirmed WRITE actions
    # ------------------------------------------------------------------

    async def _exec_assign_lecturer(self, payload: dict) -> CapabilityResult:
        from datetime import timezone
        from decimal import Decimal
        from ..services.assignments import AssignmentService

        try:
            svc = AssignmentService(self._session, self._context)
            assignment = await svc.assign_lecturer(
                lecturer_user_id=UUID(payload["lecturer_user_id"]),
                module_offering_id=UUID(payload["module_offering_id"]),
                responsibility_type="lecturer",
                workload_percentage=Decimal("100") if not payload.get("workload_percentage") else Decimal(str(payload["workload_percentage"])),
                valid_from=datetime.now(timezone.utc),
                valid_until=None,
            )
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    f"ASSIGNMENT EXECUTED SUCCESSFULLY\n"
                    f"Assignment ID: {assignment.id}\n"
                    f"Lecturer: {payload.get('lecturer_name', payload['lecturer_user_id'])}\n"
                    f"Module offering: {payload.get('module_label', payload['module_offering_id'])}\n"
                    f"Assigned by: {self._context.user_id}\n"
                    f"Status: active\n"
                    f"Audit event: academic.lecturer_assigned\n\n"
                    "INSTRUCTION: Confirm the assignment success to the user with all the above details. "
                    "Tell them the database has been updated and a notification sent to the lecturer."
                ),
            )
        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    f"ASSIGNMENT EXECUTION FAILED: {exc}\n"
                    "INSTRUCTION: Inform the user the assignment failed with the above error. "
                    "No database changes were made."
                ),
            )

    async def _exec_create_org_unit(self, payload: dict) -> CapabilityResult:
        from ..services.organisation import OrganisationService
        from ..schemas.organisation import OrganisationalUnitCreate

        try:
            svc = OrganisationService(self._session, self._context)
            create_payload = OrganisationalUnitCreate(
                unit_type_id=UUID(payload["unit_type_id"]),
                parent_id=UUID(payload["parent_id"]) if payload.get("parent_id") and payload["parent_id"] != "NONE" else None,
                code=payload["code"],
                name=payload["name"],
            )
            unit = await svc.create_unit(create_payload)
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    f"UNIT CREATED SUCCESSFULLY\n"
                    f"Unit ID: {unit.id}\n"
                    f"Code: {unit.code}\n"
                    f"Name: {unit.name}\n"
                    f"Path: {unit.materialized_path}\n\n"
                    "INSTRUCTION: Confirm creation to the user. "
                    "Tell them the organisational structure has been updated."
                ),
            )
        except Exception as exc:
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    f"UNIT CREATION FAILED: {exc}\n"
                    "INSTRUCTION: Inform the user of the failure. No changes were made."
                ),
            )
