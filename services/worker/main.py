from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket

from sqlalchemy.ext.asyncio import async_sessionmaker

from services.api.app.core.database import get_worker_engine
from services.api.app.observability.logging import configure_logging
from services.api.app.services.job_queue import JobQueueService

from .handlers import HANDLERS

logger = logging.getLogger("lsa.worker")


async def run_worker(*, queue_name: str, poll_seconds: float, once: bool) -> None:
    factory = async_sessionmaker(get_worker_engine(), expire_on_commit=False)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    while True:
        async with factory() as session:
            async with session.begin():
                queue = JobQueueService(session)
                await queue.recover_expired_service_leases()
                await queue.enqueue_due_schedules_service_worker()
                claimed = await queue.claim_next_service_worker(worker_id=worker_id, queue_name=queue_name)
                if claimed is None:
                    if once:
                        return
                else:
                    handler = HANDLERS.get(claimed.job.job_type)
                    try:
                        if handler is None:
                            raise RuntimeError("No handler is registered for the claimed job type.")
                        result = await handler(session, claimed.job)
                        await queue.succeed(claimed, result)
                        logger.info("job.completed", extra={"event": "job.completed", "job_id": str(claimed.job.id), "job_type": claimed.job.job_type})
                    except Exception as exc:
                        logger.exception("job.failed", extra={"event": "job.failed", "job_id": str(claimed.job.id), "job_type": claimed.job.job_type})
                        await queue.fail(claimed, error_code=type(exc).__name__, safe_error_detail=str(exc))
        if once:
            return
        await asyncio.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lecturer Support Agent durable background worker")
    parser.add_argument("--queue", default="default")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"), json_logs=True)
    import sys, selectors
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_worker(queue_name=args.queue, poll_seconds=args.poll_seconds, once=args.once))


if __name__ == "__main__":
    main()
