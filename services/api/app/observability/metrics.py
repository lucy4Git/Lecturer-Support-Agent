from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Iterable


class MetricsRegistry:
    """Small dependency-free Prometheus text registry for operational metrics."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    @staticmethod
    def _key(name: str, labels: dict[str, str] | None) -> tuple[str, tuple[tuple[str, str], ...]]:
        return name, tuple(sorted((labels or {}).items()))

    def increment(self, name: str, value: float = 1, *, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += value

    def set_gauge(self, name: str, value: float, *, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    @staticmethod
    def _render_labels(labels: Iterable[tuple[str, str]]) -> str:
        items = list(labels)
        if not items:
            return ""
        escaped = [f'{key}="{value.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"' for key, value in items]
        return "{" + ",".join(escaped) + "}"

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"{name}{self._render_labels(labels)} {value}")
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"{name}{self._render_labels(labels)} {value}")
        return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()
