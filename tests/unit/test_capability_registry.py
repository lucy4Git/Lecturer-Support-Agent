"""Unit tests for CapabilityRegistry intent patterns and PendingActionStore."""
from __future__ import annotations

import asyncio
import time
from uuid import UUID, uuid4

import pytest

from services.api.app.ai.capability_registry import (
    _WORKLOAD_RE,
    _ASSIGN_LECTURER_RE,
    _STRUCTURE_QUERY_RE,
    _CREATE_UNIT_RE,
    _MY_MODULES_RE,
    _MY_REVIEWS_RE,
    _CONFIRM_RE,
    _CANCEL_RE,
)
from services.api.app.services.pending_actions import PendingActionStore


# ---------------------------------------------------------------------------
# Intent regex pattern tests
# ---------------------------------------------------------------------------

class TestWorkloadPattern:
    def _match(self, text: str) -> bool:
        return bool(_WORKLOAD_RE.search(text))

    def test_workload_keyword(self) -> None:
        assert self._match("show workload of lecturers")

    def test_teaching_load(self) -> None:
        assert self._match("what is the teaching load this semester?")

    def test_unassigned_module(self) -> None:
        assert self._match("which modules have no lecturer assigned?")

    def test_no_match_on_random(self) -> None:
        assert not self._match("please help me write a quiz")


class TestAssignLecturerPattern:
    def _match(self, text: str) -> bool:
        return bool(_ASSIGN_LECTURER_RE.search(text))

    def test_assign_lecturer(self) -> None:
        assert self._match("assign Dr Smith as the lecturer for CS101")

    def test_allocate_staff(self) -> None:
        assert self._match("allocate a staff member to CS101")

    def test_appoint_lecturer(self) -> None:
        assert self._match("appoint a lecturer for MATH201")

    def test_no_match_on_create(self) -> None:
        assert not self._match("create a new department")


class TestStructureQueryPattern:
    def _match(self, text: str) -> bool:
        return bool(_STRUCTURE_QUERY_RE.search(text))

    def test_show_departments(self) -> None:
        assert self._match("show me all departments in this institution")

    def test_list_faculties(self) -> None:
        assert self._match("list all faculties")

    def test_display_structure(self) -> None:
        assert self._match("display institutional structure")

    def test_no_match_on_workload(self) -> None:
        assert not self._match("what is the lecturer workload?")


class TestCreateUnitPattern:
    def _match(self, text: str) -> bool:
        return bool(_CREATE_UNIT_RE.search(text))

    def test_create_department(self) -> None:
        assert self._match("create a new department called Engineering")

    def test_create_faculty(self) -> None:
        assert self._match("create a faculty of science")

    def test_no_match_on_show(self) -> None:
        assert not self._match("show me the department list")


class TestMyModulesPattern:
    def _match(self, text: str) -> bool:
        return bool(_MY_MODULES_RE.search(text))

    def test_my_modules(self) -> None:
        assert self._match("show my modules")

    def test_modules_i_coordinate(self) -> None:
        assert self._match("modules i coordinate this semester")

    def test_no_match_on_all_modules(self) -> None:
        assert not self._match("list all modules in the system")


class TestMyReviewsPattern:
    def _match(self, text: str) -> bool:
        return bool(_MY_REVIEWS_RE.search(text))

    def test_my_moderation(self) -> None:
        assert self._match("show my moderation tasks")

    def test_my_review(self) -> None:
        assert self._match("what are my assigned review tasks?")

    def test_no_match_on_unrelated(self) -> None:
        assert not self._match("how do I write a rubric?")


class TestConfirmCancelPatterns:
    def test_confirm_valid_uuid(self) -> None:
        token = "3a8c1234-abcd-4ef0-9123-456789abcdef"
        m = _CONFIRM_RE.match(f"__confirm__{token}")
        assert m is not None
        assert m.group(1) == token

    def test_cancel_valid_uuid(self) -> None:
        token = "3a8c1234-abcd-4ef0-9123-456789abcdef"
        m = _CANCEL_RE.match(f"__cancel__{token}")
        assert m is not None
        assert m.group(1) == token

    def test_confirm_rejects_non_uuid(self) -> None:
        assert _CONFIRM_RE.match("__confirm__not-a-uuid") is None

    def test_cancel_rejects_plain_text(self) -> None:
        assert _CANCEL_RE.match("__cancel__yes please") is None


# ---------------------------------------------------------------------------
# PendingActionStore
# ---------------------------------------------------------------------------

class TestPendingActionStore:
    def setup_method(self) -> None:
        PendingActionStore._instance = None  # fresh instance per test

    @pytest.mark.asyncio
    async def test_create_and_claim(self) -> None:
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid,
            tenant_id=tid,
            action_type="assign_lecturer",
            payload={"lecturer_user_id": str(uuid4()), "module_offering_id": str(uuid4())},
            label="Confirm Assignment",
            details=[{"key": "Lecturer", "value": "Dr Smith"}],
        )
        assert len(token) == 36  # UUID4 string

        action = await store.claim(token=token, user_id=uid, tenant_id=tid)
        assert action is not None
        assert action.action_type == "assign_lecturer"
        assert action.label == "Confirm Assignment"

    @pytest.mark.asyncio
    async def test_claim_removes_token(self) -> None:
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid, tenant_id=tid, action_type="test", payload={},
            label="L", details=[],
        )
        await store.claim(token=token, user_id=uid, tenant_id=tid)
        # Second claim returns None (token consumed)
        assert await store.claim(token=token, user_id=uid, tenant_id=tid) is None

    @pytest.mark.asyncio
    async def test_wrong_user_cannot_claim(self) -> None:
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid, tenant_id=tid, action_type="test", payload={},
            label="L", details=[],
        )
        assert await store.claim(token=token, user_id=uuid4(), tenant_id=tid) is None

    @pytest.mark.asyncio
    async def test_wrong_tenant_cannot_claim(self) -> None:
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid, tenant_id=tid, action_type="test", payload={},
            label="L", details=[],
        )
        assert await store.claim(token=token, user_id=uid, tenant_id=uuid4()) is None

    @pytest.mark.asyncio
    async def test_cancel_removes_token(self) -> None:
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid, tenant_id=tid, action_type="test", payload={},
            label="L", details=[],
        )
        ok = await store.cancel(token=token, user_id=uid, tenant_id=tid)
        assert ok is True
        assert await store.claim(token=token, user_id=uid, tenant_id=tid) is None

    @pytest.mark.asyncio
    async def test_cancel_wrong_user_fails(self) -> None:
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid, tenant_id=tid, action_type="test", payload={},
            label="L", details=[],
        )
        ok = await store.cancel(token=token, user_id=uuid4(), tenant_id=tid)
        assert ok is False
        # Token still valid for real owner
        assert await store.claim(token=token, user_id=uid, tenant_id=tid) is not None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self) -> None:
        """Tokens expire after TTL; directly set expires_at to force expiry."""
        store = PendingActionStore.get()
        uid = uuid4()
        tid = uuid4()
        token = await store.create(
            user_id=uid, tenant_id=tid, action_type="test", payload={},
            label="L", details=[],
        )
        # Force expiry
        async with store._lock:
            store._store[token].expires_at = time.monotonic() - 1

        result = await store.claim(token=token, user_id=uid, tenant_id=tid)
        assert result is None  # expired

    @pytest.mark.asyncio
    async def test_singleton(self) -> None:
        assert PendingActionStore.get() is PendingActionStore.get()
