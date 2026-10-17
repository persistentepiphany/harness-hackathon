import io
import json
from pathlib import Path

from rich.console import Console

from pah.core.events import CallbackSink, ConsoleSink, EventBus, JsonlSink, MemorySink, new_run_id
from pah.core.models import EventKind, Finding, Gate, Layer, Measurement, Threshold


def test_sequence_and_fanout() -> None:
    mem = MemorySink()
    seen: list[int] = []
    bus = EventBus("r1", [mem, CallbackSink(lambda e: seen.append(e.seq))])
    bus.emit(EventKind.RUN_START, "run", "start")
    bus.emit(EventKind.FINDING, "L1", "x", gate="pass")
    assert [e.seq for e in mem.events] == [1, 2]
    assert seen == [1, 2]
    assert mem.events[1].data == {"gate": "pass"}


def test_jsonl_sink_flushes_each_event(tmp_path: Path) -> None:
    path = tmp_path / "runs" / "events.jsonl"
    bus = EventBus("r2", [JsonlSink(path)])
    bus.emit(EventKind.LOG, "s", "one")
    assert len(path.read_text().splitlines()) == 1
    bus.emit(EventKind.LOG, "s", "two")
    bus.close()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["message"] for r in rows] == ["one", "two"]


def test_console_sink_renders_status() -> None:
    buf = io.StringIO()
    sink = ConsoleSink(Console(file=buf, width=200, color_system=None))
    with EventBus("r3", [sink]) as bus:
        bus.emit(EventKind.RESULT, "doctor", "uniprot", status="ok")
    out = buf.getvalue()
    assert "OK" in out and "uniprot" in out and "doctor" in out


def test_finding_roundtrip() -> None:
    f = Finding(
        check_id="l4.posebusters",
        layer=Layer.VALIDITY,
        gate=Gate.STOP,
        message="bond_lengths failed",
        measurements=(Measurement(name="bond_lengths", value=False),),
        thresholds=(Threshold(name="clash", value=0.75, comparator="<", origin="PoseBusters"),),
    )
    assert Finding.model_validate_json(f.model_dump_json()) == f


def test_run_id_prefix() -> None:
    assert new_run_id("doctor").startswith("doctor-")


def test_console_sink_does_not_eat_brackets() -> None:
    buf = io.StringIO()
    sink = ConsoleSink(Console(file=buf, width=200, color_system=None))
    EventBus("r4", [sink]).emit(EventKind.FINDING, "L1", "msg [n=3, x=1]", gate="pass")
    assert "[n=3, x=1]" in buf.getvalue()
