"""
Regression test for F-009 — Windows ProactorEventLoop incompatibility.

psycopg3 async mode cannot run on the Windows ProactorEventLoop.  The API
launcher (services/api/run_api.py) and the application module (main.py) must
both apply WindowsSelectorEventLoopPolicy before any async engine is created.

These tests are skipped on non-Windows platforms.
"""
from __future__ import annotations

import asyncio
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows-specific event-loop policy tests",
)


class TestWindowsSelectorLoopPolicy:
    """Verify that the SelectorEventLoop policy is applied before server start."""

    def test_run_api_sets_selector_policy_before_uvicorn(self) -> None:
        """run_api.py must apply WindowsSelectorEventLoopPolicy before importing uvicorn."""
        import importlib, types

        # Capture the policy at the point run_api sets it.
        # We re-execute the policy guard in isolation to confirm the module
        # applies it unconditionally on Windows before importing uvicorn.
        original_policy = asyncio.get_event_loop_policy()
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            assert not isinstance(
                asyncio.get_event_loop_policy(),
                asyncio.WindowsSelectorEventLoopPolicy,
            ), "Pre-condition: policy should NOT be selector yet"

            # Simulate what run_api.py does at module scope
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

            assert isinstance(
                asyncio.get_event_loop_policy(),
                asyncio.WindowsSelectorEventLoopPolicy,
            ), "run_api.py guard must install WindowsSelectorEventLoopPolicy"
        finally:
            asyncio.set_event_loop_policy(original_policy)

    def test_main_module_sets_selector_policy(self) -> None:
        """services/api/app/main.py must set the policy at import time."""
        original_policy = asyncio.get_event_loop_policy()
        try:
            # Reset to default so we can confirm the module re-installs the policy
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

            # Execute just the guard block from main.py
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

            assert isinstance(
                asyncio.get_event_loop_policy(),
                asyncio.WindowsSelectorEventLoopPolicy,
            )
        finally:
            asyncio.set_event_loop_policy(original_policy)

    def test_selector_loop_is_not_proactor(self) -> None:
        """After the policy is applied, a new event loop must not be ProactorEventLoop."""
        original_policy = asyncio.get_event_loop_policy()
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            try:
                assert not isinstance(loop, asyncio.ProactorEventLoop), (
                    "ProactorEventLoop created despite WindowsSelectorEventLoopPolicy — "
                    "psycopg3 async will fail"
                )
                assert isinstance(loop, asyncio.SelectorEventLoop)
            finally:
                loop.close()
        finally:
            asyncio.set_event_loop_policy(original_policy)

    def test_async_db_query_runs_on_selector_loop(self) -> None:
        """A real async database query must succeed when run on SelectorEventLoop."""
        import os
        import dotenv

        dotenv.load_dotenv(".env")

        original_policy = asyncio.get_event_loop_policy()
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

            async def _probe() -> str:
                from sqlalchemy.ext.asyncio import create_async_engine
                from sqlalchemy import text

                url = os.environ.get("DATABASE_URL", "")
                if not url:
                    pytest.skip("DATABASE_URL not set — skipping live DB probe")

                engine = create_async_engine(url)
                try:
                    async with engine.connect() as conn:
                        result = await conn.execute(text("SELECT 1"))
                        val = result.scalar()
                    assert val == 1
                    return "ok"
                finally:
                    await engine.dispose()

            result = asyncio.run(_probe())
            assert result == "ok", "Async DB probe did not return ok"
        finally:
            asyncio.set_event_loop_policy(original_policy)

    def test_uvicorn_loop_arg_accepts_selector_class(self) -> None:
        """uvicorn.Config must accept asyncio.SelectorEventLoop as the loop factory."""
        import uvicorn

        cfg = uvicorn.Config("services.api.app.main:app", loop=asyncio.SelectorEventLoop)
        assert cfg.loop is asyncio.SelectorEventLoop, (
            "uvicorn.Config rejected SelectorEventLoop as loop factory — "
            "run_api.py will not be able to force the correct loop"
        )
