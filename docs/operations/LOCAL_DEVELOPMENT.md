# Local Development

Provide reproducible scripts and Docker Compose, but never auto-launch Docker Desktop. Developers explicitly start required infrastructure. Seed data must be synthetic and tenant-safe.

---

## Starting the API on Windows

Always use the dedicated launcher — never invoke uvicorn directly:

```
python services/api/run_api.py
```

The launcher applies two complementary guards before uvicorn starts:

1. `asyncio.WindowsSelectorEventLoopPolicy()` — sets the global asyncio policy.
2. `loop=asyncio.SelectorEventLoop` passed to `uvicorn.run()` — uvicorn 0.49
   accepts any callable as a `LoopFactoryType` and forwards it to
   `asyncio.run(loop_factory=...)`, guaranteeing a `SelectorEventLoop` regardless
   of platform defaults.

### Why this is necessary

Python 3.8+ defaults to `ProactorEventLoop` on Windows. psycopg3's async driver
cannot run on `ProactorEventLoop` and raises:

```
psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in
async mode.
```

Invoking uvicorn directly (`uvicorn services.api.app.main:app`) bypasses the
`loop=asyncio.SelectorEventLoop` guard in `run_api.py` and will reproduce the
error even if `main.py` sets the policy, because uvicorn may consult the platform
before the policy takes effect.

### Validation

After starting the API, confirm all probes pass:

```
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Both must return HTTP 200. If the PostgreSQL probe reports `InterfaceError`, the
server was not started via `services/api/run_api.py`.

### Pulling the embedding model (first time)

```
ollama pull nomic-embed-text-v2-moe
```

The generation model (`qwen3:8b`) and general chat model (`mistral:latest`,
`llama3.1:8b`) are pulled separately. Ingestion embedding will fail until
`nomic-embed-text-v2-moe` is available.
