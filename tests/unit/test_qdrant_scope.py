from uuid import UUID

from services.api.app.integrations.qdrant import RetrievalScope, build_tenant_filter

TENANT = UUID("11111111-1111-1111-1111-111111111111")
USER = UUID("22222222-2222-2222-2222-222222222222")
MODULE = UUID("33333333-3333-3333-3333-333333333333")


def test_private_filter_always_contains_tenant() -> None:
    result = build_tenant_filter(
        RetrievalScope(
            tenant_id=TENANT,
            user_id=USER,
            allowed_module_ids=(MODULE,),
            include_public=False,
        )
    )
    tenant_conditions = [item for item in result["must"] if item.get("key") == "tenant_id"]
    assert tenant_conditions == [{"key": "tenant_id", "match": {"value": str(TENANT)}}]


def test_public_branch_does_not_remove_private_tenant_constraint() -> None:
    result = build_tenant_filter(RetrievalScope(tenant_id=TENANT, user_id=USER))
    private_branch = result["should"][0]
    assert {"key": "tenant_id", "match": {"value": str(TENANT)}} in private_branch["must"]
    assert result["should"][1]["must"][0]["match"]["value"] == "public"
