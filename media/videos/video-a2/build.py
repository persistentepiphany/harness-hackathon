"""Build demo video A2 from one recorded take (video A pipeline, A2 paths and cues).

Reads work/<v>/raw.webm and work/<v>/events.json (written by record.sh), then:
  1. aligns page time to video time (title-card removal frame),
  2. writes the subtitles (SRT for delivery, ASS for burning in),
  3. places the synthesized SFX on the recorded events and mixes them over the bed,
  4. encodes MP4 (H.264 + AAC) with a 100 px caption band (WebM with --webm),
  5. writes contact sheets and a loudness report.

Usage: .venv/bin/python build.py <version> [--fast] [--webm]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

A = Path("/home/user/harness-hackathon/out/videos/a2")
W = A / "work"
SFX = A / "sfx"
SR = 48_000
VW, VH, BAND = 1440, 800, 100
FPS = 30

# Loudness targets (A2: no voice, no bed, UI sounds only, kept quiet and dry). Momentary maximum
# per sound; a click is a 70 ms transient, so its 400 ms momentary value reads low. Typing is
# levelled as a run of keys (KEY_BURST_LUFS) and sits under the clicks.
TARGET = {"click": -27.0, "chime": -27.0, "whoosh": -28.0}
KEY_VARIANTS = 6
KEY_BURST_LUFS = -31.0
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


def sfx_events(
    ev: list, to_v, my_id: str, keys_v: list[float], scenes_v: list[float]
) -> list[tuple[float, str, float]]:
    """(video time, sound, extra gain dB) for every event that gets a sound.

    A2 uses UI sounds only: a click on every pointer press, one key sound per typed character, a
    whoosh on every page or scene change (at most one per 0.6 s) and a soft chime when the
    followed run's verdict arrives on its page. No bed, no check-result ticks, no stop tone.
    """
    out: list[tuple[float, str, float]] = []
    route = "/runs/new"
    whooshes = [t - 0.06 for t in scenes_v]
    for t_page, kind, data in ev:
        t = to_v(t_page)
        if kind == "route":
            route = data["path"]
            whooshes.append(t - 0.06)
        elif kind == "pointerdown":
            out.append((t, "click", 0.0))
        elif kind == "status" and data["status"] == "done":
            if data["job"] == my_id and route == f"/jobs/{my_id}":
                out.append((t + 0.05, "chime", 0.0))
    last = -9.0
    for t in sorted(whooshes):
        if t - last >= 0.6:
            out.append((t, "whoosh", 0.0))
            last = t
    rng = np.random.default_rng(7)
    prev = -1
    for t in keys_v:
        k = int(rng.integers(0, KEY_VARIANTS - 1))
        k = k + 1 if k >= prev else k  # never the same variant twice in a row
        prev = k
        out.append((max(0.0, t), f"key{k}", float(rng.uniform(-1.5, 1.5))))
    return sorted(out)


def mix(
    total: float, events: list[tuple[float, str, float]], out: Path
) -> dict[str, dict[str, float]]:
    n = int(total * SR)
    sfx_track = np.zeros((n, 2), dtype=np.float32)
    levels: dict[str, dict[str, float]] = {}
    clips = {}
    for name, target in TARGET.items():
        clip = read_wav(SFX / f"{name}.wav")
        m = ebur128(SFX / f"{name}.wav", pad=1.0)["M_max"]
        clips[name] = (clip, 10 ** ((target - m) / 20))
        levels[name] = {"M_max_raw": m, "target": target}
    # keys are levelled as typing: a run of keys 40 ms apart, measured as one momentary value
    keys = [read_wav(SFX / f"key{k}.wav") for k in range(KEY_VARIANTS)]
    burst = np.zeros((int(3.0 * SR), 2), dtype=np.float32)
    for i in range(30):
        place(burst, keys[i % KEY_VARIANTS], 0.5 + i * 0.04, 1.0)
    tmp = out.with_name("keys-burst.wav")
    write_wav(tmp, burst)
    m = ebur128(tmp)["M_max"]
    tmp.unlink()
    g_key = 10 ** ((KEY_BURST_LUFS - m) / 20)
    for k in range(KEY_VARIANTS):
        clips[f"key{k}"] = (keys[k], g_key)
    levels["key"] = {"M_max_raw_burst": m, "target_burst": KEY_BURST_LUFS}
    for t, name, extra in events:
        clip, g = clips[name]
        place(sfx_track, clip, t, g * 10 ** (extra / 20))
    peak = float(np.max(np.abs(sfx_track)))
    if peak > 0.89:
        sfx_track *= 0.89 / peak
    write_wav(out, sfx_track)
    levels["mix"] = ebur128(out)
    return levels


def typing_start(raw: Path, until_s: float) -> float:
    """Raw video time of the first frame with ink on the title line (the first typed character).

    The caret is accent-coloured and lighter than the ink threshold, so it does not count.
    """
    w, h = 720, 400
    frames = gray_frames(raw, 0.0, until_s, w, h)
    band = frames[:, 185:222, :]  # the title line only (y 370-444 at full size)
    ink = (band < 90).sum(axis=(1, 2))
    hits = np.nonzero(ink > 20)[0]
    if not len(hits):
        print("typing start not found; no start cut")
        return 0.0
    return float(hits[0] / FPS)


# ------------------------------------------------------------------ video


def encode(
    raw: Path,
    ass: Path,
    mix_wav: Path,
    mp4: Path,
    webm: Path,
    fast: bool = False,
    cuts: list[tuple[float, float]] | None = None,
    make_webm: bool = False,
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
    if fast or not make_webm:
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
    make_webm = "--webm" in sys.argv
    d = W / v
    raw = d / "raw.webm"
    data = json.loads((d / "events.json").read_text())
    t0 = data["pageT0"]
    notes = {k: t for t, k, _ in data["notes"]}
    raw_total = duration(raw)
    delta = calibrate(raw, (notes["title-off"] - t0) / 1000)
    # A2: the video starts on the first typed character of the title
    t_type = typing_start(raw, min(3.0, (notes["title-off"] - t0) / 1000))

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
    if t_type > 0.02:
        cuts.append((0.0, t_type - 0.5 / FPS))
    # A2: frames showing a page-level loading placeholder (recorded in the page as 'loading' on/off)
    on_at = None
    for t_ev, kind, data_ev in data["ev"] or []:
        if kind != "loading":
            continue
        if data_ev["on"] and on_at is None:
            on_at = t_ev
        elif not data_ev["on"] and on_at is not None:
            if t_ev - on_at < 1500:
                cuts.append(((on_at - t0) / 1000 + delta - 0.02, (t_ev - t0) / 1000 + delta + 0.07))
            on_at = None
    cuts.sort()
    merged: list[tuple[float, float]] = []
    for a_c, b_c in cuts:
        if merged and a_c <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b_c))
        else:
            merged.append((a_c, b_c))
    cuts = merged

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
    warns = write_subs(spans, d / "demo-a2.srt", d / "captions.ass")
    ev = list(data["ev"] or [])
    # clicks made through the DOM (busy Mol* pages) have no pointerdown; their note stands in
    ev += [[t, "pointerdown", {"note": v}] for t, k, v in data["notes"] if k == "click"]
    ev.sort(key=lambda e: e[0])
    title = next(v for _, k, v in data["notes"] if k == "title-type")
    keys_v = [remap(t_type) - 0.012 + i * title["ms"] / 1000 for i in range(title["chars"])]
    keys_v += [to_v(t) for t in next((v for _, k, v in data["notes"] if k == "keys"), [])]
    scenes_v = [to_v(notes[k]) for k in ("title-off", "end-on") if k in notes]
    events = sfx_events(ev, to_v, data["myId"], keys_v, scenes_v)
    levels = mix(total, events, d / "mix.wav")
    mp4 = d / "demo-a2.mp4"
    encode(raw, d / "captions.ass", d / "mix.wav", mp4, d / "demo-a2.webm", fast, cuts, make_webm)
    final = duration(mp4)
    sh = sheets(mp4, d, final)
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
            str(mp4),
        ]
    ).stdout
    counts: dict[str, int] = {}
    for _, name, _ in events:
        group = "key" if name.startswith("key") else name
        counts[group] = counts.get(group, 0) + 1
    report = {
        "version": v,
        "raw_s": raw_total,
        "final_s": final,
        "cuts_s": [[round(a, 2), round(b, 2)] for a, b in cuts],
        "delta_s": delta,
        "typing_start_raw_s": t_type,
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
