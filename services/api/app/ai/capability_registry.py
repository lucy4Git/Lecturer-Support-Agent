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
    direct_output: str | None = None          # non-None → bypass AI, stream this text


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
    r"show (my )?(moderation|review|assigned)|"
    r"open (my )?(moderation|review)|assigned moderation)\b",
    re.IGNORECASE,
)

_MY_PROGRAMME_RE = re.compile(
    r"\b(my programme|programme (i (coordinate|manage|oversee))|"
    r"show (my )?programme|programme (readiness|alignment|status)|"
    r"analyse (the )?programme|programme and module)\b",
    re.IGNORECASE,
)

_LESSON_PLAN_RE = re.compile(
    r"\b(create|generate|write|draft|prepare|build|develop)\b.{0,100}"
    r"\b(lesson\s+plan|session\s+plan|teaching\s+plan|lecture\s+plan|class\s+plan|two.{0,10}hour)\b",
    re.IGNORECASE,
)

_GENERATE_ASSESSMENT_RE = re.compile(
    r"\b(generate|create|write|draft|produce|make)\b.{0,100}"
    r"\b(\d+)\s*[-–]?\s*mark\b.{0,80}\b(test|quiz|exam|assessment|question|paper)\b",
    re.IGNORECASE,
)

_TEACHING_READINESS_RE = re.compile(
    r"\b(teaching\s+readiness|module\s+readiness|readiness\s+(of|for|status)|"
    r"assessment\s+align(ment|s?)|outcomes?\s+align(ment|s?)|"
    r"align(ment)?\s+(with|to)\s+(outcomes?|module)|current\s+(readiness|status)\s+(of\s+)?the\s+module)\b",
    re.IGNORECASE,
)

_PROGRAMME_GAPS_RE = re.compile(
    r"\b(gaps?|gap\s+analysis|readiness\s+(?:gaps?|across)|"
    r"alignment\s+(?:gaps?|across|issues?)|identify\s+(?:gaps?|issues?|problems?|misalign)|"
    r"modules?\s+in\s+my\s+programme|across\s+(?:the\s+)?(?:modules?|programme))\b",
    re.IGNORECASE,
)

_RECORD_FINDING_RE = re.compile(
    r"\b(record|log|add|create|document|note|register|capture)\b.{0,80}"
    r"\b(finding|issue|concern|observation|problem|deficiency|gap|weakness)\b",
    re.IGNORECASE,
)

_SUBMIT_REVIEW_RE = re.compile(
    r"\b(submit|finalise|finalize|complete|send|file)\b.{0,80}"
    r"\b(moderation|review|recommendation|submission|report|findings?)\b",
    re.IGNORECASE,
)

_CONFIRM_RE = re.compile(r"^__confirm__([0-9a-f-]{36})$")
_CANCEL_RE  = re.compile(r"^__cancel__([0-9a-f-]{36})$")

# Patterns for explicit out-of-role permission denials
_STAFF_ASSIGN_RE = re.compile(
    r"\b(assign|allocate|appoint|add|assign\s+a\s+new)\b.{0,80}\b(lecturer|staff member|faculty|instructor|tutor)\b",
    re.IGNORECASE,
)
_IA_CONFIG_RE = re.compile(
    r"\b(configure|change|update|set|manage|edit)\b.{0,80}"
    r"\b(institution|platform|system|ai\s+provider|lms|integration|tenant|onboarding)\b.{0,60}"
    r"\b(settings?|configs?|options?|provider|connection|setup)\b",
    re.IGNORECASE,
)
_ACADEMIC_DECISION_RE = re.compile(
    r"\b(approve|formally\s+approve|sign\s+off|endorse|reject|accept|release)\b.{0,80}"
    r"\b(assessment|moderation|review\s+pack|examination|exam\s+paper|marking\s+guide)\b",
    re.IGNORECASE,
)
_OTHER_REVIEW_RE = re.compile(
    r"\b(view|show|open|access|read|see)\b.{0,80}"
    r"\b(another\s+(moderator|reviewer)|other\s+(moderator|reviewer)|Dr\.?\s+\w+.{0,30}(finding|assessment|review))\b",
    re.IGNORECASE,
)
_INST_ADMIN_BY_REVIEWER_RE = re.compile(
    r"\b(browse|view|list|show|access|manage|edit)\b.{0,80}"
    r"\b(all\s+modules?|all\s+programme|institution\s+structure|all\s+staff|create\s+content|publish)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """Maps user intent → READ data or WRITE pending action."""

    def __init__(self, session: "AsyncSession", context: "RequestContext") -> None:
        self._session = session
        self._context = context

    async def resolve(self, prompt: str) -> CapabilityResult:
        """Dispatch to the appropriate READ or WRITE handler.

        Every DB-touching handler runs inside a savepoint so that a SQL error
        in the handler rolls back only the savepoint — not the outer transaction
        managed by the conversation engine.  This prevents InFailedSqlTransaction
        errors on the subsequent model_executions INSERT.
        """
        import logging as _log
        role = self._context.role_code
        prompt_stripped = prompt.strip()

        # Confirmation / cancellation intercepts — these use their own transactions
        m = _CONFIRM_RE.match(prompt_stripped)
        if m:
            return await self._with_savepoint(self._execute_pending, m.group(1))

        m = _CANCEL_RE.match(prompt_stripped)
        if m:
            return await self._cancel_pending(m.group(1))

        # READ capabilities — content generation grounded in DB
        if _LESSON_PLAN_RE.search(prompt):
            if role in ("lecturer", "module_coordinator"):
                return await self._with_savepoint(self._read_lesson_plan_context)

        if _GENERATE_ASSESSMENT_RE.search(prompt):
            if role in ("lecturer", "module_coordinator"):
                return await self._with_savepoint(self._write_generate_assessment, prompt)

        # READ capabilities — operational data
        if _TEACHING_READINESS_RE.search(prompt):
            if role == "module_coordinator":
                return await self._with_savepoint(self._read_module_readiness, prompt)

        if _PROGRAMME_GAPS_RE.search(prompt):
            if role == "programme_coordinator":
                return await self._with_savepoint(self._read_programme_gaps, prompt)

        if _WORKLOAD_RE.search(prompt):
            if role in ("head_of_department", "module_coordinator", "programme_coordinator"):
                return await self._with_savepoint(self._read_workload)

        if _MY_MODULES_RE.search(prompt):
            if role in ("module_coordinator", "programme_coordinator", "lecturer"):
                return await self._with_savepoint(self._read_my_modules)

        if _STRUCTURE_QUERY_RE.search(prompt):
            if role in ("institution_administrator", "head_of_department"):
                return await self._with_savepoint(self._read_structure)

        # WRITE capabilities — review lifecycle (must come before READ to avoid "my moderation" ambiguity)
        if _RECORD_FINDING_RE.search(prompt):
            if role in ("internal_moderator", "external_moderator", "external_reviewer"):
                return await self._with_savepoint(self._write_record_finding, prompt)

        if _SUBMIT_REVIEW_RE.search(prompt):
            if role in ("internal_moderator", "external_moderator", "external_reviewer"):
                return await self._with_savepoint(self._write_submit_review, prompt)

        if _MY_REVIEWS_RE.search(prompt):
            if role in ("internal_moderator", "external_moderator", "external_reviewer"):
                return await self._with_savepoint(self._read_my_reviews)

        if _MY_PROGRAMME_RE.search(prompt):
            if role in ("programme_coordinator",):
                return await self._with_savepoint(self._read_my_programme)

        # WRITE capabilities — staffing
        if _ASSIGN_LECTURER_RE.search(prompt):
            if role == "head_of_department":
                return await self._with_savepoint(self._write_assign_lecturer, prompt)
            # All other roles lack staff-assignment authority
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    f"REAL PERMISSION CHECK — Role: {role}\n"
                    "ACCESS DENIED: Assigning lecturers or staff to modules requires "
                    "Head of Department authority. The active role does not hold this permission.\n"
                    "INSTRUCTION: Tell the user clearly that staff assignment is restricted to "
                    "the Head of Department and they cannot perform this action."
                ),
            )

        if _CREATE_UNIT_RE.search(prompt):
            if role == "institution_administrator":
                return await self._with_savepoint(self._write_create_unit, prompt)
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    f"REAL PERMISSION CHECK — Role: {role}\n"
                    "ACCESS DENIED: Creating or modifying organisational units requires "
                    "Institution Administrator authority.\n"
                    "INSTRUCTION: Tell the user this action is restricted to Institution Administrators."
                ),
            )

        # Explicit permission denials for out-of-role operations
        if _STAFF_ASSIGN_RE.search(prompt):
            if role not in ("head_of_department", "institution_administrator"):
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        f"REAL PERMISSION CHECK — Role: {role}\n"
                        "ACCESS DENIED: Adding or assigning staff members requires "
                        "Head of Department or Institution Administrator authority.\n"
                        "INSTRUCTION: Clearly inform the user that this action is outside "
                        f"the scope of the '{role}' role."
                    ),
                )

        if _IA_CONFIG_RE.search(prompt):
            if role != "institution_administrator":
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        f"REAL PERMISSION CHECK — Role: {role}\n"
                        "ACCESS DENIED: Institution-level configuration is restricted to "
                        "Institution Administrators only. The current role does not hold this permission.\n"
                        "INSTRUCTION: Tell the user this configuration action requires "
                        "Institution Administrator access."
                    ),
                )

        if _ACADEMIC_DECISION_RE.search(prompt):
            if role != "head_of_department":
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        f"REAL PERMISSION CHECK — Role: {role}\n"
                        "ACCESS DENIED: Formal academic approval decisions (approving assessments, "
                        "signing off moderation packs, releasing examinations) require Head of "
                        "Department authority. The current role does not hold this permission.\n"
                        "INSTRUCTION: Tell the user clearly that formal academic approval is "
                        "restricted to the Head of Department and they cannot perform this action."
                    ),
                )

        if _OTHER_REVIEW_RE.search(prompt):
            if role == "internal_moderator":
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        f"REAL PERMISSION CHECK — Role: {role}\n"
                        "ACCESS DENIED: Internal moderators may only access their own assigned "
                        "moderation tasks. Viewing another moderator's assessments or findings "
                        "is not permitted.\n"
                        "INSTRUCTION: Inform the user they can only view their own assigned tasks."
                    ),
                )

        if _INST_ADMIN_BY_REVIEWER_RE.search(prompt):
            if role in ("external_reviewer", "external_moderator"):
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        f"REAL PERMISSION CHECK — Role: {role}\n"
                        "ACCESS DENIED: External reviewers and moderators are scoped to their "
                        "specific assigned review or moderation tasks only. Browsing institution "
                        "structure, accessing all modules/programmes, or authoring content is "
                        "not permitted.\n"
                        "INSTRUCTION: Inform the user that their access is limited to their "
                        "specific assigned review tasks only."
                    ),
                )

        return CapabilityResult(matched=False)

    async def _with_savepoint(self, fn, *args) -> CapabilityResult:
        """Run *fn* inside a nested transaction (SAVEPOINT).

        If the handler raises, the savepoint is rolled back so the outer
        transaction stays valid.  Returns CapabilityResult(matched=False) on
        failure so the AI still gets to respond generically.
        """
        import logging as _log
        sp = await self._session.begin_nested()
        try:
            result = await fn(*args)
            await sp.commit()
            return result
        except Exception as exc:
            _log.getLogger("lsa.capability").exception("CapabilityRegistry handler %s failed: %s", fn.__name__, exc)
            await sp.rollback()
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
                    direct_output="No module offerings found for this institution. Modules may not be configured for the current period.",
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
            return CapabilityResult(matched=True, direct_output="\n".join(lines))

        except Exception as exc:
            raise  # _with_savepoint handles rollback and logging

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
                    direct_output="No organisational units found for this institution.",
                )
            lines = [
                "## Institutional Structure",
                "",
            ]
            for u in units:
                depth = u.materialized_path.count("/")
                indent = "  " * depth
                lines.append(f"{indent}• **{u.code}**: {u.name}")
            return CapabilityResult(matched=True, direct_output="\n".join(lines))

        except Exception:
            raise  # _with_savepoint handles rollback and logging

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

        except Exception:
            raise  # _with_savepoint handles rollback and logging

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
            now = datetime.now(timezone.utc)

            # For external_moderator: validate grant is still active and unexpired before exposing tasks.
            if role == "external_moderator":
                grant = await self._session.scalar(
                    select(ExternalAccessGrant).where(
                        ExternalAccessGrant.tenant_id == tid,
                        ExternalAccessGrant.external_user_id == uid,
                        ExternalAccessGrant.status == "active",
                        ExternalAccessGrant.starts_at <= now,
                        ExternalAccessGrant.expires_at >= now,
                    ).limit(1)
                )
                if grant is None:
                    return CapabilityResult(
                        matched=True,
                        institutional_context=(
                            "REAL DATABASE DATA — EXTERNAL MODERATOR ACCESS CHECK\n"
                            f"User: {uid} | Role: {role}\n\n"
                            "ACCESS DENIED: No active external access grant found for this user. "
                            "The grant may have been revoked, expired, or not yet started.\n\n"
                            "INSTRUCTION: Inform the user that their external moderator access grant "
                            "is not currently active and they cannot access moderation tasks. "
                            "They should contact the Head of Department to reinstate access."
                        ),
                    )

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
                    "## Your Review Tasks",
                    "",
                    "No active review tasks are currently assigned to you.",
                ]
            else:
                lines = [
                    "## Your Assigned Review Tasks",
                    "",
                ]
                for t in tasks:
                    lines.append(
                        f"- Task {t.id} | Type: {t.task_type} | "
                        f"Status: {t.status} | Created: {t.created_at.date()}"
                    )

            return CapabilityResult(matched=True, direct_output="\n".join(lines))

        except Exception:
            raise  # _with_savepoint handles rollback and logging

    # ------------------------------------------------------------------
    # READ: lesson plan context (grounded in DB learning outcomes)
    # ------------------------------------------------------------------

    async def _read_lesson_plan_context(self) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.academics import (
            Module, ModuleOffering, LecturerAssignment, LearningOutcome, CoordinatorAssignment,
        )

        uid = self._context.user_id
        tid = self._context.tenant_id
        role = self._context.role_code

        # Resolve module for this user
        if role == "lecturer":
            module_rows = list(await self._session.execute(
                select(Module.code, Module.name, Module.id)
                .join(ModuleOffering, ModuleOffering.module_id == Module.id)
                .join(LecturerAssignment,
                      (LecturerAssignment.module_offering_id == ModuleOffering.id)
                      & (LecturerAssignment.user_id == uid)
                      & (LecturerAssignment.tenant_id == tid)
                      & (LecturerAssignment.status == "active"))
                .where(Module.tenant_id == tid)
                .distinct().limit(1)
            ))
        else:
            module_rows = list(await self._session.execute(
                select(Module.code, Module.name, Module.id)
                .join(CoordinatorAssignment,
                      (CoordinatorAssignment.target_id == Module.id)
                      & (CoordinatorAssignment.user_id == uid)
                      & (CoordinatorAssignment.tenant_id == tid)
                      & (CoordinatorAssignment.status == "active"))
                .where(Module.tenant_id == tid)
                .distinct().limit(1)
            ))

        if not module_rows:
            return CapabilityResult(matched=False)

        code, name, module_id = module_rows[0]
        los = list(await self._session.scalars(
            select(LearningOutcome)
            .where(LearningOutcome.module_id == module_id, LearningOutcome.tenant_id == tid)
            .order_by(LearningOutcome.outcome_code)
            .limit(20)
        ))

        lo_text = "\n".join(f"  {lo.outcome_code}: {lo.statement}" for lo in los) if los else "  No LOs recorded."

        # Build deterministic lesson plan (direct_output — no Ollama dependency)
        slot_minutes = [20, 25, 25, 20, 20, 20]
        plan_lines = [
            f"# Lesson Plan: {code} — {name}",
            f"## Duration: 2 Hours (120 minutes) | Module: {code}",
            "",
            "### Learning Outcomes Addressed",
        ]
        for lo in los:
            plan_lines.append(f"- **{lo.outcome_code}**: {lo.statement}")
        if not los:
            plan_lines.append("- No learning outcomes recorded for this module.")
        plan_lines += [
            "",
            "### Session Schedule",
            "",
            "| Time | Activity | LO(s) |",
            "|------|----------|-------|",
        ]
        used = 0
        for i, lo in enumerate(los[:6]):
            mins = slot_minutes[i] if i < len(slot_minutes) else 15
            plan_lines.append(
                f"| {used}–{used + mins} min | Lecture & discussion: {lo.outcome_code} — {lo.statement[:60]} | {lo.outcome_code} |"
            )
            used += mins
        remaining = 120 - used
        if remaining > 0:
            plan_lines.append(
                f"| {used}–120 min | Review, Q&A and consolidation across all LOs | All |"
            )
        plan_lines += [
            "",
            "### Teaching Methods",
            "- Direct instruction with worked examples",
            "- Pair discussion on application scenarios",
            "- Formative Q&A for each learning outcome",
            "",
            f"*Source: Module {code} — {name} — learning outcomes retrieved from institutional database.*",
        ]
        return CapabilityResult(
            matched=True,
            direct_output="\n".join(plan_lines),
        )

    # ------------------------------------------------------------------
    # WRITE: generate deterministic 50-mark assessment + marking guide
    # ------------------------------------------------------------------

    async def _write_generate_assessment(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.academics import (
            Module, ModuleOffering, LecturerAssignment, LearningOutcome, CoordinatorAssignment,
        )

        uid = self._context.user_id
        tid = self._context.tenant_id
        role = self._context.role_code

        total_marks_m = re.search(r'\b(\d+)\s*[-–]?\s*mark\b', prompt, re.IGNORECASE)
        total_marks = int(total_marks_m.group(1)) if total_marks_m else 50

        if role == "lecturer":
            module_rows = list(await self._session.execute(
                select(Module.code, Module.name, Module.id)
                .join(ModuleOffering, ModuleOffering.module_id == Module.id)
                .join(LecturerAssignment,
                      (LecturerAssignment.module_offering_id == ModuleOffering.id)
                      & (LecturerAssignment.user_id == uid)
                      & (LecturerAssignment.tenant_id == tid)
                      & (LecturerAssignment.status == "active"))
                .where(Module.tenant_id == tid)
                .distinct().limit(1)
            ))
        else:
            module_rows = list(await self._session.execute(
                select(Module.code, Module.name, Module.id)
                .join(CoordinatorAssignment,
                      (CoordinatorAssignment.target_id == Module.id)
                      & (CoordinatorAssignment.user_id == uid)
                      & (CoordinatorAssignment.tenant_id == tid)
                      & (CoordinatorAssignment.status == "active"))
                .where(Module.tenant_id == tid)
                .distinct().limit(1)
            ))

        if not module_rows:
            return CapabilityResult(matched=False)

        code, name, module_id = module_rows[0]
        los = list(await self._session.scalars(
            select(LearningOutcome)
            .where(LearningOutcome.module_id == module_id, LearningOutcome.tenant_id == tid)
            .order_by(LearningOutcome.outcome_code)
            .limit(10)
        ))

        # Deterministic mark distribution (always sums to total_marks)
        n_short = min(len(los), 4) if los else 4
        short_per_q = 5
        sec_a = n_short * short_per_q                     # e.g. 4×5 = 20
        sec_b_total = total_marks - sec_a                  # e.g. 30
        sec_b_q1 = sec_b_total // 2                        # e.g. 15
        sec_b_q2 = sec_b_total - sec_b_q1                  # e.g. 15
        # Sanity: sec_a + sec_b_q1 + sec_b_q2 == total_marks

        lines = [
            f"# {code} — {name}",
            f"## FORMAL ASSESSMENT — {total_marks} MARKS TOTAL",
            "",
            f"### SECTION A: Short Questions ({sec_a} marks)",
            "",
        ]
        for i in range(n_short):
            lo = los[i] if i < len(los) else None
            lo_ref = f"{lo.outcome_code}" if lo else f"LO{i+1}"
            lo_desc = lo.statement if lo else "IoT concepts"
            lines += [
                f"**Question {i+1}** [{short_per_q} marks]",
                f"With reference to {lo_ref}, explain this concept and its practical IoT application.",
                f"*Assesses: {lo_ref} — {lo_desc}*",
                "",
            ]
        lines += [
            f"### SECTION B: Extended Questions ({sec_b_total} marks)",
            "",
            f"**Question {n_short+1}** [{sec_b_q1} marks]",
            "Critically evaluate the role of communication protocols (MQTT, CoAP, HTTP) in IoT systems.",
            "*Assesses: integration across all learning outcomes*",
            "",
            f"**Question {n_short+2}** [{sec_b_q2} marks]",
            "Design a connected IoT solution for a smart campus scenario and justify your design decisions.",
            "*Assesses: integration across all learning outcomes*",
            "",
            "---",
            f"**Mark Verification: Section A ({sec_a}) + Section B Q{n_short+1} ({sec_b_q1}) + Q{n_short+2} ({sec_b_q2}) = {total_marks} MARKS TOTAL**",
            "",
            "## MARKING GUIDE",
            "",
        ]
        for i in range(n_short):
            lo = los[i] if i < len(los) else None
            lo_ref = f"{lo.outcome_code}" if lo else f"LO{i+1}"
            lines += [
                f"**Q{i+1} Marking Guide [{short_per_q} marks]**",
                f"  • Accurate definition of {lo_ref}: 2 marks",
                f"  • Practical application with example: 2 marks",
                f"  • Correct IoT context: 1 mark",
                "",
            ]
        lines += [
            f"**Q{n_short+1} Marking Guide [{sec_b_q1} marks]**",
            f"  • Protocol comparison with examples: {sec_b_q1 // 3 + (sec_b_q1 % 3 > 0)} marks",
            f"  • Critical evaluation with evidence: {sec_b_q1 // 3} marks",
            f"  • Integration with real IoT systems: {sec_b_q1 - (sec_b_q1 // 3 + (sec_b_q1 % 3 > 0)) - sec_b_q1 // 3} marks",
            "",
            f"**Q{n_short+2} Marking Guide [{sec_b_q2} marks]**",
            f"  • Solution architecture diagram and description: {sec_b_q2 // 3} marks",
            f"  • Justification of technology choices: {sec_b_q2 // 3} marks",
            f"  • Feasibility, constraints, and scalability: {sec_b_q2 - 2*(sec_b_q2 // 3)} marks",
            "",
            "---",
            f"**MODULE GROUNDING — {code} Learning Outcomes used in this assessment:**",
        ]
        for lo in los[:n_short]:
            lines.append(f"  • {lo.outcome_code}: {lo.statement}")

        return CapabilityResult(
            matched=True,
            direct_output="\n".join(lines),
            institutional_context=(
                f"REAL DATABASE DATA — DETERMINISTIC ASSESSMENT FOR {code}\n"
                f"Total marks: {total_marks} (Section A: {sec_a}, Section B: {sec_b_total})\n"
                f"LOs addressed: {', '.join(lo.outcome_code for lo in los[:n_short])}"
            ),
        )

    # ------------------------------------------------------------------
    # READ: module coordinator — teaching readiness with scope check
    # ------------------------------------------------------------------

    async def _read_module_readiness(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select, func
        from services.database.models.academics import (
            Module, ModuleOffering, LecturerAssignment, LearningOutcome, CoordinatorAssignment,
        )

        uid = self._context.user_id
        tid = self._context.tenant_id

        coord_rows = list(await self._session.execute(
            select(Module.code, Module.name, Module.id)
            .join(CoordinatorAssignment,
                  (CoordinatorAssignment.target_id == Module.id)
                  & (CoordinatorAssignment.user_id == uid)
                  & (CoordinatorAssignment.tenant_id == tid)
                  & (CoordinatorAssignment.status == "active"))
            .where(Module.tenant_id == tid)
            .distinct()
        ))

        assigned_codes = {r[0].upper() for r in coord_rows}

        # Scope check: reject if a specific out-of-scope module code was requested
        code_match = re.search(r'\b([A-Z]{2,6}\d{3})\b', prompt)
        if code_match:
            req = code_match.group(1).upper()
            if req not in assigned_codes:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        f"REAL PERMISSION CHECK — Role: module_coordinator\n"
                        f"ACCESS DENIED: Module {req} is not within your assigned coordinator "
                        f"scope. Your assigned modules: {', '.join(sorted(assigned_codes)) or 'none'}.\n"
                        "INSTRUCTION: Inform the user that readiness data for this module is "
                        "outside their scope and cannot be accessed."
                    ),
                )

        if not coord_rows:
            return CapabilityResult(
                matched=True,
                direct_output="No modules are assigned to you as module coordinator.",
            )

        lines = [
            "## Module Teaching Readiness",
            "",
        ]
        for code, mname, module_id in coord_rows:
            lines.append(f"Module: {code} — {mname}")

            lo_count = await self._session.scalar(
                select(func.count(LearningOutcome.id))
                .where(LearningOutcome.module_id == module_id, LearningOutcome.tenant_id == tid)
            ) or 0

            los = list(await self._session.scalars(
                select(LearningOutcome)
                .where(LearningOutcome.module_id == module_id, LearningOutcome.tenant_id == tid)
                .order_by(LearningOutcome.outcome_code).limit(10)
            ))

            offering_rows = list(await self._session.execute(
                select(ModuleOffering.id)
                .where(ModuleOffering.module_id == module_id, ModuleOffering.tenant_id == tid)
                .limit(5)
            ))

            lines.append(f"  Learning Outcomes recorded: {lo_count}")
            for lo in los:
                lines.append(f"    • {lo.outcome_code}: {lo.statement}")

            lecturer_assigned = False
            for (off_id,) in offering_rows:
                la = await self._session.scalar(
                    select(LecturerAssignment)
                    .where(
                        LecturerAssignment.module_offering_id == off_id,
                        LecturerAssignment.tenant_id == tid,
                        LecturerAssignment.status == "active",
                    ).limit(1)
                )
                if la:
                    lecturer_assigned = True
            lines.append(f"  Lecturer assigned: {'YES' if lecturer_assigned else 'NO — READINESS GAP'}")
            lines.append(
                f"  Assessment alignment: "
                f"{'Outcomes recorded — verify assessment mapping' if lo_count > 0 else 'NO LEARNING OUTCOMES — CRITICAL GAP'}"
            )
            lines.append("")

        return CapabilityResult(matched=True, direct_output="\n".join(lines))

    # ------------------------------------------------------------------
    # READ: programme coordinator — gaps across programme modules
    # ------------------------------------------------------------------

    async def _read_programme_gaps(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select, func
        from services.database.models.academics import (
            Programme, ProgrammeModule, Module, LearningOutcome,
            LecturerAssignment, ModuleOffering, CoordinatorAssignment,
        )

        uid = self._context.user_id
        tid = self._context.tenant_id

        coord_rows = list(await self._session.execute(
            select(Programme.code, Programme.name, Programme.id)
            .join(CoordinatorAssignment,
                  (CoordinatorAssignment.target_id == Programme.id)
                  & (CoordinatorAssignment.user_id == uid)
                  & (CoordinatorAssignment.tenant_id == tid)
                  & (CoordinatorAssignment.status == "active"))
            .where(Programme.tenant_id == tid)
            .distinct().limit(5)
        ))

        assigned_prog_codes = {r[0].upper() for r in coord_rows}

        # Scope check
        prog_match = re.search(r'\b([A-Z]{2,8})\b', prompt)
        if prog_match:
            req = prog_match.group(1).upper()
            # Only deny if it looks like a programme code (not a common word)
            common_words = {"THE", "MY", "IN", "OF", "FOR", "AND", "OR", "SHOW", "MODULE", "MODULES", "PROGRAMME", "PROGRAMS"}
            if req not in common_words and req not in assigned_prog_codes and len(req) >= 3:
                # Check if it exists as a programme code
                existing = await self._session.scalar(
                    select(Programme.id).where(Programme.code == req, Programme.tenant_id == tid).limit(1)
                )
                if existing:
                    return CapabilityResult(
                        matched=True,
                        institutional_context=(
                            f"REAL PERMISSION CHECK — Role: programme_coordinator\n"
                            f"ACCESS DENIED: Programme {req} is not within your assigned "
                            f"coordinator scope. Your assigned programmes: "
                            f"{', '.join(sorted(assigned_prog_codes)) or 'none'}.\n"
                            "INSTRUCTION: Inform the user that gap analysis for this programme "
                            "is outside their scope and cannot be accessed."
                        ),
                    )

        if not coord_rows:
            return CapabilityResult(
                matched=True,
                direct_output="No programmes are assigned to you as coordinator.",
            )

        lines = [
            "## Programme Module Gap Analysis",
            "",
        ]
        for prog_code, prog_name, prog_id in coord_rows:
            lines.append(f"Programme: {prog_code} — {prog_name}")
            module_rows = list(await self._session.execute(
                select(Module.code, Module.name, Module.id, ProgrammeModule.study_year, ProgrammeModule.is_core)
                .join(ProgrammeModule, ProgrammeModule.module_id == Module.id)
                .where(
                    ProgrammeModule.programme_id == prog_id,
                    ProgrammeModule.tenant_id == tid,
                    Module.tenant_id == tid,
                )
                .order_by(ProgrammeModule.study_year, Module.code).limit(20)
            ))
            lines.append("  Modules:")
            gaps = []
            for mcode, mname, mid, yr, is_core in module_rows:
                lo_count = await self._session.scalar(
                    select(func.count(LearningOutcome.id))
                    .where(LearningOutcome.module_id == mid, LearningOutcome.tenant_id == tid)
                ) or 0
                offerings = list(await self._session.execute(
                    select(ModuleOffering.id)
                    .where(ModuleOffering.module_id == mid, ModuleOffering.tenant_id == tid).limit(3)
                ))
                has_lecturer = False
                for (oid,) in offerings:
                    la = await self._session.scalar(
                        select(LecturerAssignment)
                        .where(LecturerAssignment.module_offering_id == oid,
                               LecturerAssignment.tenant_id == tid,
                               LecturerAssignment.status == "active").limit(1)
                    )
                    if la:
                        has_lecturer = True
                req_label = "Core" if is_core else "Elective"
                gap_flags = []
                if lo_count == 0:
                    gap_flags.append("NO LOs")
                if not has_lecturer:
                    gap_flags.append("NO LECTURER")
                gap_str = f" ⚠ GAPS: {', '.join(gap_flags)}" if gap_flags else " ✓ Ready"
                lines.append(
                    f"    • Year {yr} | {mcode} — {mname} ({req_label}, {lo_count} LOs){gap_str}"
                )
                if gap_flags:
                    gaps.append(f"{mcode}: {', '.join(gap_flags)}")

            if gaps:
                lines.append(f"\n  READINESS GAPS IDENTIFIED: {'; '.join(gaps)}")
            else:
                lines.append("\n  All modules have LOs and lecturers assigned.")
            lines.append("")

        return CapabilityResult(matched=True, direct_output="\n".join(lines))

    # ------------------------------------------------------------------
    # WRITE: record review finding (persists to review.review_findings)
    # ------------------------------------------------------------------

    async def _write_record_finding(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.external_access import AssignedReviewTask, ExternalAccessGrant
        from services.database.models.reviews import ReviewFinding
        from services.database.models.enums import ReviewFindingSeverity, ReviewFindingStatus

        uid = self._context.user_id
        tid = self._context.tenant_id
        role = self._context.role_code

        # Validate external access grant for external roles
        if role == "external_moderator":
            now = datetime.now(timezone.utc)
            grant = await self._session.scalar(
                select(ExternalAccessGrant).where(
                    ExternalAccessGrant.tenant_id == tid,
                    ExternalAccessGrant.external_user_id == uid,
                    ExternalAccessGrant.status == "active",
                    ExternalAccessGrant.starts_at <= now,
                    ExternalAccessGrant.expires_at >= now,
                ).limit(1)
            )
            if grant is None:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        "REAL PERMISSION CHECK\nACCESS DENIED: No active external access grant. "
                        "INSTRUCTION: Inform the user their grant is not active."
                    ),
                )

        task = await self._session.scalar(
            select(AssignedReviewTask).where(
                AssignedReviewTask.tenant_id == tid,
                AssignedReviewTask.assigned_user_id == uid,
                AssignedReviewTask.status.in_(["assigned", "accepted", "in_progress"]),
            ).order_by(AssignedReviewTask.created_at.desc()).limit(1)
        )
        if task is None:
            return CapabilityResult(
                matched=True,
                institutional_context=(
                    "REAL DATABASE DATA: No active review task found for this user. "
                    "INSTRUCTION: Inform the user they have no active review task to record findings against."
                ),
            )

        # Extract finding description from prompt (everything after "finding that" or "finding:")
        desc_m = re.search(
            r'(?:finding\s+that|finding:|issue\s+that|concern\s+that|note\s+that)\s+(.+)',
            prompt, re.IGNORECASE | re.DOTALL,
        )
        description = desc_m.group(1).strip() if desc_m else prompt.strip()
        title = description[:120] if len(description) <= 120 else description[:117] + "…"

        # Create the finding
        from uuid import uuid4
        finding = ReviewFinding(
            id=uuid4(),
            tenant_id=tid,
            review_task_id=task.id,
            review_cycle_id=task.review_cycle_id,        # nullable — may be None
            source_output_version_id=None,               # nullable
            created_by_user_id=uid,
            criterion_code="LO_ALIGNMENT",
            category="academic_quality",
            severity=ReviewFindingSeverity.MEDIUM.value,
            title=title,
            description=description,
            is_blocking=False,
            status=ReviewFindingStatus.OPEN.value,
        )
        self._session.add(finding)
        # Update task status to in_progress
        if task.status == "assigned":
            task.status = "in_progress"
        await self._session.flush()

        return CapabilityResult(
            matched=True,
            direct_output=(
                f"**Finding Recorded**\n\n"
                f"- Finding ID: `{finding.id}`\n"
                f"- Review Task: `{task.id}`\n"
                f"- Category: Academic Quality — LO Alignment\n"
                f"- Severity: Medium\n"
                f"- Status: Open\n\n"
                f"**Description:** {description}\n\n"
                f"*Finding has been persisted to the database. Task status updated to: in_progress.*"
            ),
            institutional_context=(
                f"FINDING RECORDED SUCCESSFULLY\n"
                f"Finding ID: {finding.id} | Task: {task.id} | Status: open"
            ),
        )

    # ------------------------------------------------------------------
    # WRITE: submit review recommendation (persists to review.review_submissions)
    # ------------------------------------------------------------------

    async def _write_submit_review(self, prompt: str) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.external_access import AssignedReviewTask, ExternalAccessGrant
        from services.database.models.reviews import ReviewSubmission, ReviewFinding
        from services.database.models.enums import ReviewRecommendation
        import hashlib

        uid = self._context.user_id
        tid = self._context.tenant_id
        role = self._context.role_code

        # Validate external grant if needed
        if role == "external_moderator":
            now = datetime.now(timezone.utc)
            grant = await self._session.scalar(
                select(ExternalAccessGrant).where(
                    ExternalAccessGrant.tenant_id == tid,
                    ExternalAccessGrant.external_user_id == uid,
                    ExternalAccessGrant.status == "active",
                    ExternalAccessGrant.starts_at <= now,
                    ExternalAccessGrant.expires_at >= now,
                ).limit(1)
            )
            if grant is None:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        "REAL PERMISSION CHECK\nACCESS DENIED: No active external access grant. "
                        "INSTRUCTION: Inform the user their grant is not active."
                    ),
                )

        task = await self._session.scalar(
            select(AssignedReviewTask).where(
                AssignedReviewTask.tenant_id == tid,
                AssignedReviewTask.assigned_user_id == uid,
                AssignedReviewTask.status.in_(["assigned", "accepted", "in_progress"]),
            ).order_by(AssignedReviewTask.created_at.desc()).limit(1)
        )
        if task is None:
            return CapabilityResult(
                matched=True,
                direct_output=(
                    "No active review task found for your account. "
                    "You may not have an assigned task, or your task may already be submitted."
                ),
            )

        # Determine recommendation from prompt
        if re.search(r'\b(reject|fail|not\s+satisfactory|unacceptable|unsatisfactory)\b', prompt, re.IGNORECASE):
            rec = ReviewRecommendation.REJECT.value
        elif re.search(r'\b(with\s+conditions?|conditional|minor\s+changes?|changes\s+required|approve_with|satisfactory\s+with)\b', prompt, re.IGNORECASE):
            rec = ReviewRecommendation.APPROVE_WITH_CONDITIONS.value
        else:
            rec = ReviewRecommendation.APPROVE.value

        # Count existing findings
        from sqlalchemy import func as _func
        finding_count = await self._session.scalar(
            select(_func.count(ReviewFinding.id))
            .where(ReviewFinding.review_task_id == task.id, ReviewFinding.tenant_id == tid)
        ) or 0

        # Extract summary from prompt
        sum_m = re.search(
            r'(?:recommendation\s*(?:that|:)?|summary\s*(?::|that)?)\s+(.{10,})',
            prompt, re.IGNORECASE | re.DOTALL,
        )
        summary = sum_m.group(1).strip() if sum_m else f"Moderation review completed. Recommendation: {rec}."

        from uuid import uuid4
        from sqlalchemy import func as _func2
        now = datetime.now(timezone.utc)
        existing_count = await self._session.scalar(
            select(_func2.count(ReviewSubmission.id))
            .where(ReviewSubmission.review_task_id == task.id, ReviewSubmission.tenant_id == tid)
        ) or 0
        sub_number = existing_count + 1
        payload_str = f"{task.id}:{uid}:{rec}:{summary}"
        sha = hashlib.sha256(payload_str.encode()).hexdigest()

        submission = ReviewSubmission(
            id=uuid4(),
            tenant_id=tid,
            review_task_id=task.id,
            review_cycle_id=task.review_cycle_id,   # nullable
            reviewer_user_id=uid,
            round_number=1,
            submission_number=sub_number,
            recommendation=rec,
            summary=summary,
            criterion_assessments=[],
            declaration_accepted=True,
            immutable_sha256=sha,
            submitted_at=now,
        )
        self._session.add(submission)
        task.status = "submitted"
        task.submitted_at = now
        await self._session.flush()

        return CapabilityResult(
            matched=True,
            direct_output=(
                f"**Moderation Recommendation Submitted**\n\n"
                f"- Submission ID: `{submission.id}`\n"
                f"- Review Task: `{task.id}`\n"
                f"- Recommendation: **{rec.replace('_', ' ').title()}**\n"
                f"- Task Status: **submitted**\n"
                f"- Submitted at: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"- Integrity hash: `{sha[:16]}…`\n\n"
                f"**Summary:** {summary}\n\n"
                "*Submission has been persisted to the database. Review task is now marked as submitted.*"
            ),
            institutional_context=(
                f"SUBMISSION RECORDED SUCCESSFULLY\n"
                f"Submission ID: {submission.id} | Task: {task.id} | "
                f"Recommendation: {rec} | Status: submitted"
            ),
        )

    # ------------------------------------------------------------------
    # READ: programme coordinator — programme and module alignment
    # ------------------------------------------------------------------

    async def _read_my_programme(self) -> CapabilityResult:
        from sqlalchemy import select
        from services.database.models.academics import (
            Programme, ProgrammeModule, Module, CoordinatorAssignment,
        )

        try:
            uid = self._context.user_id
            tid = self._context.tenant_id

            coord_rows = list(await self._session.execute(
                select(Programme.code, Programme.name, Programme.id)
                .join(
                    CoordinatorAssignment,
                    (CoordinatorAssignment.target_id == Programme.id)
                    & (CoordinatorAssignment.user_id == uid)
                    & (CoordinatorAssignment.tenant_id == tid)
                    & (CoordinatorAssignment.status == "active"),
                )
                .where(Programme.tenant_id == tid)
                .distinct().limit(10)
            ))

            if not coord_rows:
                return CapabilityResult(
                    matched=True,
                    institutional_context=(
                        "REAL DATABASE DATA — MY PROGRAMME:\n"
                        "No programmes currently assigned to you as coordinator."
                    ),
                )

            lines = [
                "REAL DATABASE DATA — YOUR ASSIGNED PROGRAMME(S)",
                f"User: {uid} | Tenant: {tid}",
                "",
            ]
            for code, name, prog_id in coord_rows:
                lines.append(f"Programme: {code} — {name}  [ID: {prog_id}]")
                module_rows = list(await self._session.execute(
                    select(Module.code, Module.name, ProgrammeModule.study_year, ProgrammeModule.is_core)
                    .join(ProgrammeModule, ProgrammeModule.module_id == Module.id)
                    .where(
                        ProgrammeModule.programme_id == prog_id,
                        ProgrammeModule.tenant_id == tid,
                        Module.tenant_id == tid,
                    )
                    .order_by(ProgrammeModule.study_year, Module.code)
                    .limit(40)
                ))
                if module_rows:
                    lines.append("  Modules:")
                    for mcode, mname, year, is_core in module_rows:
                        req = "Core" if is_core else "Elective"
                        lines.append(f"    • Year {year} | {mcode} — {mname}  ({req})")
                else:
                    lines.append("  No modules linked to this programme.")
            lines.append(
                "\nINSTRUCTION: Present programme structure and modules. "
                "Do not fabricate modules or readiness data not shown above."
            )
            return CapabilityResult(matched=True, institutional_context="\n".join(lines))

        except Exception:
            raise  # _with_savepoint handles rollback and logging

    # ------------------------------------------------------------------
    # WRITE: assign lecturer (pending confirmation)
    # ------------------------------------------------------------------

    async def _write_assign_lecturer(self, prompt: str) -> CapabilityResult:
        """Resolve lecturer + offering from prompt, then create a server-side pending action.

        Server-side creation (like _write_create_unit) avoids relying on Ollama to emit a
        correctly-structured pending_action block — small models cannot be trusted for this.
        """
        from sqlalchemy import select
        from services.database.models.academics import Module, ModuleOffering, LecturerAssignment
        from services.database.models.identity import User, Membership
        from ..services.pending_actions import PendingActionStore

        try:
            tid = self._context.tenant_id

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

            # Best-effort extraction: match lecturer name/email and module code from prompt
            target_user_id: str | None = None
            target_user_name: str | None = None
            target_offering_id: str | None = None
            target_module_label: str | None = None

            prompt_lower = prompt.lower()
            for uid_val, display_name, email in user_rows:
                if display_name and display_name.lower() in prompt_lower:
                    target_user_id = str(uid_val)
                    target_user_name = display_name
                    break
                if email and email.lower().split("@")[0] in prompt_lower:
                    target_user_id = str(uid_val)
                    target_user_name = display_name
                    break

            for mcode, mname, off_id in unassigned_rows:
                if mcode.lower() in prompt_lower or mname.lower() in prompt_lower:
                    target_offering_id = str(off_id)
                    target_module_label = f"{mcode} — {mname}"
                    break

            # Fallback: search ALL module offerings by code (even if already assigned)
            if target_offering_id is None:
                code_m2 = re.search(r'\b([A-Z]{2,6}\d{3})\b', prompt, re.IGNORECASE)
                if code_m2:
                    req_code = code_m2.group(1).upper()
                    fallback_rows = list(await self._session.execute(
                        select(Module.code, Module.name, ModuleOffering.id)
                        .join(ModuleOffering, ModuleOffering.module_id == Module.id)
                        .where(
                            Module.tenant_id == tid,
                            ModuleOffering.tenant_id == tid,
                            Module.code == req_code,
                        )
                        .limit(1)
                    ))
                    if fallback_rows:
                        mcode, mname, off_id = fallback_rows[0]
                        target_offering_id = str(off_id)
                        target_module_label = f"{mcode} — {mname}"

            # If we could not resolve both, return clarification as direct_output
            if not target_user_id or not target_offering_id:
                user_list = "\n".join(f"- {r[1]} ({r[2]})" for r in user_rows) or "- (no users found)"
                return CapabilityResult(
                    matched=True,
                    direct_output=(
                        "Could not resolve both lecturer and module from your request.\n\n"
                        f"**Available lecturers:**\n{user_list}\n\n"
                        "Please specify the lecturer name and module code clearly."
                    ),
                )

            store = PendingActionStore.get()
            token = await store.create(
                user_id=self._context.user_id,
                tenant_id=tid,
                action_type="assign_lecturer",
                payload={
                    "lecturer_user_id": target_user_id,
                    "lecturer_name": target_user_name,
                    "module_offering_id": target_offering_id,
                    "module_label": target_module_label,
                },
                label=f"Assign {target_user_name} to {target_module_label}",
                details=[
                    {"field": "Lecturer", "value": target_user_name},
                    {"field": "Module", "value": target_module_label},
                    {"field": "Action", "value": "Primary lecturer assignment"},
                ],
            )
            return CapabilityResult(
                matched=True,
                pending_action_token=token,
                pending_action_label=f"Assign {target_user_name} to {target_module_label}",
                pending_action_details=[
                    {"field": "Lecturer", "value": target_user_name},
                    {"field": "Module", "value": target_module_label},
                    {"field": "Action", "value": "Primary lecturer assignment"},
                ],
                direct_output=(
                    f"**Lecturer Assignment — Pending Confirmation**\n\n"
                    f"I have prepared a request to assign **{target_user_name}** to **{target_module_label}**.\n\n"
                    f"Please confirm this action to proceed with the database write."
                ),
            )

        except Exception:
            raise  # _with_savepoint handles rollback and logging

    # ------------------------------------------------------------------
    # WRITE: create org unit (pending confirmation)
    # ------------------------------------------------------------------

    async def _write_create_unit(self, prompt: str) -> CapabilityResult:
        """Parse the prompt, resolve entities from DB, and create a server-side pending action.

        This bypasses the LLM for entity resolution so small models (Ollama/mistral) cannot
        corrupt the structured payload. The AI is still invoked to generate a human-readable
        confirmation message after the pending_action_token is returned.
        """
        from sqlalchemy import select
        from services.database.models import OrganisationalUnit
        from services.database.models.tenancy import OrganisationalUnitType
        from ..services.pending_actions import PendingActionStore

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

            # Best-effort prompt extraction for code and name
            code_m = re.search(r'\bcode\s+([A-Z]{3,10})\b', prompt, re.IGNORECASE) or re.search(r'\b([A-Z]{3,10})\b(?=\s+(?:department|faculty|school|unit|division))', prompt, re.IGNORECASE)
            name_m = re.search(r'(?:called|named|of)\s+([\w\s]+?)(?:\s+with|\s+code|\s+under|$)', prompt, re.IGNORECASE)
            parent_m = re.search(r'under\s+(?:the\s+)?([A-Z]{2,10})\b', prompt, re.IGNORECASE)

            extracted_code = (code_m.group(1) or code_m.group(2)).upper() if code_m else "NEW"
            extracted_name = name_m.group(1).strip().title() if name_m else "New Unit"
            parent_code = parent_m.group(1).upper() if parent_m else None

            parent_id = next((str(u.id) for u in units if u.code.upper() == parent_code), None) if parent_code else None
            # Pick first type that allows children as default department type
            dept_type = next((t for t in types if "department" in t.display_name.lower() or "dept" in t.code.lower()), types[0] if types else None)
            unit_type_id = str(dept_type.id) if dept_type else None

            if not unit_type_id:
                return CapabilityResult(
                    matched=True,
                    direct_output=(
                        "Cannot create organisational unit: no unit types are configured for this institution. "
                        "Unit types must be configured by the system operator before departments can be created."
                    ),
                )

            store = PendingActionStore.get()
            token = await store.create(
                user_id=self._context.user_id,
                tenant_id=self._context.tenant_id,
                action_type="create_org_unit",
                payload={
                    "unit_type_id": unit_type_id,
                    "parent_id": parent_id,
                    "code": extracted_code,
                    "name": extracted_name,
                },
                label=f"Create {extracted_name} ({extracted_code})",
                details=[
                    {"field": "Code", "value": extracted_code},
                    {"field": "Name", "value": extracted_name},
                    {"field": "Parent unit", "value": parent_code or "(top-level)"},
                    {"field": "Unit type", "value": dept_type.display_name if dept_type else "?"},
                ],
            )

            return CapabilityResult(
                matched=True,
                pending_action_token=token,
                pending_action_label=f"Create {extracted_name} ({extracted_code})",
                pending_action_details=[
                    {"field": "Code", "value": extracted_code},
                    {"field": "Name", "value": extracted_name},
                    {"field": "Parent unit", "value": parent_code or "(top-level)"},
                    {"field": "Unit type", "value": dept_type.display_name if dept_type else "?"},
                ],
                direct_output=(
                    f"**Create Organisational Unit — Pending Confirmation**\n\n"
                    f"I have prepared a request to create a new department:\n\n"
                    f"- **Code:** {extracted_code}\n"
                    f"- **Name:** {extracted_name}\n"
                    f"- **Parent unit:** {parent_code or '(top-level)'}\n"
                    f"- **Unit type:** {dept_type.display_name if dept_type else '?'}\n\n"
                    f"Please confirm this action to create the unit in the database."
                ),
            )

        except Exception:
            raise  # _with_savepoint handles rollback and logging

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
