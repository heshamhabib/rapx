#!/usr/bin/env python3
"""
Synthesises the sci-fi "energy" world sounds (IDEA-31) that have no good real recording: the sonar pulse power,
healing (medic and heal crate), the Iron Curtain and the Phase Tank cloak. Same names as the originals, written to
mods/rapx/audio/sfx/<name>.ogg.

  python3 artsrc/audio/make_energy_sounds.py
"""
import os
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ogg  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mods", "rapx", "audio", "sfx")
SR = 44100
rng = np.random.default_rng(9)


def t_of(dur):
    return np.arange(int(dur * SR)) / SR


def osc(freq, t):
    f = np.broadcast_to(freq, t.shape)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, "same")


def bandnoise(t, centre, width):
    """Noise through a resonant band (two-pole filter per sample; centre may sweep)."""
    n = rng.normal(0, 1, len(t))
    c = np.broadcast_to(centre, t.shape)
    y = np.zeros(len(t))
    y1 = y2 = 0.0
    r = np.exp(-np.pi * width / SR)
    for i in range(len(t)):
        a1 = 2 * r * np.cos(2 * np.pi * c[i] / SR)
        y0 = n[i] * (1 - r) + a1 * y1 - r * r * y2
        y[i], y2, y1 = y0, y1, y0
    return y


def reverb(x, taps):
    out = np.zeros(len(x) + int(max(d for d, _ in taps) * SR))
    out[:len(x)] += x
    for d, g in taps:
        out[int(d * SR):int(d * SR) + len(x)] += x * g
    return out


def sonpulse():
    # Deep sonar ping falling slightly in pitch, muffled underwater echoes
    t = t_of(1.6)
    ping = osc(1150 - 60 * t, t) * np.minimum(1, t / 0.004) * np.exp(-t * 3.2)
    ping += 0.3 * osc(2300 - 120 * t, t) * np.exp(-t * 6)
    wet = reverb(lowpass(ping, 6), [(0.21, 0.4), (0.43, 0.22), (0.66, 0.11)])
    return wet


def heal2():
    # Soft rising shimmer of bell partials with a gentle tremolo
    t = t_of(0.9)
    x = np.zeros(len(t))
    for i, f in enumerate((660, 880, 1100, 1320, 1760)):
        start = i * 0.08
        tt = np.clip(t - start, 0, None)
        e = (t >= start) * np.minimum(1, tt / 0.02) * np.exp(-tt * 4)
        x += osc(f * (1 + 0.04 * tt), t) * e / (1 + i * 0.3)
    return x * (0.75 + 0.25 * np.sin(2 * np.pi * 9 * t)) * np.minimum(1, (0.9 - t) / 0.15)


def ironcur9():
    # Heavy energy field slamming on: low hum swell, sweeping resonant roar, metallic ring
    t = t_of(2.2)
    swell = np.minimum(1, t / 0.35) * np.exp(-np.clip(t - 0.35, 0, None) * 1.4)
    hum = (osc(55, t) + 0.6 * osc(110.5, t) + 0.3 * np.sign(osc(82.5, t))) * swell
    roar = bandnoise(t, 300 + 1500 * np.exp(-t * 2.5), 120) * 6 * swell
    ring = osc(740, t) * 0.25 * np.exp(-t * 2) * np.minimum(1, t / 0.3)
    return hum * 0.5 + roar + ring


def appear1():
    # Cloak shimmer: a phasing noise band sweeping up, with fine sparkles
    t = t_of(0.95)
    env = np.sin(np.pi * t / 0.95) ** 1.5
    band = bandnoise(t, 400 + 3200 * (t / 0.95) ** 1.3, 250) * 5
    sparkle = rng.normal(0, 1, len(t)) * (rng.random(len(t)) < 0.004) * 3
    tone = osc(900 + 900 * t, t) * 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 14 * t))
    return (band + lowpass(sparkle, 3) + tone) * env


def write_ogg(path, x):
    x = x / max(1e-9, np.max(np.abs(x))) * 0.8
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
    ogg.encode(tmp.name, path)
    os.remove(tmp.name)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("sonpulse", sonpulse), ("heal2", heal2), ("ironcur9", ironcur9), ("appear1", appear1)):
        x = fn()
        write_ogg(os.path.join(OUT, name + ".ogg"), x)
        print(f"{name}.ogg  {len(x) / SR:.2f}s")


if __name__ == "__main__":
    main()
