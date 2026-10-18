"""Read access to run directories: listing, event streams, records and safe file paths."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path, PurePosixPath
from typing import Any

log = logging.getLogger(__name__)

RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
EVENTS = "events.jsonl"
# Directories in runs_dir that are not task runs: agent monitor data, uploads, batches, and the
# reports of `pah doctor` and `pah fetch`, which share the events format but carry no task.
SKIP_PREFIXES = ("agent-", "batch-", "doctor-", "fetch-")
SKIP_NAMES = frozenset({"uploads"})
TEXT = "text/plain; charset=utf-8"
MEDIA_TYPES = {
    ".cif": TEXT, ".mmcif": TEXT, ".pdb": TEXT, ".ent": TEXT, ".sdf": TEXT, ".mol": TEXT,
    ".mol2": TEXT, ".pdbqt": TEXT, ".a3m": TEXT, ".fasta": TEXT, ".fa": TEXT, ".mmd": TEXT,
    ".jsonl": TEXT, ".log": TEXT, ".txt": TEXT, ".csv": "text/csv; charset=utf-8",
    ".tsv": "text/tab-separated-values; charset=utf-8", ".md": "text/markdown; charset=utf-8",
    ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml",
    ".pse": "application/octet-stream", ".bcif": "application/octet-stream",
    ".html": "text/html; charset=utf-8", ".gz": "application/gzip",
}  # fmt: skip
# Types a browser could execute script from; served with a sandboxing CSP.
ACTIVE_TYPES = frozenset({".svg", ".html"})


class RunNotFoundError(LookupError):
    """No run directory with this id."""


class UnsafePathError(ValueError):
    """An id or path that could leave the runs directory."""


def media_type(path: Path) -> str:
    """Media type for a run file. Structure and alignment files are served as UTF-8 text so a
    browser (and Mol* `fetch`) reads them as text; unknown types are octet-stream."""
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def file_headers(path: Path) -> dict[str, str]:
    headers = {"X-Content-Type-Options": "nosniff"}
    if path.suffix.lower() in ACTIVE_TYPES:
        headers["Content-Security-Policy"] = "sandbox"
    return headers


def valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID.fullmatch(run_id)) and run_id not in {".", ".."}


def parse_line(raw: bytes | str) -> dict[str, Any] | None:
    """One JSON object per line; anything else is ignored."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def read_events(path: Path) -> list[dict[str, Any]]:
    """Every complete event line in an events file. A partial last line is left out."""
    try:
        data = path.read_bytes()
    except OSError:
        return []
    complete, _, _ = data.rpartition(b"\n")
    out: list[dict[str, Any]] = []
    for raw in complete.split(b"\n"):
        obj = parse_line(raw)
        if obj is not None:
            out.append(obj)
    return out


def read_json(path: Path) -> Any:
    """Parsed JSON, or None when the file is missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def first_event(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as fh:
            return parse_line(fh.readline())
    except OSError:
        return None


async def tail_jsonl(
    path: Path,
    *,
    poll: float = 0.25,
    wait_for_file: float = 10.0,
    end_grace: float = 3.0,
    stale_after: float | None = 600.0,
    stop: Callable[[], Awaitable[bool]] | None = None,
    job_status: Callable[[], str | None] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yields every event in `path` from the start, then new ones as they are appended.

    Waits up to `wait_for_file` seconds for the file to appear. After a `run_end` event it keeps
    reading while a stage opened after it (the report stage: renders, figures, graph) is still
    open, then until the file has been quiet for `end_grace` seconds, so the artifact events
    written after the verdict are included. It also stops once the file has not changed for
    `stale_after` seconds. `stop` is awaited between polls (for example a client disconnect).
    `job_status` reads the job's status (job.json): a failed or done job ends the tail once the
    file is quiet, and a queued job never goes stale while it waits for a slot.
    """
    waited = 0.0
    while not path.is_file():
        if waited >= wait_for_file or (stop is not None and await stop()):
            return
        await asyncio.sleep(poll)
        waited += poll
    pos = 0
    buf = b""
    ended = False
    open_stages: set[str] = set()
    last_data = time.monotonic()
    status: str | None = None
    status_at = -1.0e9
    while True:
        try:
            size = path.stat().st_size
            if size < pos:  # replaced or truncated: start again
                pos, buf = 0, b""
            with path.open("rb") as fh:
                fh.seek(pos)
                chunk = fh.read()
            mtime = path.stat().st_mtime
        except OSError:
            chunk, mtime = b"", time.time()
        if chunk:
            pos += len(chunk)
            last_data = time.monotonic()
            *lines, buf = (buf + chunk).split(b"\n")
            for raw in lines:
                obj = parse_line(raw)
                if obj is None:
                    continue
                kind, stage = obj.get("kind"), str(obj.get("stage", ""))
                if kind == "run_end":
                    ended = True
                elif kind == "stage_start" and ended:
                    open_stages.add(stage)
                elif kind == "stage_end":
                    open_stages.discard(stage)
                yield obj
        quiet = time.time() - mtime
        settled = quiet >= end_grace or time.monotonic() - last_data >= end_grace
        if ended and not open_stages and settled:
            return
        if job_status is not None and time.monotonic() - status_at >= 1.0:
            status, status_at = job_status(), time.monotonic()
        if status in {"failed", "done"} and settled and not (ended and open_stages):
            return
        if stale_after is not None and quiet >= stale_after and status != "queued":
            return
        if stop is not None and await stop():
            return
        await asyncio.sleep(poll)


class RunStore:
    """Run directories under one `runs_dir`. Ids are directory names."""

    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    def _root(self) -> Path:
        return self.runs_dir.resolve()

    def path_for(self, run_id: str) -> Path:
        """Directory a run with this id has or would have. Does not require it to exist."""
        if not valid_run_id(run_id):
            raise UnsafePathError(f"invalid run id {run_id!r}")
        return self.runs_dir / run_id

    def run_dir(self, run_id: str) -> Path:
        """Existing run directory, resolved inside runs_dir. Directories that are not runs
        (uploads, agent logs, doctor and batch directories) are not found."""
        path = self.path_for(run_id)
        if run_id in SKIP_NAMES or run_id.startswith(SKIP_PREFIXES) or not path.is_dir():
            raise RunNotFoundError(run_id)
        if path.resolve().parent != self._root():
            raise UnsafePathError(f"run {run_id!r} resolves outside {self.runs_dir}")
        return path

    def events_path(self, run_id: str) -> Path:
        return self.path_for(run_id) / EVENTS

    def is_run(self, path: Path) -> bool:
        name = path.name
        if name in SKIP_NAMES or name.startswith(SKIP_PREFIXES) or not valid_run_id(name):
            return False
        if (path / "batch_report.json").is_file():
            return False
        return path.is_dir() and (path / EVENTS).is_file()

    def list_runs(self) -> list[Path]:
        """Run directories with an events file, newest first (first event time, else mtime)."""
        try:
            entries = [p for p in self.runs_dir.iterdir() if self.is_run(p)]
        except OSError:
            return []

        def created(p: Path) -> str:
            first = first_event(p / EVENTS)
            ts = first.get("ts") if first else None
            if isinstance(ts, str):
                return ts
            try:
                stamp = (p / EVENTS).stat().st_mtime
            except OSError:
                return ""
            return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(stamp))

        return sorted(entries, key=created, reverse=True)

    def events(self, run_id: str) -> list[dict[str, Any]]:
        return read_events(self.run_dir(run_id) / EVENTS)

    def record(self, run_id: str) -> dict[str, Any] | None:
        data = read_json(self.run_dir(run_id) / "record.json")
        return data if isinstance(data, dict) else None

    def provenance(self, run_id: str) -> list[dict[str, Any]] | None:
        data = read_json(self.run_dir(run_id) / "provenance.json")
        return [p for p in data if isinstance(p, dict)] if isinstance(data, list) else None

    def findings(self, run_id: str) -> list[dict[str, Any]]:
        """Findings written to `findings/` so far, ordered by layer then file name."""
        folder = self.run_dir(run_id) / "findings"
        out: list[dict[str, Any]] = []
        for path in sorted(folder.glob("L*_*.json")) if folder.is_dir() else ():
            data = read_json(path)
            if isinstance(data, dict):
                out.append(data)
        return out

    def resolve_file(self, run_id: str, relative: str) -> Path:
        """A regular file inside the run directory.

        Rejects absolute paths, `..` segments, backslashes, NUL bytes and any path whose real
        location (after following symlinks) is outside the run directory.
        """
        if not relative or "\x00" in relative or "\\" in relative:
            raise UnsafePathError(f"invalid path {relative!r}")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or any(part in {"..", ""} for part in relative.split("/")):
            raise UnsafePathError(f"invalid path {relative!r}")
        base = self.run_dir(run_id).resolve()
        target = (base / pure).resolve()
        if not target.is_relative_to(base) or target == base:
            raise UnsafePathError(f"path {relative!r} leaves run {run_id!r}")
        if not target.is_file():
            raise FileNotFoundError(relative)
        return target

    def tail(
        self,
        run_id: str,
        *,
        poll: float = 0.25,
        wait_for_file: float = 10.0,
        end_grace: float = 3.0,
        stale_after: float | None = 600.0,
        stop: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Replays then tails `events.jsonl` of a run that may not exist yet; job.json's status
        ends it for a failed job and keeps a queued one from going stale."""
        return tail_jsonl(
            self.events_path(run_id),
            poll=poll,
            wait_for_file=wait_for_file,
            end_grace=end_grace,
            stale_after=stale_after,
            stop=stop,
            job_status=lambda: self.job_status(run_id),
        )

    def job_status(self, run_id: str) -> str | None:
        """`status` of runs/<id>/job.json (UI runs), or None."""
        data = read_json(self.path_for(run_id) / "job.json")
        status = data.get("status") if isinstance(data, dict) else None
        return str(status) if isinstance(status, str) else None
