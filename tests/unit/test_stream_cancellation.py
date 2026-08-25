"""Proves the client-disconnect cancellation contract used by
ConversationEngine.stream_message, in isolation from the real DB/provider
stack (which the existing test suite has no fixtures for).

The real generator's structure is: one big `try: ... except Exception: yield
error-frame; return` wrapping an `async for token in self.router.stream(...)`
loop, where each provider adapter opens its HTTP connection via
`async with httpx.AsyncClient(...) as client: async with client.stream(...) as
response: ...`.

When a browser aborts a fetch, Starlette's StreamingResponse detects the
failed ASGI `send()` and calls `.aclose()` on the response body iterator —
this is exactly how FastAPI/Starlette handle client disconnects for streaming
responses, and it is NOT something application code opts into; it happens
automatically. `.aclose()` raises `GeneratorExit` at the generator's current
suspension point (inside the `yield`).

These tests reproduce that exact mechanism against a minimal generator with
the same try/except shape and the same async-with-managed upstream resource,
to prove — not merely assert — that:

1. `except Exception` does not swallow `GeneratorExit` (it is a BaseException,
   not an Exception subclass), so cancellation is never misreported as a
   provider/persistence error.
2. No "done" event is ever yielded after cancellation.
3. The upstream resource (standing in for httpx's connection) is actually
   closed, via the same `async with` unwinding Python guarantees during
   GeneratorExit propagation.
"""
from __future__ import annotations

import asyncio

import pytest

from services.api.app.services.conversation_engine import (
    _ClientDisconnected,
    _consume_cancellable,
)


class FakeUpstreamConnection:
    """Stands in for httpx.AsyncClient's `async with client.stream(...)`."""

    def __init__(self) -> None:
        self.closed = False
        self.entered = False

    async def __aenter__(self) -> "FakeUpstreamConnection":
        self.entered = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True


async def _wait_for(predicate, *, max_ticks: int = 50) -> bool:
    """Cleanup of a nested async generator's `async with` block on GeneratorExit
    is NOT synchronous with the outer generator's `.aclose()` call — CPython
    finalizes it via the event loop's async-generator finalizer hook, which
    runs a few ticks later. Measured empirically at ~2 ticks (sub-millisecond)
    in this exact nested async-for/async-with shape; this waits generously
    rather than assuming a fixed number, and this timing detail is exactly
    why "GeneratorExit bypasses except Exception" alone was an insufficient
    proof of prompt backend cleanup — eventual is not the same as immediate."""
    for _ in range(max_ticks):
        if predicate():
            return True
        await asyncio.sleep(0)
    return False


async def fake_provider_generate_stream(connection: FakeUpstreamConnection, token_count: int = 1000):
    """Mirrors OllamaProvider/OpenAIProvider.generate_stream's shape: opens a
    connection via `async with`, yields tokens indefinitely until told to stop."""
    async with connection:
        for i in range(token_count):
            yield f"token-{i}"
            await asyncio.sleep(0.005)


async def stream_response_like(connection: FakeUpstreamConnection, *, raise_after: int | None = None):
    """Mirrors ConversationEngine.stream_message's real shape: one try/except
    Exception around the provider token loop, yielding SSE-equivalent tuples,
    emitting a final "done" only on a clean, uninterrupted finish."""
    count = 0
    try:
        async for token in fake_provider_generate_stream(connection):
            yield ("token", token)
            count += 1
            if raise_after is not None and count >= raise_after:
                raise RuntimeError("simulated persistence failure")
    except Exception as exc:
        yield ("error", str(exc))
        return
    yield ("done", None)


@pytest.mark.asyncio
async def test_client_disconnect_closes_upstream_and_never_emits_done() -> None:
    connection = FakeUpstreamConnection()
    gen = stream_response_like(connection)

    received: list[tuple[str, object]] = []
    async for event in gen:
        received.append(event)
        if len(received) == 3:
            break  # simulates the browser aborting: caller just stops reading

    # This is exactly what Starlette's StreamingResponse does internally when
    # it detects the client connection is gone.
    await gen.aclose()

    assert all(kind == "token" for kind, _ in received), "no error/done should appear before the simulated disconnect"
    assert not any(kind == "done" for kind, _ in received), "done must never be emitted for a cancelled stream"
    assert connection.entered is True
    assert await _wait_for(lambda: connection.closed), "GeneratorExit must eventually propagate through `async with` and close the upstream connection"


@pytest.mark.asyncio
async def test_generator_exit_is_not_swallowed_as_a_provider_error() -> None:
    """A cancellation must never be misreported through the same `except
    Exception` path used for genuine provider/persistence failures — that
    would turn a user-initiated Stop into a scary logged 'error' event."""
    connection = FakeUpstreamConnection()
    gen = stream_response_like(connection)

    await gen.__anext__()  # first token
    # aclose() while suspended inside the try/except Exception block.
    await gen.aclose()

    # If GeneratorExit had been caught by `except Exception`, the generator
    # would have yielded an ("error", ...) frame instead of closing cleanly;
    # aclose() completing without raising proves it took the correct path.
    assert await _wait_for(lambda: connection.closed)


@pytest.mark.asyncio
async def test_genuine_exception_during_streaming_still_reported_as_error() -> None:
    """Sanity check: the mechanism above does not accidentally suppress real
    failures — only true cancellation (aclose/GeneratorExit) is silent."""
    connection = FakeUpstreamConnection()
    gen = stream_response_like(connection, raise_after=2)

    received = [event async for event in gen]

    assert received[-1][0] == "error"
    assert "simulated persistence failure" in str(received[-1][1])
    assert not any(kind == "done" for kind, _ in received)
    assert await _wait_for(lambda: connection.closed)


@pytest.mark.asyncio
async def test_uncancelled_stream_completes_and_emits_done_exactly_once() -> None:
    connection = FakeUpstreamConnection()

    async def capped_provider(_connection, token_count=5):
        async with _connection:
            for i in range(token_count):
                yield f"token-{i}"

    async def capped_stream_response(_connection):
        try:
            async for token in capped_provider(_connection):
                yield ("token", token)
        except Exception as exc:
            yield ("error", str(exc))
            return
        yield ("done", None)

    events = [event async for event in capped_stream_response(connection)]
    done_events = [e for e in events if e[0] == "done"]
    assert len(done_events) == 1, "done must be emitted exactly once for a successful, uninterrupted stream"
    assert await _wait_for(lambda: connection.closed)


class BlockedAfterFirstTokenProvider:
    """Mirrors a real provider stalled mid-stream: yields one token normally,
    then the async generator's `__anext__()` never resolves — the exact
    "provider next() is blocked" scenario this test guards against. Uses an
    `async with`-managed resource so cancellation-triggered cleanup (aclose())
    is observable the same way it is for a real httpx connection."""

    def __init__(self) -> None:
        self.closed = False
        self.entered = False
        self.never_resolves = asyncio.Event()

    async def __aenter__(self) -> "BlockedAfterFirstTokenProvider":
        self.entered = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True

    async def stream(self):
        async with self:
            yield "first-token"
            await self.never_resolves.wait()  # never set — simulates a stalled network read
            yield "unreachable-second-token"  # pragma: no cover


@pytest.mark.asyncio
async def test_blocked_provider_anext_is_cancelled_on_disconnect() -> None:
    """The scenario the ASGI live-socket test could not isolate cleanly:
    a provider whose `anext()` is genuinely stuck waiting for the next
    network chunk, not one that is actively yielding. `_consume_cancellable`
    must cancel that in-flight call — not merely stop reading after it
    eventually resolves — and must close the provider's resource."""
    provider = BlockedAfterFirstTokenProvider()
    disconnect_event = asyncio.Event()

    received: list[str] = []
    consumer = _consume_cancellable(provider.stream(), disconnect_event)

    first = await consumer.__anext__()
    received.append(first)
    assert first == "first-token"

    # At this point the underlying anext() call for the SECOND token is
    # blocked forever on `never_resolves.wait()`. Simulate the disconnect
    # watcher firing while that call is in flight.
    disconnect_event.set()

    with pytest.raises(_ClientDisconnected):
        await consumer.__anext__()

    assert received == ["first-token"], "no further tokens should be yielded after disconnect"
    assert await _wait_for(lambda: provider.closed), (
        "the blocked provider's async-with resource must be closed even though its "
        "anext() call was never going to resolve on its own"
    )


@pytest.mark.asyncio
async def test_consume_cancellable_passes_through_all_tokens_when_no_disconnect() -> None:
    """Sanity check: the cancellation machinery is invisible to a normal,
    uninterrupted stream."""

    async def normal_provider():
        for i in range(5):
            yield f"token-{i}"

    disconnect_event = asyncio.Event()
    tokens = [t async for t in _consume_cancellable(normal_provider(), disconnect_event)]
    assert tokens == [f"token-{i}" for i in range(5)]
