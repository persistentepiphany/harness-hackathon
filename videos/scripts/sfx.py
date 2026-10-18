"""Synthesise film B's interface sounds with numpy and measure each file's peak time.

    uv run --no-project --with numpy --with imageio-ffmpeg python3 scripts/sfx.py

No sound API is available (EACHLABS_API_KEY is unset), so every effect is made here, dry and short:
  click   soft press (buttons, the prompt field, the overlay toggle)
  key     very soft key tap, three pitches (typing)
  tick    small high tick (a decision row, a source row, a layer or step landing)
  chime   two soft sine bells a fifth apart, D5 then A5 (the verdict, the logo)
  whoosh  short filtered noise swell (three scene changes only)
Writes public/audio/demo-b/sfx/*.wav and src/videos/demo-b/sfx-peaks.json (seconds from file start to
the loudest sample), so a sound placed at `cue - peak` puts its transient on the cue frame.
"""

import json
import pathlib
import wave

import numpy as np

SR = 48000
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "public/audio/demo-b/sfx"
PEAKS = ROOT / "src/videos/demo-b/sfx-peaks.json"
rng = np.random.default_rng(7)


def t_axis(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def band(x: np.ndarray, low: float, high: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    gain = ((f >= low) & (f <= high)).astype(float)
    # soften the band edges a little
    gain = np.convolve(gain, np.hanning(31) / np.hanning(31).sum(), mode="same")
    return np.fft.irfft(spec * gain, n=len(x))


def click() -> np.ndarray:
    t = t_axis(0.09)
    body = np.sin(2 * np.pi * 1900 * t) * np.exp(-t / 0.012)
    low = np.sin(2 * np.pi * 420 * t) * np.exp(-t / 0.02) * 0.5
    noise = band(rng.standard_normal(len(t)), 1500, 8000) * np.exp(-t / 0.003) * 0.6
    return (body * 0.5 + low + noise) * np.minimum(1, t / 0.0008)


def key(pitch: float) -> np.ndarray:
    t = t_axis(0.05)
    tone = np.sin(2 * np.pi * pitch * t) * np.exp(-t / 0.008)
    noise = band(rng.standard_normal(len(t)), 2000, 9000) * np.exp(-t / 0.004) * 0.5
    return (tone * 0.6 + noise) * np.minimum(1, t / 0.0005)


def tick() -> np.ndarray:
    t = t_axis(0.06)
    tone = np.sin(2 * np.pi * 3100 * t) * np.exp(-t / 0.009)
    tone += np.sin(2 * np.pi * 4700 * t) * np.exp(-t / 0.005) * 0.3
    return tone * np.minimum(1, t / 0.0005)


def bell(freq: float, seconds: float) -> np.ndarray:
    t = t_axis(seconds)
    partials = [(1.0, 1.0, 1.0), (2.0, 0.35, 1.7), (3.01, 0.12, 2.6), (4.2, 0.05, 3.5)]
    sig = sum(a * np.sin(2 * np.pi * freq * r * t) * np.exp(-t * d * 2.2) for r, a, d in partials)
    return sig * np.minimum(1, t / 0.003)


def chime() -> np.ndarray:
    first = bell(587.33, 1.6)
    second = bell(880.0, 1.6) * 0.8
    out = np.zeros(int(1.9 * SR))
    out[: len(first)] += first
    offset = int(0.12 * SR)
    out[offset : offset + len(second)] += second
    return out


def whoosh() -> np.ndarray:
    t = t_axis(0.7)
    noise = rng.standard_normal(len(t))
    # sweep a band upwards by mixing three static bands with moving weights
    lo, mid, hi = band(noise, 250, 900), band(noise, 900, 2600), band(noise, 2600, 7000)
    u = t / t[-1]
    sig = lo * (1 - u) + mid * np.sin(np.pi * u) + hi * u**2
    env = np.sin(np.pi * np.clip(u / 0.8, 0, 1)) ** 2 * np.where(u > 0.8, np.exp(-(u - 0.8) * 20), 1)
    return sig * env


def write(name: str, x: np.ndarray, level: float) -> float:
    x = x / np.abs(x).max() * level
    OUT.mkdir(parents=True, exist_ok=True)
    stereo = np.stack([x, x], axis=1)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes((np.clip(stereo, -1, 1) * 32767).astype(np.int16).tobytes())
    return round(float(np.argmax(np.abs(x))) / SR, 4)


def main() -> None:
    peaks = {
        "click": write("click", click(), 0.7),
        "key1": write("key1", key(2400), 0.5),
        "key2": write("key2", key(2700), 0.5),
        "key3": write("key3", key(2150), 0.5),
        "tick": write("tick", tick(), 0.5),
        "chime": write("chime", chime(), 0.6),
        "whoosh": write("whoosh", whoosh(), 0.6),
    }
    PEAKS.write_text(json.dumps(peaks, indent=1) + "\n")
    print(peaks)


if __name__ == "__main__":
    main()
