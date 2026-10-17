"""Persistence hook for deployments whose run storage needs an explicit flush.

On Modal the runs and cache directories are Volumes, and writes become visible to other
containers only after `volume.commit()`. The Modal app registers that call with `on_persist`;
the service calls `persist()` after every write it makes (job state, run end, agent-log steps,
uploads). With no callback registered `persist()` does nothing. A callback that raises is logged
and the remaining callbacks still run; the write that triggered it is never failed.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

PersistCallback = Callable[[], object]

_callbacks: list[PersistCallback] = []
_lock = threading.Lock()


def on_persist(callback: PersistCallback) -> Callable[[], None]:
    """Registers a callback. Returns a function that removes it again."""
    with _lock:
        _callbacks.append(callback)

    def remove() -> None:
        with _lock:
            if callback in _callbacks:
                _callbacks.remove(callback)

    return remove


def persist(reason: str = "") -> None:
    """Runs every registered callback in registration order. Never raises."""
    with _lock:
        callbacks = list(_callbacks)
    for cb in callbacks:
        try:
            cb()
        except Exception:  # a failed commit is logged, never fatal to the write
            log.exception("persist callback %r failed (%s)", cb, reason or "no reason given")


def clear() -> None:
    """Removes every callback (used by tests)."""
    with _lock:
        _callbacks.clear()
