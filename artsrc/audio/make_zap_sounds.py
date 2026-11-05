#!/usr/bin/env python3
"""
Synthesises the Battle Droid's energy-blaster "zap" (sci-fi pew): a tone sweeping fast from high to low with a
buzzy harmonic, an electric crackle on the attack and a short metallic echo. Two zaps 120 ms apart per burst
(DroidBlaster: PxTracer Rounds 2, RoundInterval 3 ticks). Writes mods/rapx/audio/weapons/droid-zap1..3.wav.

  python3 artsrc/audio/make_zap_sounds.py
"""
import os
import wave

import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mods", "rapx", "audio", "weapons")
SR = 44100


def zap(rng):
    dur = 0.24
    t = np.arange(int(dur * SR)) / SR
    f0, f1 = rng.uniform(1700, 2100), rng.uniform(260, 340)
    freq = f1 + (f0 - f1) * np.exp(-t * rng.uniform(16, 22))  # fast exponential pitch fall
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(phase) + 0.45 * np.sign(np.sin(phase * 2.01)) * 0.5 + 0.25 * np.sin(phase * 3.02)
    env = np.minimum(1, t / 0.004) * np.exp(-t * 11)
    # electric crackle: band-limited noise bursts on the attack
    noise = rng.normal(0, 1, len(t))
    noise = np.convolve(noise, np.ones(6) / 6, "same") * (rng.random(len(t)) < 0.35)
    crackle = noise * np.exp(-t * 45) * 0.6
    x = tone * env * 0.7 + crackle
    # short metallic echo (two taps)
    out = np.zeros(len(x) + int(0.09 * SR))
    out[:len(x)] += x
    for delay, gain in ((0.045, 0.32), (0.085, 0.16)):
        d = int(delay * SR)
        out[d:d + len(x)] += x * gain
    return out


def burst(rng):
    a, b = zap(rng), zap(rng)
    gap = int(0.12 * SR)
    out = np.zeros(gap + len(b))
    out[:len(a)] += a
    out[gap:gap + len(b)] += b * 0.92
    return out


def save(name, x):
    x = x / max(1e-6, np.abs(x).max()) * 0.75
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    print("wrote", name, f"{len(x) / SR:.2f}s")


if __name__ == "__main__":
    rng = np.random.default_rng(11)
    for n in range(1, 4):
        save(f"droid-zap{n}.wav", burst(rng))
