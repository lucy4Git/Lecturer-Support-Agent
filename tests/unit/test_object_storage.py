from uuid import UUID

import pytest

from services.api.app.integrations.object_storage import InMemoryObjectStorage, build_object_key


@pytest.mark.asyncio
async def test_in_memory_storage_preserves_versions() -> None:
    tenant = UUID("11111111-1111-1111-1111-111111111111")
    store = InMemoryObjectStorage()
    first = await store.put_bytes(
        tenant_id=tenant,
        object_key="one/file.txt",
        content=b"version one",
        media_type="text/plain",
    )
    second = await store.put_bytes(
        tenant_id=tenant,
        object_key="one/file.txt",
        content=b"version two",
        media_type="text/plain",
    )
    assert first.storage_version_id != second.storage_version_id
    assert await store.get_bytes(object_key=first.object_key, version_id=first.storage_version_id) == b"version one"
    assert await store.get_bytes(object_key=second.object_key, version_id=second.storage_version_id) == b"version two"


def test_object_key_is_tenant_and_version_scoped() -> None:
    tenant = UUID("11111111-1111-1111-1111-111111111111")
    document = UUID("22222222-2222-2222-2222-222222222222")
    key = build_object_key(
        tenant_id=tenant,
        document_id=document,
        version_number=3,
        filename="IoT Practical Guide (final).docx",
    )
    assert key == (
        f"tenants/{tenant}/documents/{document}/versions/3/IoT_Practical_Guide__final_.docx"
    )
