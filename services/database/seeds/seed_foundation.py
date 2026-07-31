from __future__ import annotations

import json
import os
import secrets
import string
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.database.models import (
    AcademicPeriod,
    AccessScope,
    AIUsageDaily,
    AIUsagePolicy,
    AssignedReviewTask,
    CoordinatorAssignment,
    ExternalAccessGrant,
    InsightAlert,
    Institution,
    LecturerAssignment,
    LearningOutcome,
    Membership,
    Module,
    ModuleOffering,
    Notification,
    OrganisationalUnit,
    OrganisationalUnitClosure,
    OrganisationalUnitType,
    PasswordCredential,
    PlatformSetting,
    Programme,
    ProgrammeModule,
    ReportDefinition,
    Permission,
    Role,
    RoleAssignment,
    RolePermission,
    User,
)
from services.api.app.core.security import PasswordManager


def stable_id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"lecturer-support-agent:{value}")


_CRED_FILE = Path("runtime") / "seed_credentials.txt"


def _generate_password(length: int = 24) -> str:
    """Generate a random password that satisfies the platform password policy.

    Guarantees: ≥1 uppercase, ≥1 lowercase, ≥1 digit, ≥1 special character.
    """
    specials = "!@#$%^&*"
    pool = string.ascii_letters + string.digits + specials
    while True:
        pw = "".join(secrets.choice(pool) for _ in range(length))
        if (
            any(c.isupper() for c in pw)
            and any(c.islower() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in specials for c in pw)
        ):
            return pw


def _resolve_demo_password() -> str:
    """Return the demonstration password, generating a fresh one when needed.

    Priority:
    1. SEED_DEMO_PASSWORD environment variable (owner-controlled, never committed).
    2. Cached value in runtime/seed_credentials.txt (git-ignored).
    3. Freshly generated random password written to that file.

    The plaintext password is NEVER embedded in source code.
    """
    env_pw = os.getenv("SEED_DEMO_PASSWORD", "").strip()
    if env_pw:
        return env_pw
    if _CRED_FILE.exists():
        lines = _CRED_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if line.startswith("DEMO_PASSWORD="):
                return line.split("=", 1)[1].strip()
    pw = _generate_password()
    _CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CRED_FILE.write_text(
        "# Synthetic demonstration credentials — NOT for production use.\n"
        "# This file is git-ignored. Re-run the seed to regenerate.\n"
        f"DEMO_PASSWORD={pw}\n"
        "# Accounts: admin/hod/lecturer/moderator/external/modcoord/progcoord/extmod\n"
        "# Email pattern: <handle>.<slug>@example.com  (e.g. lecturer.demo-north@example.com)\n",
        encoding="utf-8",
    )
    return pw


def load_role_catalogue() -> dict:
    path = Path(__file__).with_name("role_permissions.json")
    return json.loads(path.read_text(encoding="utf-8"))


def seed_catalogue(session: Session) -> tuple[dict[str, Role], dict[str, Permission]]:
    data = load_role_catalogue()
    permissions: dict[str, Permission] = {}
    for item in data["permissions"]:
        permission = Permission(
            id=stable_id(f"permission:{item['code']}"),
            code=item["code"],
            resource=item["resource"],
            action=item["action"],
            description=item["description"],
            risk_level=item["risk_level"],
        )
        session.merge(permission)
        permissions[item["code"]] = permission

    roles: dict[str, Role] = {}
    for item in data["roles"]:
        role = Role(
            id=stable_id(f"role:{item['code']}"),
            code=item["code"],
            name=item["name"],
            description=item["description"],
            is_system_role=True,
            is_external=item["is_external"],
        )
        session.merge(role)
        roles[item["code"]] = role
        for permission_code in item["permissions"]:
            session.merge(
                RolePermission(
                    role_id=role.id,
                    permission_id=stable_id(f"permission:{permission_code}"),
                )
            )
    session.flush()
    return roles, permissions


def seed_tenant(session: Session, slug: str, name: str, country_code: str, *, demo_password: str) -> None:
    tenant_id = stable_id(f"tenant:{slug}")
    institution = Institution(
        id=tenant_id,
        slug=slug,
        legal_name=name,
        display_name=name,
        institution_type="demonstration_higher_education_institution",
        country_code=country_code,
        default_timezone="Africa/Johannesburg",
        default_locale="en",
        configuration={"synthetic_demo": True, "no_real_personal_data": True},
    )
    session.merge(institution)

    unit_types = [
        ("faculty", "Faculty", 10),
        ("department", "Department", 20),
    ]
    for code, display_name, level in unit_types:
        session.merge(
            OrganisationalUnitType(
                id=stable_id(f"{slug}:unit-type:{code}"),
                tenant_id=tenant_id,
                code=code,
                display_name=display_name,
                plural_name=f"{display_name}s",
                level_order=level,
            )
        )

    faculty_id = stable_id(f"{slug}:faculty:technology")
    department_id = stable_id(f"{slug}:department:computing")
    session.merge(
        OrganisationalUnit(
            id=faculty_id,
            tenant_id=tenant_id,
            unit_type_id=stable_id(f"{slug}:unit-type:faculty"),
            code="TECH",
            name="Faculty of Technology",
            short_name="TECH",
            materialized_path="/TECH",
            depth=0,
        )
    )
    session.merge(
        OrganisationalUnit(
            id=department_id,
            tenant_id=tenant_id,
            unit_type_id=stable_id(f"{slug}:unit-type:department"),
            parent_id=faculty_id,
            code="COMP",
            name="Department of Computing",
            short_name="COMP",
            materialized_path="/TECH/COMP",
            depth=1,
        )
    )
    for ancestor, descendant, depth in (
        (faculty_id, faculty_id, 0),
        (department_id, department_id, 0),
        (faculty_id, department_id, 1),
    ):
        session.merge(
            OrganisationalUnitClosure(
                tenant_id=tenant_id,
                ancestor_id=ancestor,
                descendant_id=descendant,
                depth=depth,
            )
        )

    period_id = stable_id(f"{slug}:period:2026-s1")
    session.merge(
        AcademicPeriod(
            id=period_id,
            tenant_id=tenant_id,
            code="2026-S1",
            name="2026 Semester 1",
            period_type="semester",
            starts_on=date(2026, 1, 19),
            ends_on=date(2026, 6, 30),
            is_current=True,
        )
    )
    module_id = stable_id(f"{slug}:module:iot101")
    offering_id = stable_id(f"{slug}:offering:iot101:2026-s1")
    session.merge(
        Module(
            id=module_id,
            tenant_id=tenant_id,
            owning_unit_id=department_id,
            code="IOT101",
            name="Introduction to Internet of Things",
            credit_value=Decimal("12.00"),
            level_framework="demonstration-level-framework",
            level_value="Diploma Year 1",
            default_contact_hours=48,
            attributes={"synthetic_demo": True},
        )
    )
    session.merge(
        ModuleOffering(
            id=offering_id,
            tenant_id=tenant_id,
            module_id=module_id,
            academic_period_id=period_id,
            org_unit_id=department_id,
            offering_code="IOT101-2026-S1",
            delivery_mode="blended",
        )
    )
    for sequence, (code, statement, cognitive) in enumerate((
        ("LO1", "Explain the purpose and architecture of introductory Internet of Things systems.", "understand"),
        ("LO2", "Connect and read common digital and analogue sensors using a microcontroller platform.", "apply"),
        ("LO3", "Interpret sensor measurements and diagnose basic wiring or data-quality faults.", "analyse"),
        ("LO4", "Document a safe and repeatable IoT sensor practical activity.", "create"),
    ), start=1):
        session.merge(
            LearningOutcome(
                id=stable_id(f"{slug}:learning-outcome:{code.lower()}"),
                tenant_id=tenant_id,
                module_id=module_id,
                outcome_code=code,
                statement=statement,
                cognitive_level=cognitive,
                sequence_order=sequence,
            )
        )

    # Second module for programme coordinator cross-module coverage
    module2_id = stable_id(f"{slug}:module:net201")
    offering2_id = stable_id(f"{slug}:offering:net201:2026-s1")
    session.merge(
        Module(
            id=module2_id,
            tenant_id=tenant_id,
            owning_unit_id=department_id,
            code="NET201",
            name="Network Fundamentals for IoT",
            credit_value=Decimal("12.00"),
            level_framework="demonstration-level-framework",
            level_value="Diploma Year 2",
            default_contact_hours=48,
            attributes={"synthetic_demo": True},
        )
    )
    session.merge(
        ModuleOffering(
            id=offering2_id,
            tenant_id=tenant_id,
            module_id=module2_id,
            academic_period_id=period_id,
            org_unit_id=department_id,
            offering_code="NET201-2026-S1",
            delivery_mode="blended",
        )
    )
    for sequence, (code, statement, cognitive) in enumerate((
        ("LO1", "Describe OSI and TCP/IP network models relevant to IoT deployments.", "understand"),
        ("LO2", "Configure basic IP addressing and subnetting for IoT device networks.", "apply"),
    ), start=1):
        session.merge(
            LearningOutcome(
                id=stable_id(f"{slug}:learning-outcome:net201-{code.lower()}"),
                tenant_id=tenant_id,
                module_id=module2_id,
                outcome_code=code,
                statement=statement,
                cognitive_level=cognitive,
                sequence_order=sequence,
            )
        )

    # Programme containing both modules
    programme_id = stable_id(f"{slug}:programme:diot")
    session.merge(
        Programme(
            id=programme_id,
            tenant_id=tenant_id,
            owning_unit_id=department_id,
            code="DIOT",
            name="Diploma in Internet of Things",
            delivery_mode="blended",
            attributes={"synthetic_demo": True},
        )
    )
    for pm_module_id, year, semester, core in (
        (module_id, 1, "S1", True),
        (module2_id, 2, "S1", True),
    ):
        session.merge(
            ProgrammeModule(
                tenant_id=tenant_id,
                programme_id=programme_id,
                module_id=pm_module_id,
                study_year=year,
                semester_or_term=semester,
                is_core=core,
            )
        )

    users = {
        "admin": "institution_administrator",
        "hod": "head_of_department",
        "lecturer": "lecturer",
        "moderator": "internal_moderator",
        "external": "external_reviewer",
        "modcoord": "module_coordinator",
        "progcoord": "programme_coordinator",
        "extmod": "external_moderator",
    }
    for handle, role_code in users.items():
        user_id = stable_id(f"{slug}:user:{handle}")
        email = f"{handle}.{slug}@example.com"
        session.merge(
            User(
                id=user_id,
                email=email,
                email_normalized=email,
                given_name=handle.title(),
                family_name="Demonstration",
                display_name=f"{handle.title()} Demonstration",
                is_active=True,
                profile={"synthetic_demo": True},
            )
        )
        session.merge(
            PasswordCredential(
                id=stable_id(f"{slug}:credential:{handle}"),
                user_id=user_id,
                password_hash=PasswordManager().hash(demo_password),
                password_changed_at=datetime.now(timezone.utc),
                must_change_password=True,
            )
        )
        session.merge(
            Membership(
                id=stable_id(f"{slug}:membership:{handle}"),
                tenant_id=tenant_id,
                user_id=user_id,
                institutional_identifier=f"DEMO-{handle.upper()}",
                position_title=role_code.replace("_", " ").title(),
                status="active",
                joined_at=datetime.now(timezone.utc),
            )
        )
        scope_id = stable_id(f"{slug}:scope:{handle}")
        scope_type = "institution" if role_code == "institution_administrator" else "organisational_unit"
        scoped_resource = None if scope_type == "institution" else department_id
        if role_code.startswith("external_"):
            scope_type = "module"
            scoped_resource = module_id
        # Academic roles need include_descendants so their department scope covers
        # module offerings, modules, and programmes within that department.
        descendant_roles = {"head_of_department", "lecturer", "internal_moderator",
                            "module_coordinator", "programme_coordinator"}
        # external_moderator is scoped to the IOT101 module like external_reviewer
        if role_code == "external_moderator":
            scope_type = "module"
            scoped_resource = module_id
        session.merge(
            AccessScope(
                id=scope_id,
                tenant_id=tenant_id,
                scope_type=scope_type,
                scope_id=scoped_resource,
                include_descendants=role_code in descendant_roles,
                constraints={"synthetic_demo": True},
            )
        )
        session.merge(
            RoleAssignment(
                id=stable_id(f"{slug}:role-assignment:{handle}"),
                tenant_id=tenant_id,
                user_id=user_id,
                role_id=stable_id(f"role:{role_code}"),
                access_scope_id=scope_id,
                assigned_by_user_id=stable_id(f"{slug}:user:admin"),
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                reason="Synthetic v2.5 demonstration assignment.",
            )
        )

    # Coordinator assignments
    session.merge(
        CoordinatorAssignment(
            id=stable_id(f"{slug}:coord-assign:modcoord:iot101"),
            tenant_id=tenant_id,
            user_id=stable_id(f"{slug}:user:modcoord"),
            coordinator_type="module_coordinator",
            target_type="module",
            target_id=module_id,
            assigned_by_user_id=stable_id(f"{slug}:user:hod"),
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="active",
        )
    )
    session.merge(
        CoordinatorAssignment(
            id=stable_id(f"{slug}:coord-assign:progcoord:diot"),
            tenant_id=tenant_id,
            user_id=stable_id(f"{slug}:user:progcoord"),
            coordinator_type="programme_coordinator",
            target_type="programme",
            target_id=programme_id,
            assigned_by_user_id=stable_id(f"{slug}:user:hod"),
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status="active",
        )
    )

    # External moderator grant and review task
    ext_mod_grant_id = stable_id(f"{slug}:ext-grant:extmod:iot101")
    session.merge(
        ExternalAccessGrant(
            id=ext_mod_grant_id,
            tenant_id=tenant_id,
            external_user_id=stable_id(f"{slug}:user:extmod"),
            granted_by_user_id=stable_id(f"{slug}:user:hod"),
            purpose="Synthetic external moderation of IOT101 assessment for demonstration validation.",
            status="active",
            starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            expires_at=datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc),
            allowed_actions=["read_review_pack", "record_finding", "submit_recommendation"],
            resource_scope={
                "module_id": str(module_id),
                "module_code": "IOT101",
                "synthetic_demo": True,
            },
        )
    )
    session.merge(
        AssignedReviewTask(
            id=stable_id(f"{slug}:review-task:extmod:iot101"),
            tenant_id=tenant_id,
            assigned_user_id=stable_id(f"{slug}:user:extmod"),
            assigned_by_user_id=stable_id(f"{slug}:user:hod"),
            external_access_grant_id=ext_mod_grant_id,
            reviewer_role_code="external_moderator",
            review_kind="external_moderation",
            task_type="moderation_review",
            target_type="module",
            target_id=module_id,
            status="assigned",
            instructions=(
                "Review the IOT101 assessment portfolio for alignment with Diploma Year 1 "
                "learning outcomes, mark allocation, cognitive-level coverage, and rubric clarity. "
                "Record all findings with evidence locators. Submit an immutable recommendation."
            ),
            permissions_snapshot={"synthetic_demo": True},
            task_metadata={"synthetic_demo": True, "release": "2.5.0"},
        )
    )

    # v2.2 non-secret commercial configuration and governed AI defaults.
    system_user_id = stable_id(f"{slug}:user:admin")
    for category, key, value, value_type in (
        ("institution", "default_locale", {"value": "en-GB"}, "json"),
        ("appearance", "default_theme", {"value": "system"}, "json"),
        ("terminology", "module_label", {"singular": "Module", "plural": "Modules"}, "json"),
        ("analytics", "default_period_days", {"value": 30}, "json"),
    ):
        session.merge(
            PlatformSetting(
                id=stable_id(f"{slug}:setting:{category}:{key}"),
                tenant_id=tenant_id,
                scope_type="institution",
                scope_id=None,
                category=category,
                setting_key=key,
                value=value,
                value_type=value_type,
                description="Synthetic demonstration configuration.",
                secret_reference_only=False,
                locked=False,
                version_number=1,
                updated_by_user_id=system_user_id,
            )
        )
    session.merge(
        AIUsagePolicy(
            id=stable_id(f"{slug}:ai-policy:default"),
            tenant_id=tenant_id,
            name="Default governed multi-provider policy",
            scope_type="institution",
            scope_id=None,
            allowed_providers=["ollama", "anthropic", "openai", "google_gemini", "deepseek"],
            denied_providers=[],
            local_only_privacy_classes=["confidential", "restricted_assessment"],
            source_required_for_tasks=["examination", "moderation_review", "alignment_review"],
            monthly_request_limit=None,
            monthly_input_token_limit=None,
            monthly_output_token_limit=None,
            monthly_cost_limit=None,
            currency_code="GBP",
            warning_threshold_percent=80,
            hard_limit_enabled=False,
            is_active=True,
            policy_metadata={"synthetic_demo": True},
            created_by_user_id=system_user_id,
        )
    )
    for code, name, report_type in (
        ("teaching_operations", "Teaching Operations Summary", "teaching_operations_summary"),
        ("module_readiness", "Module Readiness Summary", "module_readiness_summary"),
        ("moderation_progress", "Moderation Progress", "moderation_progress"),
        ("ai_usage_governance", "AI Usage Governance", "ai_usage_governance"),
    ):
        session.merge(
            ReportDefinition(
                id=stable_id(f"{slug}:report-definition:{code}"),
                tenant_id=tenant_id,
                code=code,
                name=name,
                report_type=report_type,
                description="Synthetic demonstration report definition.",
                default_scope_type="institution",
                default_parameters={"period_days": 30},
                allowed_formats=["json", "csv", "pdf"],
                owner_user_id=system_user_id,
                shared=True,
                is_active=True,
            )
        )

    today = datetime.now(timezone.utc).date()
    session.merge(
        AIUsageDaily(
            id=stable_id(f"{slug}:ai-usage:{today.isoformat()}:lecturer:qwen3"),
            tenant_id=tenant_id,
            usage_date=today,
            user_id=stable_id(f"{slug}:user:lecturer"),
            provider="ollama",
            model_id="qwen3:8b",
            role_code="lecturer",
            task_type="lesson_plan",
            request_count=3,
            successful_count=3,
            failed_count=0,
            input_tokens=1800,
            output_tokens=3200,
            estimated_cost=Decimal("0.0000"),
            currency_code="GBP",
            latency_total_ms=12400,
        )
    )
    for alert_key, scope_type, scope_id, title, message in (
        ("institution_governance", "institution", None, "Review AI usage governance", "Confirm provider policy and source requirements before the pilot validation."),
        ("department_readiness", "organisational_unit", department_id, "Module readiness needs attention", "IOT101 demonstration readiness evidence is incomplete."),
        ("lecturer_materials", "user", stable_id(f"{slug}:user:lecturer"), "Complete the semester teaching pack", "Upload the remaining teaching plan and assessment support materials."),
    ):
        session.merge(
            InsightAlert(
                id=stable_id(f"{slug}:insight-alert:{alert_key}"),
                tenant_id=tenant_id,
                category="operational_readiness",
                severity="warning",
                status="open",
                scope_type=scope_type,
                scope_id=scope_id,
                title=title,
                message=message,
                metric_key="readiness_attention",
                metric_value=Decimal("1"),
                threshold_value=Decimal("0"),
                action_path="action:moduleReadiness",
                detected_at=datetime.now(timezone.utc),
                alert_metadata={"synthetic_demo": True, "release": "2.2.0"},
            )
        )


    session.merge(
        LecturerAssignment(
            id=stable_id(f"{slug}:lecturer-assignment:iot101"),
            tenant_id=tenant_id,
            user_id=stable_id(f"{slug}:user:lecturer"),
            module_offering_id=offering_id,
            assigned_by_user_id=stable_id(f"{slug}:user:hod"),
            responsibility_type="primary_lecturer",
            workload_percentage=Decimal("100.00"),
            status="active",
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )

    demo_notifications = {
        "admin": ("tenant_onboarding", "Institution workspace ready", "The synthetic institution, roles, and academic structure are ready for validation.", "success", "action:structure"),
        "hod": ("module_readiness_risk", "Review module readiness", "IOT101 requires a teaching plan and assessment evidence before the demonstration period begins.", "warning", "action:moduleReadiness"),
        "lecturer": ("module_assignment", "You were assigned IOT101", "Prepare the teaching plan and upload the semester teaching pack from the unified work area.", "information", "action:teachingPlan"),
        "moderator": ("review_assignment", "Moderation task awaiting review", "A synthetic moderation scenario is available for owner-machine workflow validation.", "information", "action:reviewTasks"),
        "external": ("temporary_access", "External review access is limited", "Your demonstration access is restricted to the assigned review task and its evidence.", "warning", "action:reviewTasks"),
        "modcoord": ("module_assignment", "You are coordinating IOT101", "Review module learning outcomes, teaching outputs, and readiness evidence for IOT101.", "information", "action:moduleReadiness"),
        "progcoord": ("programme_assignment", "You are coordinating DIOT programme", "Review cross-module alignment and programme readiness for the Diploma in Internet of Things.", "information", "action:moduleReadiness"),
        "extmod": ("temporary_access", "External moderation access active", "Your temporary access covers IOT101 assessment moderation only. Access expires 30 September 2026.", "warning", "action:reviewTasks"),
    }
    for handle, (kind, title, body, severity, action_path) in demo_notifications.items():
        session.merge(
            Notification(
                id=stable_id(f"{slug}:notification:{handle}:v21"),
                tenant_id=tenant_id,
                recipient_user_id=stable_id(f"{slug}:user:{handle}"),
                notification_type=kind,
                title=title,
                body=body,
                severity=severity,
                action_path=action_path,
                notification_metadata={"synthetic_demo": True, "release": "2.1.0"},
            )
        )


def main() -> None:
    url = os.getenv(
        "MIGRATION_DATABASE_URL",
        "postgresql+psycopg://lsa_owner:change-owner-password@localhost:5432/lecturer_support_agent",
    )
    demo_password = _resolve_demo_password()
    engine = create_engine(url)
    with Session(engine) as session, session.begin():
        seed_catalogue(session)
        seed_tenant(session, "demo-north", "North Demonstration University", "ZA", demo_password=demo_password)
        seed_tenant(session, "demo-south", "South Demonstration Institute", "ZA", demo_password=demo_password)
    print("Seeded role catalogue and two isolated synthetic demonstration tenants.")
    print(f"Credentials written to: {_CRED_FILE.resolve()}")


if __name__ == "__main__":
    main()
