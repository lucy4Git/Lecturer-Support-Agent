from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.app.core.request_context import RequestContext
from services.api.app.integrations.object_storage import InMemoryObjectStorage
from services.api.app.services.document_versioning import DocumentVersioningService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_new_content_creates_append_only_versions() -> None:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL is not configured")
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    tenant_id = UUID("88c37d6a-b76f-5ee4-9c02-75e4fdcac2aa")
    user_id = UUID("dbaa170b-37d5-530d-89fe-31ded307b3d9")
    module_id = UUID("863d1777-6d2f-5bc1-9271-a3545676e9a0")
    context = RequestContext(tenant_id, user_id, "lecturer", "test-correlation")
    try:
        async with factory() as session, session.begin():
            await session.execute(__import__("sqlalchemy").text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            service = DocumentVersioningService(session=session, storage=InMemoryObjectStorage(), context=context)
            first = await service.create_version(
                title="Test lesson", document_type="lesson_plan", filename="lesson.txt",
                content=b"first", media_type="text/plain", change_reason="initial",
                module_id=module_id,
            )
            second = await service.create_version(
                title="Test lesson", document_type="lesson_plan", filename="lesson.txt",
                content=b"second", media_type="text/plain", change_reason="revision",
                document_id=first.document.id, module_id=module_id,
            )
            assert first.version.version_number == 1
            assert second.version.version_number == 2
            assert second.version.previous_version_id == first.version.id
            await session.rollback()
    finally:
        await engine.dispose()
