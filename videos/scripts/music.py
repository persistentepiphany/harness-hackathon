"""Compose and render film B's music bed with numpy: 100 BPM, 4/4, 50 bars (120 s).

    uv run --no-project --with numpy --with imageio-ffmpeg python3 scripts/music.py

Writes public/audio/demo-b/music.wav (the mix) and public/audio/demo-b/stems/{drums,kick,hats,pad,pluck,bass}.wav.
scripts/beats.py measures the tempo from the drum stem, then the beat phase and downbeat from the kick stem
(the off-beat hats carry more spectral flux than the soft kick, so the full drum stem locks to the "and"s).

Song map (bars are 1-based, as in cues.ts):
  1-4    pad and a sparse muted pluck, no drums        cold open
  5-13   light kick on 1 and 3, closed hats on the off-beats   new run, sources
  14-20  soft sub bass joins, ghost sixteenth hats      job running, log
  20     drums and bass drop out for one bar            the verdict lands
  21-23  kick and bass back, no hats
  24-44  full groove, a quiet bell arpeggio on top      report, ensemble, agent
  45-48  drums and bass out, pad and pluck              closing line
  49-50  pad alone on the tonic chord, fades out        logo
Everything is deterministic (fixed random seed), so the WAV is reproducible.
"""

import pathlib
import subprocess
import wave

import imageio_ffmpeg
import numpy as np

SR = 48000
BPM = 100.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
BARS = 50
DURATION = BARS * BAR
N = int(round(DURATION * SR))
OUT = pathlib.Path(__file__).resolve().parents[1] / "public/audio/demo-b"
rng = np.random.default_rng(20261017)


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def at(bar: int, beat: float = 1.0) -> float:
    """Seconds at a 1-based bar and beat."""
    return (bar - 1) * BAR + (beat - 1) * BEAT


# D major: Dmaj9, Bm9, Gmaj9, A(add9). One chord per bar.
CHORDS = [
    [50, 57, 61, 64, 66],
    [47, 54, 57, 61, 62],
    [43, 50, 54, 57, 59],
    [45, 52, 59, 61, 64],
]
ROOTS = [38, 35, 31, 33]
# Pluck arpeggios, eighth notes, one octave above the pad.
ARPS = [
    [62, 69, 73, 76, 78, 76, 73, 69],
    [59, 66, 69, 73, 74, 73, 69, 66],
    [55, 62, 66, 69, 71, 69, 66, 62],
    [57, 64, 69, 71, 73, 71, 69, 64],
]


def chord_of(bar: int) -> int:
    if bar >= 49:
        return 0
    return (bar - 1) % 4


def add(track: np.ndarray, start_s: float, sig: np.ndarray, pan: float = 0.0) -> None:
    i = int(round(start_s * SR))
    if i >= N:
        return
    sig = sig[: N - i]
    left = np.cos((pan + 1) * np.pi / 4)
    right = np.sin((pan + 1) * np.pi / 4)
    track[i : i + len(sig), 0] += sig * left * np.sqrt(2)
    track[i : i + len(sig), 1] += sig * right * np.sqrt(2)


def one_pole_lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Frequency-domain gentle lowpass (12 dB/oct shape), applied to the whole signal."""
    spec = np.fft.rfft(x, axis=0)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    gain = 1 / (1 + (freqs / cutoff) ** 2)
    return np.fft.irfft(spec * (gain[:, None] if x.ndim == 2 else gain), n=len(x), axis=0)


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    spec = np.fft.rfft(x, axis=0)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    gain = (freqs / cutoff) ** 2 / (1 + (freqs / cutoff) ** 2)
    return np.fft.irfft(spec * (gain[:, None] if x.ndim == 2 else gain), n=len(x), axis=0)


def reverb(x: np.ndarray, seconds: float = 2.2, mix: float = 0.25) -> np.ndarray:
    """Convolution with decaying stereo noise; a plain, soft room."""
    length = int(seconds * SR)
    t = np.arange(length) / SR
    env = np.exp(-t * 6.9 / seconds)
    ir = rng.standard_normal((length, 2)) * env[:, None]
    ir = one_pole_lowpass(ir, 5000)
    ir /= np.sqrt((ir**2).sum(axis=0))
    size = 1 << int(np.ceil(np.log2(len(x) + length)))
    wet = np.fft.irfft(np.fft.rfft(x, size, axis=0) * np.fft.rfft(ir, size, axis=0), size, axis=0)[: len(x)]
    return x * (1 - mix) + wet * mix


# ------------------------------------------------------------------ pad
def pad_voice(freq: float, length_s: float) -> np.ndarray:
    n = int(length_s * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for detune in (-0.07, 0.0, 0.06):  # semitones
        f = freq * 2 ** (detune / 12)
        phase = rng.uniform(0, 2 * np.pi)
        for k in range(1, 9):
            out += np.sin(2 * np.pi * f * k * t + phase * k) * (1 / k) * np.exp(-0.35 * k)
    return out / 3


def render_pad() -> np.ndarray:
    track = np.zeros((N, 2))
    attack, release = 0.9, 1.6
    for bar in range(1, BARS + 1):
        notes = CHORDS[chord_of(bar)]
        hold = BAR if bar < 49 else 2 * BAR - 0.4
        if bar == 50:
            continue  # bar 49 holds through the end
        length = hold + release
        n = int(length * SR)
        t = np.arange(n) / SR
        env = np.minimum(1, t / attack)
        env *= np.where(t < hold, 1.0, np.exp(-(t - hold) * 4.0 / release))
        level = 0.66 if bar <= 4 else 0.5 if bar < 45 else 0.62
        for j, m in enumerate(notes):
            sig = pad_voice(midi(m), length) * env * level / len(notes)
            add(track, at(bar), sig, pan=(j - 2) * 0.25)
    track = one_pole_lowpass(track, 1800)
    return track


# ------------------------------------------------------------------ pluck
def pluck(freq: float, velocity: float, length_s: float = 0.9) -> np.ndarray:
    n = int(length_s * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for k in range(1, 7):
        sig += np.sin(2 * np.pi * freq * k * t) * (0.8**k) * np.exp(-t * (7 + 5 * k))
    click = rng.standard_normal(n) * np.exp(-t * 900) * 0.05
    sig = (sig + click) * np.minimum(1, t / 0.002)
    return sig * velocity


def delay(x: np.ndarray, seconds: float, feedback: float, taps: int = 4) -> np.ndarray:
    d = int(seconds * SR)
    out = x.copy()
    for k in range(1, taps + 1):
        shifted = np.zeros_like(x)
        shifted[d * k :] = x[: -d * k]
        if k % 2 == 1:  # ping-pong: odd taps swap channels
            shifted = shifted[:, ::-1]
        out += shifted * feedback**k
    return out


def render_pluck() -> np.ndarray:
    track = np.zeros((N, 2))
    for bar in range(1, 49):
        arp = ARPS[chord_of(bar)]
        for i, m in enumerate(arp):
            if bar <= 4 and i % 2 == 1:
                continue  # sparse intro: quarter notes only
            if bar >= 45 and i % 2 == 1 and i != 3:
                continue
            accent = 1.0 if i % 4 == 0 else 0.72
            vel = accent * (0.9 + 0.1 * rng.random()) * (0.75 if bar <= 4 else 1.0)
            add(track, at(bar) + i * BEAT / 2, pluck(midi(m), vel), pan=0.3 if i % 2 else -0.3)
    track = one_pole_lowpass(track, 2600)
    track = delay(track, 0.45, 0.28)
    return track * 0.16


def bell(freq: float, length_s: float = 1.6) -> np.ndarray:
    n = int(length_s * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * freq * 3.5 * t) * 1.2 * np.exp(-t * 4)
    return np.sin(2 * np.pi * freq * t + mod) * np.exp(-t * 3.2) * np.minimum(1, t / 0.004)


def render_bells() -> np.ndarray:
    track = np.zeros((N, 2))
    for bar in range(24, 45):
        notes = CHORDS[chord_of(bar)]
        for beat in (1, 3):
            m = notes[-1] + 12 if beat == 1 else notes[-2] + 12
            add(track, at(bar, beat), bell(midi(m)) * 0.5, pan=-0.4 if beat == 1 else 0.4)
    track = delay(track, 0.45, 0.3)
    return track * 0.05


# ------------------------------------------------------------------ drums
def kick() -> np.ndarray:
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    freq = 46 + 70 * np.exp(-t / 0.035)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t / 0.22)
    click = highpass(rng.standard_normal(n) * np.exp(-t * 700), 2000) * 0.08
    return (body + click) * np.minimum(1, t / 0.001)


NOISE = highpass(rng.standard_normal(int(0.2 * SR)), 7000)


def hat(decay: float) -> np.ndarray:
    t = np.arange(len(NOISE)) / SR
    return NOISE * np.exp(-t / decay)


def render_drums() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    track = np.zeros((N, 2))
    hats = np.zeros((N, 2))
    duck = np.ones(N)
    k = kick()
    duck_shape = 1 - 0.35 * np.exp(-np.arange(int(0.3 * SR)) / SR / 0.09)
    for bar in range(5, 45):
        if bar == 20:
            continue
        for beat in (1, 3):
            add(track, at(bar, beat), k * 0.55)
            i = int(at(bar, beat) * SR)
            seg = duck[i : i + len(duck_shape)]
            duck[i : i + len(duck_shape)] = np.minimum(seg, duck_shape[: len(seg)])
        if bar in (21, 22, 23):
            continue
        for eighth in range(8):
            if eighth % 2 == 1:
                add(hats, at(bar) + eighth * BEAT / 2, hat(0.035) * 0.16, pan=0.25)
        if bar >= 14:
            for sixteenth in (3, 7, 11, 15):
                if (bar + sixteenth) % 3 == 0:
                    add(hats, at(bar) + sixteenth * BEAT / 4, hat(0.02) * 0.06, pan=-0.2)
    return track, hats, duck


def render_bass(duck: np.ndarray) -> np.ndarray:
    track = np.zeros((N, 2))
    for bar in range(14, 45):
        if bar == 20:
            continue
        root = ROOTS[chord_of(bar)]
        length = BAR + 0.3
        n = int(length * SR)
        t = np.arange(n) / SR
        f = midi(root)
        sig = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
        env = np.minimum(1, t / 0.05) * np.where(t < BAR - 0.05, 1, np.exp(-(t - BAR + 0.05) * 20))
        add(track, at(bar), sig * env * 0.15)
    return track * duck[:, None]


# ------------------------------------------------------------------ mix
def loudness(path: pathlib.Path) -> float:
    out = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stderr
    summary = out[out.rfind("Summary:") :]
    return float(summary.split("I:")[1].split("LUFS")[0])


def write(path: pathlib.Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main() -> None:
    kicks, hats, duck = render_drums()
    drums = kicks + hats
    pad = render_pad() * duck[:, None] ** 0.5
    pluck_track = render_pluck() + render_bells()
    bass = render_bass(duck)
    mix = reverb(pad + pluck_track, 2.4, 0.3) + drums + bass
    # Fade the last 2.2 s, never cut the ring-out.
    fade = int(2.2 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 2
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)

    target = -15.5
    tmp = OUT / "music-raw.wav"
    write(tmp, mix / max(1e-9, np.abs(mix).max()) * 0.5)
    measured = loudness(tmp)
    gain = 10 ** ((target - measured) / 20) * 0.5 / max(1e-9, np.abs(mix).max())
    tmp.unlink()
    peak = np.abs(mix * gain).max()
    if peak > 0.89:  # keep true-peak headroom
        gain *= 0.89 / peak
    write(OUT / "music.wav", mix * gain)
    stems = (("drums", drums), ("kick", kicks), ("hats", hats), ("pad", pad), ("pluck", pluck_track), ("bass", bass))
    for name, stem in stems:
        write(OUT / "stems" / f"{name}.wav", stem * gain)
    print(f"music.wav {DURATION:.1f} s, {BARS} bars at {BPM} BPM, integrated {loudness(OUT / 'music.wav'):.1f} LUFS")


if __name__ == "__main__":
    main()
