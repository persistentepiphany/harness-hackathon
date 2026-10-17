"""Synthesize the UI sound effects for demo video A2.

Same generator as video A (click, tick, stop, chime and whoosh come out identical), plus six
keyboard key variants for the typed text. A2 has no background bed, so the pad is not written.
No sound-effects API key is available, so every sound is built from sine partials and filtered
noise with numpy/scipy. Output: 48 kHz, 16-bit stereo WAV files in <out>/sfx/.

Usage: .venv/bin/python make_sfx.py <out_dir>
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48_000
RNG = np.random.default_rng(7)


def t_axis(seconds: float) -> np.ndarray:
    return np.arange(int(SR * seconds)) / SR


def env_ad(n: int, attack_s: float, decay_s: float) -> np.ndarray:
    """Linear attack, exponential decay (time constant decay_s)."""
    t = np.arange(n) / SR
    a = np.clip(t / max(attack_s, 1e-4), 0, 1)
    d = np.exp(-np.maximum(t - attack_s, 0) / decay_s)
    return a * d


def fade(x: np.ndarray, fin_s: float, fout_s: float) -> np.ndarray:
    n = len(x)
    fi, fo = int(SR * fin_s), int(SR * fout_s)
    g = np.ones(n)
    if fi:
        g[:fi] = np.sin(np.linspace(0, np.pi / 2, fi)) ** 2
    if fo:
        g[-fo:] = np.cos(np.linspace(0, np.pi / 2, fo)) ** 2
    return x * (g[:, None] if x.ndim == 2 else g)


def bandpass(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lowpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, fc, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def highpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, fc, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def stereo(x: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """Equal-power pan, pan in [-1, 1]."""
    a = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def click() -> np.ndarray:
    """Soft UI click: a short low-passed noise transient plus a damped 1.9 kHz body."""
    n = int(SR * 0.07)
    t = np.arange(n) / SR
    noise = bandpass(RNG.standard_normal(n), 900, 5000) * env_ad(n, 0.0008, 0.006)
    body = np.sin(2 * np.pi * 1900 * t) * env_ad(n, 0.001, 0.012) * 0.5
    thump = np.sin(2 * np.pi * 420 * t) * env_ad(n, 0.001, 0.010) * 0.35
    x = lowpass(noise * 0.6 + body + thump, 6000)
    return stereo(fade(x, 0.0005, 0.01))


def tick() -> np.ndarray:
    """Light tick for a streamed check result: a short, high, glassy blip."""
    n = int(SR * 0.05)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 3100 * t) * env_ad(n, 0.0006, 0.007)
    x += 0.35 * np.sin(2 * np.pi * 4650 * t) * env_ad(n, 0.0006, 0.004)
    x += 0.15 * highpass(RNG.standard_normal(n), 3000) * env_ad(n, 0.0003, 0.002)
    return stereo(fade(x, 0.0003, 0.01), pan=0.15)


def stop_tone() -> np.ndarray:
    """Low stop tone: two soft descending notes (G3 then D3) with a little second harmonic."""
    out = np.zeros(int(SR * 0.9))
    for start, f in ((0.0, 196.0), (0.16, 146.8)):
        n = int(SR * 0.7)
        t = np.arange(n) / SR
        note = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
        note *= env_ad(n, 0.012, 0.18)
        i = int(SR * start)
        out[i : i + n] += note * (1.0 if start == 0 else 0.9)
    return stereo(fade(lowpass(out, 1800), 0.002, 0.08))


def chime() -> np.ndarray:
    """Gentle success chime: two bell-like notes (E5, B5) with soft inharmonic partials."""
    out = np.zeros(int(SR * 2.2))
    for start, f, g in ((0.0, 659.25, 1.0), (0.13, 987.77, 0.8)):
        n = int(SR * 2.0)
        t = np.arange(n) / SR
        note = np.zeros(n)
        for ratio, amp, dec in (
            (1.0, 1.0, 0.65),
            (2.0, 0.28, 0.35),
            (2.76, 0.12, 0.22),
            (5.4, 0.04, 0.1),
        ):
            note += amp * np.sin(2 * np.pi * f * ratio * t) * env_ad(n, 0.004, dec)
        i = int(SR * start)
        out[i : i + n] += note * g
    x = lowpass(out, 7000)
    left = x
    right = np.concatenate([np.zeros(int(SR * 0.006)), x[: -int(SR * 0.006)]])
    return fade(np.stack([left, right], axis=1), 0.001, 0.4)


def whoosh() -> np.ndarray:
    """Short whoosh for a page change: noise through a band-pass that sweeps up, panned L to R."""
    dur = 0.55
    n = int(SR * dur)
    noise = RNG.standard_normal(n)
    hop = 256
    out = np.zeros(n)
    win = np.hanning(hop * 2)
    for k, i in enumerate(range(0, n - hop * 2, hop)):
        frac = i / n
        fc = 350 * (6.0**frac)
        seg = noise[i : i + hop * 2]
        sos = signal.butter(2, [fc * 0.6, fc * 1.6], btype="band", fs=SR, output="sos")
        out[i : i + hop * 2] += signal.sosfilt(sos, seg) * win
        del k
    t = np.arange(n) / SR
    envl = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    x = out * envl
    pan = np.linspace(-0.6, 0.6, n)
    a = (pan + 1) * np.pi / 4
    return fade(np.stack([x * np.cos(a), x * np.sin(a)], axis=1), 0.01, 0.06)


KEY_VARIANTS = 6


def key(variant: int) -> np.ndarray:
    """Dry keyboard key: a 2-7 kHz noise snap, a faint plastic body and a low thock.

    The variants differ a little in pitch, brightness and pan, so a typed line does not repeat
    one sample.
    """
    rng = np.random.default_rng(100 + variant)
    n = int(SR * 0.045)
    t = np.arange(n) / SR
    spread = (variant - (KEY_VARIANTS - 1) / 2) / KEY_VARIANTS
    snap = bandpass(rng.standard_normal(n), 2000 * (1 + 0.15 * spread), 7000) * env_ad(
        n, 0.0003, 0.0028
    )
    body = np.sin(2 * np.pi * 2400 * (1 + 0.08 * spread) * t) * env_ad(n, 0.0004, 0.0035) * 0.22
    thock = np.sin(2 * np.pi * (240 + 40 * spread) * t) * env_ad(n, 0.0008, 0.007) * 0.3
    x = lowpass(snap * 0.9 + body + thock, 9000)
    return stereo(fade(x, 0.0002, 0.006), pan=0.2 * spread)


def pad(seconds: float) -> np.ndarray:
    """Very quiet ambient bed: a slow, detuned A-major-add9 chord, low-passed, with slow swells."""
    t = t_axis(seconds)
    notes = [110.0, 164.81, 220.0, 246.94, 329.63]
    left = np.zeros_like(t)
    right = np.zeros_like(t)
    for k, f in enumerate(notes):
        amp = 1.0 / (1 + 0.6 * k)
        lfo = 0.75 + 0.25 * np.sin(2 * np.pi * (0.05 + 0.013 * k) * t + k)
        left += amp * lfo * np.sin(2 * np.pi * (f * 0.9985) * t + 0.3 * k)
        right += amp * lfo * np.sin(2 * np.pi * (f * 1.0015) * t + 0.7 * k)
    air = lowpass(RNG.standard_normal(len(t)), 900) * 0.04
    left = lowpass(left + air, 1400)
    right = lowpass(right + air, 1400)
    x = np.stack([left, right], axis=1)
    return fade(x, 2.5, 3.5)


def write_wav(path: Path, x: np.ndarray) -> None:
    x = x / max(1e-9, float(np.max(np.abs(x)))) * 0.5
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> None:
    out = Path(sys.argv[1])
    sfx = out / "sfx"
    sfx.mkdir(parents=True, exist_ok=True)
    for name, fn in (
        ("click", click),
        ("tick", tick),
        ("stop", stop_tone),
        ("chime", chime),
        ("whoosh", whoosh),
    ):
        write_wav(sfx / f"{name}.wav", fn())
    for k in range(KEY_VARIANTS):
        write_wav(sfx / f"key{k}.wav", key(k))
    print("wrote", sorted(p.name for p in sfx.glob("*.wav")))


if __name__ == "__main__":
    main()
