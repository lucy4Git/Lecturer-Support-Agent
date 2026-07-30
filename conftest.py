from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv(override=False)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
