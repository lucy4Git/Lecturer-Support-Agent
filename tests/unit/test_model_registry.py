from services.database.models import Base


def test_cumulative_model_registry_contains_all_foundation_tables() -> None:
    tables = set(Base.metadata.tables)
    assert len(tables) >= 90
    assert {
        "tenant.institutions",
        "iam.role_assignments",
        "iam.password_credentials",
        "iam.authentication_sessions",
        "iam.user_invitations",
        "iam.position_definitions",
        "iam.membership_positions",
        "academic.lecturer_assignments",
        "content.document_versions",
        "ingestion.upload_batches",
        "conversation.conversations",
        "ai.model_executions",
        "source.citations",
        "review.external_access_grants",
        "audit.audit_events",
    }.issubset(tables)


def test_every_tenant_owned_table_has_tenant_id() -> None:
    tenant_schemas = {
        "tenant", "iam", "academic", "ingestion", "content", "conversation",
        "ai", "source", "review", "audit", "privacy", "governance", "analytics",
    }
    global_tables = {
        "tenant.institutions",
        "iam.users",
        "iam.password_credentials",
        "iam.roles",
        "iam.permissions",
        "iam.role_permissions",
    }
    for key, table in Base.metadata.tables.items():
        if table.schema in tenant_schemas and key not in global_tables:
            assert "tenant_id" in table.columns, f"{key} must be tenant-owned or explicitly global"
