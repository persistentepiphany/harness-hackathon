"""Build demo video A from one recorded take.

Reads work/<v>/raw.webm and work/<v>/events.json (written by record.sh), then:
  1. aligns page time to video time (title-card removal frame),
  2. writes the subtitles (SRT for delivery, ASS for burning in),
  3. places the synthesized SFX on the recorded events and mixes them over the bed,
  4. encodes MP4 (H.264 + AAC) and WebM (VP9 + Opus) with a 100 px caption band,
  5. writes contact sheets and a loudness report.

Usage: .venv/bin/python build.py <version>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

A = Path("/home/user/harness-hackathon/out/videos/a")
W = A / "work"
SFX = A / "sfx"
SR = 48_000
VW, VH, BAND = 1440, 800, 100
FPS = 30

# Loudness targets (no voice in this video): bed about -30 LUFS, SFX about -22 LUFS momentary.
# Clicks and ticks are 50-70 ms transients, so their 400 ms momentary value reads low; they sit a
# little under the others to stay light.
TARGET = {"click": -25.0, "tick": -27.0, "stop": -22.0, "chime": -22.0, "whoosh": -24.0}
BED_LUFS = -30.0
MIN_HOLD, PER_WORD = 1.5, 0.3


def run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)  # type: ignore[call-overload]


def duration(path: Path) -> float:
    out = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    ).stdout
    return float(out.strip())


def hold(text: str) -> float:
    return max(MIN_HOLD, len(text.split()) * PER_WORD)


# ------------------------------------------------------------------ alignment


def gray_frames(path: Path, start: float, length: float, w: int = 160, h: int = 89) -> np.ndarray:
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{start}",
            "-t",
            f"{length}",
            "-i",
            str(path),
            "-vf",
            f"fps={FPS},scale={w}:{h},format=gray",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w).astype(np.float32)


def calibrate(raw: Path, title_off_s: float) -> float:
    """Offset to add to (page time - pageT0) to get video time, from the title-card removal."""
    start = max(0.0, title_off_s - 1.5)
    frames = gray_frames(raw, start, 3.5)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    k = int(np.argmax(diffs))
    v_off = start + (k + 1) / FPS
    delta = v_off - title_off_s - 0.03
    if not -0.5 <= delta <= 1.5 or diffs[k] < 3:
        print(f"calibration unsure (delta {delta:.3f}, diff {diffs[k]:.1f}); using 0")
        return 0.0
    return float(delta)


# ------------------------------------------------------------------ subtitles

STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
)


def fmt_srt(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def fmt_ass(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 360000:d}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def caption_spans(
    caps: list[tuple[float, str]], end_limit: float
) -> list[tuple[float, float, str]]:
    spans = []
    for i, (t, text) in enumerate(caps):
        h = hold(text)
        nxt = caps[i + 1][0] if i + 1 < len(caps) else end_limit
        end = min(nxt - 0.12, t + h + 2.0)
        end = max(end, t + h)
        spans.append((t, end, text))
    return spans


def text_width(text: str, size: int) -> float:
    from PIL import ImageFont

    font = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", size)
    return float(font.getlength(text))


def write_subs(spans: list[tuple[float, float, str]], srt: Path, ass: Path) -> list[str]:
    warnings = []
    with srt.open("w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(spans, 1):
            f.write(f"{i}\n{fmt_srt(a)} --> {fmt_srt(b)}\n{text}\n\n")
    size = 29
    style = (
        f"Style: Cap,Inter Medium,{size},&H00FFFFFF,&H00FFFFFF,&H24181A1A,&H00000000,"
        f"0,0,0,0,100,100,0.2,0,3,13,0,2,40,40,{(BAND - size) // 2 + 1},1"
    )
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VW}
PlayResY: {VH + BAND}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
{STYLE_FORMAT}
{style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with ass.open("w", encoding="utf-8") as f:
        f.write(head)
        for a, b, text in spans:
            wpx = text_width(text, size)
            if wpx > VW - 2 * 60:
                warnings.append(f"caption too wide ({wpx:.0f}px): {text}")
            f.write(f"Dialogue: 0,{fmt_ass(a)},{fmt_ass(b)},Cap,,0,0,0,,{{\\fad(120,120)}}{text}\n")
    return warnings


# ------------------------------------------------------------------ audio


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def write_wav(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def ebur128(path: Path, pad: float = 0.0) -> dict[str, float]:
    af = (f"apad=pad_dur={pad}," if pad else "") + "ebur128=peak=true:framelog=info"
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", af, "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stderr
    ms = [float(m) for m in re.findall(r"\bM:\s*(-?[\d.]+|-inf)", err) if m != "-inf"]
    summary = err[err.rfind("Summary:") :]
    i = re.search(r"I:\s*(-?[\d.]+|-inf) LUFS", summary)
    lra = re.search(r"LRA:\s*(-?[\d.]+) LU", summary)
    tp = re.search(r"Peak:\s*(-?[\d.]+|-inf) dBFS", summary)
    return {
        "M_max": max(ms) if ms else float("-inf"),
        "I": float(i.group(1)) if i and i.group(1) != "-inf" else float("-inf"),
        "LRA": float(lra.group(1)) if lra else float("nan"),
        "TP": float(tp.group(1)) if tp and tp.group(1) != "-inf" else float("-inf"),
    }


def place(track: np.ndarray, clip: np.ndarray, t: float, gain: float) -> None:
    i = round(t * SR)
    if i < 0 or i >= len(track):
        return
    n = min(len(clip), len(track) - i)
    track[i : i + n] += clip[:n] * gain


def sfx_events(ev: list, to_v, my_id: str, other_name: str) -> list[tuple[float, str, float]]:
    """(video time, sound, extra gain dB) for every event that gets a sound."""
    out: list[tuple[float, str, float]] = []
    route = "/runs/new"
    last_tick = -1.0
    for t_page, kind, data in ev:
        t = to_v(t_page)
        if kind == "route":
            route = data["path"]
            out.append((t - 0.06, "whoosh", 0.0))
        elif kind == "pointerdown":
            out.append((t, "click", 0.0))
        elif kind == "log" and data["job"] == my_id and route in ("/jobs", f"/jobs/{my_id}"):
            if data["kind"] == "check":
                if data.get("result") == "stop":
                    out.append((t, "stop", 0.0))
                elif t - last_tick >= 0.13:
                    out.append((t, "tick", 0.0))
                    last_tick = t
        elif kind == "status" and data["status"] == "done":
            if data["job"] == my_id and route == f"/jobs/{my_id}":
                out.append((t + 0.05, "chime", 0.0))
            elif (
                data["name"] == other_name and route == "/jobs" and data.get("verdict") == "refused"
            ):
                out.append((t + 0.05, "stop", 0.0))
        elif kind == "agentstep" and data["task"] == "agent_01" and route == "/agent":
            out.append((t, "tick", -3.0))
    # ticks give way to the stop tone and the chime, so the louder cue stays clean
    cues = [t for t, name, _ in out if name in ("stop", "chime")]
    return [e for e in out if e[1] != "tick" or all(abs(e[0] - c) > 0.6 for c in cues)]


def mix(
    total: float, events: list[tuple[float, str, float]], out: Path
) -> dict[str, dict[str, float]]:
    n = int(total * SR)
    sfx_track = np.zeros((n, 2), dtype=np.float32)
    levels = {}
    clips = {}
    for name, target in TARGET.items():
        clip = read_wav(SFX / f"{name}.wav")
        m = ebur128(SFX / f"{name}.wav", pad=1.0)["M_max"]
        clips[name] = (clip, 10 ** ((target - m) / 20))
        levels[name] = {"M_max_raw": m, "target": target}
    for t, name, extra in events:
        clip, g = clips[name]
        place(sfx_track, clip, t, g * 10 ** (extra / 20))
    bed = read_wav(SFX / "pad.wav")
    if len(bed) < n:
        bed = np.concatenate([bed, np.zeros((n - len(bed), 2), dtype=np.float32)])
    bed = bed[:n].copy()
    fo = int(3.0 * SR)
    bed[-fo:] *= np.cos(np.linspace(0, np.pi / 2, fo))[:, None] ** 2
    tmp = out.with_name("bed-tmp.wav")
    write_wav(tmp, bed)
    bi = ebur128(tmp)["I"]
    bed *= 10 ** ((BED_LUFS - bi) / 20)
    write_wav(tmp, bed)
    write_wav(out.with_name("sfx-only.wav"), sfx_track)
    total_mix = bed + sfx_track
    peak = float(np.max(np.abs(total_mix)))
    if peak > 0.89:
        total_mix *= 0.89 / peak
    write_wav(out, total_mix)
    levels["bed"] = ebur128(tmp)
    levels["sfx_only"] = ebur128(out.with_name("sfx-only.wav"))
    levels["mix"] = ebur128(out)
    tmp.unlink()
    return levels


# ------------------------------------------------------------------ video


def encode(
    raw: Path,
    ass: Path,
    mix_wav: Path,
    mp4: Path,
    webm: Path,
    fast: bool = False,
    cuts: list[tuple[float, float]] | None = None,
) -> None:
    keep = ""
    if cuts:
        expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cuts)
        keep = f"select='not({expr})',setpts=N/{FPS}/TB,"
    vf = (
        f"fps={FPS},{keep}pad={VW}:{VH + BAND}:0:0:color=0xf7f7f4,"
        f"drawbox=x=0:y={VH}:w={VW}:h=1:color=0xe6e6e1:t=fill,"
        f"ass={ass}"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(raw),
            "-i",
            str(mix_wav),
            "-filter_complex",
            f"[0:v]{vf}[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if fast else "medium",
            "-crf",
            "18",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-shortest",
            "-movflags",
            "+faststart",
            str(mp4),
        ]
    )
    if fast:
        return
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(mp4),
            "-map",
            "0:v",
            "-map",
            "0:a",
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "33",
            "-b:v",
            "0",
            "-deadline",
            "good",
            "-cpu-used",
            "4",
            "-row-mt",
            "1",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
            str(webm),
        ]
    )


def sheets(mp4: Path, d: Path, total: float) -> list[Path]:
    paths = []
    per = 24
    for k in range(int(np.ceil(total / per))):
        p = d / f"sheet-{k + 1}.png"
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                str(k * per),
                "-t",
                str(per),
                "-i",
                str(mp4),
                "-vf",
                "fps=1,scale=480:-1,tile=6x4",
                "-frames:v",
                "1",
                str(p),
            ]
        )
        paths.append(p)
    return paths


def main() -> None:
    v = sys.argv[1]
    fast = "--fast" in sys.argv
    d = W / v
    raw = d / "raw.webm"
    data = json.loads((d / "events.json").read_text())
    t0 = data["pageT0"]
    notes = {k: t for t, k, _ in data["notes"]}
    raw_total = duration(raw)
    delta = calibrate(raw, (notes["title-off"] - t0) / 1000)

    # waits cut from the video, in raw video time: Mol* loading (marked by the take) and page
    # changes where the old page sat frozen for more than 1.2 s after the click
    cuts = [
        ((a - t0) / 1000 + delta, (b - t0) / 1000 + delta)
        for a, b in data.get("cuts") or []
        if b > a
    ]
    last_click = None
    clicks_and_routes = list(data["ev"] or []) + [
        [tt, "pointerdown", None] for tt, k, _ in data["notes"] if k == "click"
    ]
    for t_ev, kind, _ in sorted(clicks_and_routes, key=lambda e: e[0]):
        if kind == "pointerdown":
            last_click = t_ev
        elif kind == "route" and last_click is not None:
            gap = (t_ev - last_click) / 1000
            if 1.2 < gap < 20:
                a = (last_click - t0) / 1000 + delta + 0.4
                cuts.append((a, (t_ev - t0) / 1000 + delta - 0.15))
            last_click = None
    cuts.sort()

    def remap(t: float) -> float:
        out = t
        for a, b in cuts:
            if t >= b:
                out -= b - a
            elif t > a:
                out -= t - a
        return out

    def to_v(t_page: float) -> float:
        return remap((t_page - t0) / 1000 + delta)

    total = remap(raw_total)
    caps = [(to_v(t), text) for t, text in data["caps"]]
    end_on = to_v(notes["end-on"]) if "end-on" in notes else total - 4.5
    spans = caption_spans(caps, end_on)
    warns = write_subs(spans, d / "demo-a.srt", d / "captions.ass")
    ev = list(data["ev"] or [])
    # clicks made through the DOM (busy Mol* pages) have no pointerdown; their note stands in
    ev += [[t, "pointerdown", {"note": v}] for t, k, v in data["notes"] if k == "click"]
    ev.sort(key=lambda e: e[0])
    events = sfx_events(ev, to_v, data["myId"], "KRAS · RAF1 discovery")
    levels = mix(total, events, d / "mix.wav")
    encode(raw, d / "captions.ass", d / "mix.wav", d / "demo-a.mp4", d / "demo-a.webm", fast, cuts)
    final = duration(d / "demo-a.mp4")
    sh = sheets(d / "demo-a.mp4", d, final)
    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,pix_fmt,sample_rate,channels",
            "-show_entries",
            "format=duration",
            "-of",
            "compact",
            str(d / "demo-a.mp4"),
        ]
    ).stdout
    counts: dict[str, int] = {}
    for _, name, _ in events:
        counts[name] = counts.get(name, 0) + 1
    report = {
        "version": v,
        "raw_s": raw_total,
        "final_s": final,
        "cuts_s": [[round(a, 2), round(b, 2)] for a, b in cuts],
        "delta_s": delta,
        "captions": len(spans),
        "sfx_counts": counts,
        "levels": levels,
        "warnings": warns,
        "probe": probe.strip().splitlines(),
        "sheets": [str(p) for p in sh],
        "scenes": {k: round(to_v(t), 2) for k, t in notes.items()},
    }
    (d / "build.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
