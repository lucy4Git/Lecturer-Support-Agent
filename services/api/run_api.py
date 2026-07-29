"""
Lecturer Support Agent — API launcher for Windows and POSIX.

On Windows, Python 3.8+ defaults to ProactorEventLoop which psycopg3 cannot
use for async operations.  Two complementary guards are applied here:

1. asyncio.WindowsSelectorEventLoopPolicy() — sets the global policy so that
   any asyncio.get_event_loop() / asyncio.new_event_loop() call returns a
   SelectorEventLoop.

2. loop=asyncio.SelectorEventLoop is passed to uvicorn.  Uvicorn 0.29+ accepts
   a LoopFactoryType (any callable → AbstractEventLoop) for its ``loop``
   parameter and forwards it as loop_factory to asyncio.run().  This overrides
   the platform default even when the global policy is not consulted.

Both guards are set BEFORE uvicorn or SQLAlchemy are imported so that no
ProactorEventLoop is ever created.

Usage (development):
    python services/api/run_api.py

Usage (production — prefer the Docker entrypoint over this script):
    python services/api/run_api.py --host 0.0.0.0 --port 8000 --workers 4
"""
from __future__ import annotations

import argparse
import asyncio
import sys

# Guard 1 — global loop policy (affects asyncio.run(), get_event_loop(), etc.)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # imported AFTER the policy is applied


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the Lecturer Support Agent API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", default=False)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--env-file", default=".env")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse()

    # Guard 2 — explicit loop factory passed to uvicorn (uvicorn 0.29+).
    # Uvicorn 0.49 accepts LoopFactoryType (callable → AbstractEventLoop) for
    # the ``loop`` parameter and forwards it to asyncio.run(loop_factory=...).
    # Passing asyncio.SelectorEventLoop directly guarantees a SelectorEventLoop
    # is created on Windows regardless of any platform-detection inside uvicorn.
    loop_arg: object = asyncio.SelectorEventLoop if sys.platform == "win32" else "auto"

    uvicorn.run(
        "services.api.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        env_file=args.env_file,
        log_level="info",
        loop=loop_arg,
    )
