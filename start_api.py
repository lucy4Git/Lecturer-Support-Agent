"""Start the API with SelectorEventLoop — required for psycopg3 async on Windows."""
import asyncio
import sys

if sys.platform == "win32":
    # Must be set BEFORE asyncio.run() so Runner uses WindowsSelectorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(
        "services.api.app.main:app",
        host="127.0.0.1",
        port=8001,
        log_level="warning",
        loop="none",  # suppress uvicorn loop_factory; asyncio.run() uses current policy
    )
    server = uvicorn.Server(config)
    # Bypass server.run() (which passes loop_factory to asyncio_run) and call
    # asyncio.run(server.serve()) directly so our WindowsSelectorEventLoopPolicy is used.
    asyncio.run(server.serve())
