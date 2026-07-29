"""Windows startup wrapper: sets SelectorEventLoopPolicy before uvicorn creates the loop."""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402

if __name__ == "__main__":
    # loop="none" tells uvicorn not to override the event loop factory,
    # letting our WindowsSelectorEventLoopPolicy above take effect.
    # "asyncio" on Windows forces ProactorEventLoop — that breaks psycopg3.
    uvicorn.run(
        "services.api.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        loop="none",
    )
