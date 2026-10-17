"""Event bus and sinks. Every stage reports through here as it happens."""

from __future__ import annotations

import json
import sys
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Protocol

from rich.console import Console
from rich.markup import escape

from pah.core.models import Event, EventKind


class Sink(Protocol):
    def handle(self, event: Event) -> None: ...

    def close(self) -> None: ...


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class EventBus:
    """Fan-out of events to sinks. Thread safe; sequence numbers are strictly increasing."""

    def __init__(self, run_id: str, sinks: list[Sink] | None = None, seq_start: int = 0) -> None:
        self.run_id = run_id
        self._sinks: list[Sink] = list(sinks or [])
        self._seq = seq_start
        self._lock = threading.Lock()

    def add_sink(self, sink: Sink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def emit(self, kind: EventKind, stage: str, message: str, **data: Any) -> Event:
        with self._lock:
            self._seq += 1
            event = Event(
                run_id=self.run_id,
                seq=self._seq,
                kind=kind,
                stage=stage,
                message=message,
                data=data,
            )
            for sink in self._sinks:
                sink.handle(event)
        return event

    def close(self) -> None:
        with self._lock:
            for sink in self._sinks:
                sink.close()

    def __enter__(self) -> EventBus:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


_STATUS_STYLE = {
    "pass": "green",
    "ok": "green",
    "warn": "yellow",
    "stop": "red",
    "skip": "dim",
    "blocked": "red",
    "unreachable": "red",
    "http_error": "yellow",
    "missing": "yellow",
    "error": "red",
}


class ConsoleSink:
    """Human-readable line per event."""

    def __init__(self, console: Console | None = None, show_logs: bool = True) -> None:
        self._console = console or Console(stderr=False, highlight=False)
        self._show_logs = show_logs

    def handle(self, event: Event) -> None:
        if event.kind is EventKind.LOG and not self._show_logs:
            return
        status = str(event.data.get("status", event.data.get("gate", ""))).lower()
        style = _STATUS_STYLE.get(status, "cyan")
        tag = f"[{style}]{status.upper():<11}[/{style}]" if status else " " * 11
        clock = event.ts.strftime("%H:%M:%S")
        self._console.print(
            f"[dim]{clock} #{event.seq:<4}[/dim] {event.kind.value:<11} {tag} "
            f"[bold]{escape(event.stage)}[/bold]  {escape(event.message)}",
            soft_wrap=True,
        )

    def close(self) -> None:
        return None


class JsonlSink:
    """Appends one JSON object per event and flushes immediately."""

    def __init__(self, target: Path | IO[str]) -> None:
        if isinstance(target, Path):
            target.parent.mkdir(parents=True, exist_ok=True)
            self._fh: IO[str] = target.open("a", encoding="utf-8")
            self._owns = True
        else:
            self._fh = target
            self._owns = False

    def handle(self, event: Event) -> None:
        self._fh.write(event.model_dump_json() + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._owns:
            self._fh.close()


class StdoutJsonlSink(JsonlSink):
    """Machine-readable stream for agents and pipes."""

    def __init__(self) -> None:
        super().__init__(sys.stdout)


class CallbackSink:
    """Forwards events to a callable, used by MCP progress and SSE streams."""

    def __init__(self, callback: Callable[[Event], None]) -> None:
        self._callback = callback

    def handle(self, event: Event) -> None:
        self._callback(event)

    def close(self) -> None:
        return None


class MemorySink:
    """Keeps events in memory, for tests and API replay."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def handle(self, event: Event) -> None:
        self.events.append(event)

    def close(self) -> None:
        return None

    def as_json(self) -> str:
        return json.dumps([e.model_dump(mode="json") for e in self.events])
