"""Assemble demo film C: stills + UI recording -> xfade timeline, captions, music, sfx, two MP4s.

Usage: .venv/bin/python build.py <work_dir> <rec_dir> <version>
Reads <work>/shots.json, <work>/stills/*.png and <rec>/{frames.txt,events.json}.
Writes <work>/<version>/{demo-c.mp4, demo-c-nosfx.mp4, demo-c.srt, contact.jpg} and the mixes.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import make_sfx as S  # noqa: E402

WORK, REC, VER = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
OUT = WORK / VER
OUT.mkdir(parents=True, exist_ok=True)
CL = WORK / "clips"
CL.mkdir(exist_ok=True)
FPS = 30
SR = S.SR
GRAPH_XY = (708, 75)
GRAPH_WH = (1120, 790)


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-3000:])
        raise SystemExit(f"failed: {' '.join(cmd[:8])}")


def words(s: str) -> int:
    return len(s.split())


def hold(s: str) -> float:
    return max(1.5, 0.3 * words(s))


shots = json.loads((WORK / "shots.json").read_text())
ev = json.loads((REC / "events.json").read_text())
# cut the Jobs page loading state out of the recording (seconds in recording time)
UI_CUTS = [(35.9, 37.7)]


def apply_cuts() -> Path:
    lines = (REC / "frames.txt").read_text().splitlines()
    out = ["ffconcat version 1.0"]
    tcur = 0.0
    last = None
    for i, l in enumerate(lines):
        if l.startswith("file") and i + 1 < len(lines) and lines[i + 1].startswith("duration"):
            d = float(lines[i + 1].split()[1])
            a, b = tcur, tcur + d
            keep = d
            for c0, c1 in UI_CUTS:
                keep -= max(0.0, min(b, c1) - max(a, c0))
            if keep > 1e-4:
                out += [l, f"duration {keep:.4f}"]
                last = l
            tcur = b
    if last:
        out.append(last)
    p = REC / "frames_cut.txt"
    p.write_text("\n".join(out) + "\n")
    return p


def shift(t_: float) -> float:
    for c0, c1 in UI_CUTS:
        if t_ >= c1:
            t_ -= c1 - c0
        elif t_ > c0:
            t_ = c0
    return t_


FRAMES = apply_cuts()
CAP_FIX = {"Ensemble shows every structure the run produced, with its values.":
           "Ensemble lays out every structure in a run. This one holds the 3PTB reference."}
ev["ev"] = [[shift(t_), k, CAP_FIX.get(v, v) if k == "cap" else v] for t_, k, v in ev["ev"]]
ui_dur = round(ev["duration"] - sum(c1 - c0 for c0, c1 in UI_CUTS), 3)

# ------------------------------------------------------------------ clips
clips = []
for s in shots:
    name = s["name"]
    out = CL / f"{name}.mp4"
    if name == "UI":
        s["dur"] = ui_dur
        if os.environ.get("REUSE") and (OUT / "video.mp4").exists():
            clips.append(out)
            continue
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(FRAMES),
             "-loop", "1", "-i", str(WORK / "stills/zz_uiband.png"),
             "-filter_complex",
             f"[0:v]scale=1920:940:flags=lanczos,setsar=1,fps={FPS}[ui];[1:v][ui]overlay=0:0:shortest=0,"
             f"trim=duration={ui_dur},format=yuv420p[v]",
             "-map", "[v]", "-t", str(ui_dur), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "12", str(out)])
    elif os.environ.get("REUSE") and (OUT / "video.mp4").exists():
        pass
    elif name == "s5_graph":
        d = s["dur"]
        gh = 2655
        travel = gh - GRAPH_WH[1]
        # hold 1.2 s, one smooth scroll of 3.4 s, then look
        y = (f"{travel}*(0.5-0.5*cos(PI*min(max((t-1.2)/3.4,0),1)))")
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / f"stills/{name}.png"),
             "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / "stills/graph_tall.png"),
             "-filter_complex",
             f"[1:v]crop={GRAPH_WH[0]}:{GRAPH_WH[1]}:0:'{y}'[g];[0:v][g]overlay={GRAPH_XY[0]}:{GRAPH_XY[1]},format=yuv420p[v]",
             "-map", "[v]", "-t", str(d), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", str(out)])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / f"stills/{name}.png"),
             "-vf", "format=yuv420p", "-t", str(s["dur"]), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
             "-tune", "stillimage", "-crf", "12", str(out)])
    clips.append(out)

# ------------------------------------------------------------------ timeline
starts = [0.0]
for i in range(1, len(shots)):
    starts.append(starts[-1] + shots[i - 1]["dur"] - shots[i]["xf"])
T = starts[-1] + shots[-1]["dur"]
print(f"total {T:.2f} s")
for s, st in zip(shots, starts):
    print(f"  {st:7.2f}  {s['dur']:6.2f}  {s['name']}")

# ------------------------------------------------------------------ captions
caps: list[tuple[float, float, str]] = []


def group(name: str) -> str:
    return name.rstrip("0123456789")


ends: dict[str, float] = {}
for i, (s, st) in enumerate(zip(shots, starts)):
    ends[group(s["name"])] = st + s["dur"] - (shots[i + 1]["xf"] if i + 1 < len(shots) else 0) - 0.1
raw: list[tuple[float, str, str]] = []
for s, st in zip(shots, starts):
    if s["name"] == "UI":
        raw += [(st + t_, v, "UI") for t_, k, v in ev["ev"] if k == "cap"]
    else:
        raw += [(st + o, txt, group(s["name"])) for o, txt in s["caps"]]
raw.sort()
for j, (a, txt, g_) in enumerate(raw):
    b = ends[g_]
    if j + 1 < len(raw):
        b = min(b, raw[j + 1][0] - 0.15)
    caps.append((a, b, txt))
    if b - a < hold(txt) - 0.01:
        print(f"WARN short caption {b - a:.2f} < {hold(txt):.2f}: {txt}")


def ass_ts(x: float) -> str:
    cs = int(round(x * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Geist Medium,34,&H00181A1A,&H00181A1A,&H00F4F7F7,&H00F4F7F7,0,0,0,0,100,100,0,0,1,0,0,1,80,720,46,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
for a, b, txt in caps:
    ass += f"Dialogue: 0,{ass_ts(a)},{ass_ts(b)},Cap,,0,0,0,,{txt}\n"
(OUT / "captions.ass").write_text(ass)


def ts(x: float) -> str:
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


srt = "".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(caps, 1))
(OUT / "demo-c.srt").write_text(srt)

# ------------------------------------------------------------------ video
inputs: list[str] = []
for c in clips:
    inputs += ["-i", str(c)]
fc = []
prev = "[0:v]"
for i in range(1, len(clips)):
    xf = shots[i]["xf"]
    lab = f"[x{i}]"
    if xf <= 0:
        fc.append(f"{prev}[{i}:v]concat=n=2:v=1:a=0{lab}")
    else:
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xf}:offset={starts[i]:.3f}{lab}")
    prev = lab
fontsdir = WORK / "fonts"
fc.append(f"{prev}subtitles='{OUT / 'captions.ass'}':fontsdir='{fontsdir}',format=yuv420p[v]")
video = OUT / "video.mp4"
if not (os.environ.get("REUSE") and video.exists()):
  run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-r", str(FPS),
     "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
     "-movflags", "+faststart", str(video)])

# ------------------------------------------------------------------ music: 100 BPM, D major, numpy
N = int(math.ceil((T + 0.5) * SR))
t = np.arange(N) / SR
BPM = 100.0
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(20261018)


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


CHORDS = [[50, 57, 61, 64, 66], [47, 54, 57, 61, 62], [43, 50, 54, 57, 59], [45, 52, 59, 61, 64]]
ROOTS = [38, 35, 31, 33]
music = np.zeros(N)
nbars = int(math.ceil(T / BAR)) + 1
# pad: one chord per bar, slow attack, crossfaded
for b in range(nbars):
    ch = CHORDS[b % 4]
    a0 = int(b * BAR * SR)
    n = int((BAR + 1.2) * SR)
    if a0 >= N:
        break
    n = min(n, N - a0)
    tt = np.arange(n) / SR
    env = np.minimum(tt / 0.9, 1) * np.minimum(1, np.maximum(0, (BAR + 1.2 - tt) / 1.2))
    sig = np.zeros(n)
    for k, m in enumerate(ch):
        f = midi(m)
        sig += (np.sin(2 * np.pi * f * tt + k) + 0.25 * np.sin(2 * np.pi * 2 * f * tt + 0.3 * k)) / len(ch)
        sig += 0.5 * np.sin(2 * np.pi * f * 1.003 * tt + 2 * k) / len(ch)
    music[a0:a0 + n] += 0.32 * env * sig
# soft sub bass on beats 1 and 3, kick-like pulse, off-beat hats, sparse pluck
intro, outro = 2 * BAR, T - 3 * BAR
for b in range(nbars):
    for beat in range(4):
        tb = b * BAR + beat * BEAT
        i0 = int(tb * SR)
        if i0 >= N:
            continue
        groove = intro <= tb < outro
        if groove and beat in (0, 2):
            n = min(int(0.35 * SR), N - i0)
            tt = np.arange(n) / SR
            f = 58 * np.exp(-tt * 9) + 44
            music[i0:i0 + n] += 0.22 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)
            n2 = min(int(BEAT * 1.8 * SR), N - i0)
            tt2 = np.arange(n2) / SR
            music[i0:i0 + n2] += 0.10 * np.sin(2 * np.pi * midi(ROOTS[b % 4]) * tt2) * np.exp(-tt2 * 1.3) * np.minimum(tt2 / 0.02, 1)
        if groove:
            ih = int((tb + BEAT / 2) * SR)
            n = min(int(0.05 * SR), N - ih)
            if n > 0:
                noise = S.highpass(rng.standard_normal(n), 7000)
                music[ih:ih + n] += 0.018 * noise * np.exp(-np.arange(n) / SR * 70)
        # pluck: eighth-note arpeggio on beats 2 and 4, quiet
        if beat in (1, 3):
            ch = CHORDS[b % 4]
            for e in range(2):
                ip = int((tb + e * BEAT / 2) * SR)
                n = min(int(0.6 * SR), N - ip)
                if n <= 0:
                    continue
                tt = np.arange(n) / SR
                f = midi(ch[(beat + e * 2) % len(ch)] + 12)
                music[ip:ip + n] += 0.05 * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 6)
music = S.lowpass(music, 6000)
fade_in, fade_out = 1.5, 4.0
g = np.ones(N)
g[: int(fade_in * SR)] = np.linspace(0, 1, int(fade_in * SR))
fo0 = int((T - fade_out) * SR)
g[fo0:] = np.linspace(1, 0, N - fo0).clip(0, 1)
music *= g
music = np.stack([music, music * 0.98], axis=1)
music *= 0.06 / (np.sqrt(np.mean(music ** 2)) + 1e-9)  # about -18 dBFS RMS, then the master gain

# ------------------------------------------------------------------ sfx
fx = np.zeros((N, 2))
CLICK, TICK, WHOOSH = S.click(), S.tick(), S.whoosh()


def put(sig: np.ndarray, at: float, gain: float) -> None:
    i0 = int(at * SR)
    if i0 < 0 or i0 >= N:
        return
    if sig.ndim == 1:
        sig = np.stack([sig, sig], axis=1)
    n = min(len(sig), N - i0)
    fx[i0:i0 + n] += gain * sig[:n]


def norm(x: np.ndarray) -> np.ndarray:
    return x / (np.max(np.abs(x)) + 1e-9)


CLICK, TICK, WHOOSH = norm(CLICK), norm(TICK), norm(WHOOSH)
n_click = n_key = n_whoosh = 0
for i, (s, st) in enumerate(zip(shots, starts)):
    if i == 0:
        continue
    kind = s["sfx"]
    if kind == "whoosh":
        put(WHOOSH, st - 0.15, 10 ** (-30 / 20)); n_whoosh += 1
    elif kind == "tick":
        put(TICK, st + 0.05, 10 ** (-31 / 20))
ui_st = starts[[s["name"] for s in shots].index("UI")]
evs = ev["ev"]
type_t = [(tt_, v) for tt_, k, v in evs if k == "type"]
type_end = [tt_ for tt_, k, v in evs if k == "typeEnd"]
for tt_, k, v in evs:
    if k == "click":
        put(CLICK, ui_st + tt_, 10 ** (-28 / 20)); n_click += 1
    if k == "route":
        put(WHOOSH, ui_st + tt_ + 0.1, 10 ** (-36 / 20))
for (a, nchar), b in zip(type_t, type_end):
    step = (b - a) / max(nchar, 1)
    for c in range(nchar):
        put(TICK, ui_st + a + c * step + rng.uniform(-0.01, 0.01), 10 ** ((-35 + rng.uniform(-2, 1)) / 20)); n_key += 1
print(f"sfx: {n_click} clicks, {n_key} key ticks, {n_whoosh} scene whooshes")

MASTER = 0.9


def write(path: Path, x: np.ndarray) -> None:
    x = np.clip(x * MASTER, -0.98, 0.98)
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


write(OUT / "mix_sfx.wav", music + fx)
write(OUT / "mix_nosfx.wav", music)
for wav, name in ((OUT / "mix_sfx.wav", "demo-c.mp4"), (OUT / "mix_nosfx.wav", "demo-c-nosfx.mp4")):
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{T:.3f}", "-movflags", "+faststart", str(OUT / name)])

# contact sheet: one frame every 10 s
run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT / "demo-c.mp4"), "-vf", "fps=1/10,scale=480:-1,tile=4x4:padding=4",
     "-frames:v", "1", str(OUT / "contact.jpg")])
(OUT / "timeline.json").write_text(json.dumps({"total": T, "shots": [[s["name"], st, s["dur"]] for s, st in zip(shots, starts)],
                                               "captions": caps}, indent=1))
print("done", OUT)
