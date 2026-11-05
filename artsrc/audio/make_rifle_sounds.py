#!/usr/bin/env python3
"""
Builds the small-arms sounds (rifle bursts, machine-gun and pistol shots) from real AR-15, AK-47, 1911 and Walther recordings of The Free Firearm Sound Library
(CC0 - no rights reserved, https://opengameart.org/content/the-free-firearm-sound-library, unpacked in
artsrc/audio/firearms/; the work/ copies are 44.1 kHz mono made with afconvert).

Each burst: 3 rounds 80 ms apart (the PxTracer burst: 3 rounds, 2 ticks apart), every round a single recorded shot
with a little pitch and level variation, the room tail of the last one kept. Writes
mods/rapx/audio/weapons/rifle-burst1..3.wav (AR-15) and ak-burst1..3.wav (AK-47), 44.1 kHz mono 16 bit.

  python3 artsrc/audio/make_rifle_sounds.py
"""
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "firearms", "work")
# output prefix -> (source recordings (clean single shots with long gaps), rounds, gap s, pitch, kept tail s)
# Burst weapons whose engine Burst fires several projectiles play the sound per shot, so they get single shots.
SETS = {
    "rifle-burst": (["AR-15-D_32P.wav"], 3, 0.080, 1.0, 0.9),     # Rifle Infantry, Union (PxTracer 3 rounds)
    "ak-burst": (["AK-47-C_28P.wav"], 3, 0.080, 1.0, 0.9),        # Rifle Infantry, Vanguard
    "vulcan-burst": (["AK-47-C_28P.wav"], 4, 0.060, 0.9, 0.9),    # garrisoned rifles (PxTracer 4 rounds)
    "mg-shot": (["AK-47-C_28P.wav", "AR-15-D_32P.wav"], 1, 0, 0.84, 0.6),  # M60mg (Burst 5): heavy single shots
    "chaingun-shot": (["AK-47-C_28P.wav"], 1, 0, 0.72, 0.5),     # helicopter / Yak chain guns
    "colt-shot": (["1911-A_42P.wav", "1911-A_34P.wav"], 1, 0, 1.0, 0.8),   # Tanya's Colt 45 (a real 1911)
    "pistol-shot": (["Walther_PPQ-X_31P.wav", "Walther_PPQ-X_39P.wav"], 1, 0, 1.0, 0.7),  # civilian pistols
    "sniper-shot": (["Tikka-W_29P.wav", "Tikka-W_24P.wav"], 1, 0, 1.0, 1.5),  # Sniper: bolt-action, long echo
}
OUT = os.path.join(HERE, "..", "..", "mods", "rapx", "audio", "weapons")
SR = 44100
SHOT_LEN = 1.6       # seconds cut per recorded shot (crack + tail); each set keeps its own tail


def load(path):
    w = wave.open(path)
    return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def shots(x):
    """Single shots cut at their onsets, each SHOT_LEN long with a short fade-out."""
    env = np.convolve(np.abs(x), np.ones(220) / 220, "same")
    thr = env.max() * 0.3
    out, i = [], 0
    while i < len(env):
        if env[i] > thr:
            start = max(0, i - int(0.004 * SR))
            s = x[start:start + int(SHOT_LEN * SR)].copy()
            fade = int(0.25 * SR)
            s[-fade:] *= np.linspace(1, 0, fade) ** 2
            out.append(s)
            i += int(0.5 * SR)
        else:
            i += 1
    return out


def repitch(s, factor):
    """Resample by factor (> 1 = higher and shorter)."""
    idx = np.arange(0, len(s) - 1, factor)
    return np.interp(idx, np.arange(len(s)), s).astype(np.float32)


def burst(rng, sources, rounds=3, gap=0.08, pitch=1.0, tail=0.9):
    total = np.zeros(int((gap * (rounds - 1) + tail + 0.1) * SR), np.float32)
    for r in range(rounds):
        s = repitch(sources[rng.integers(len(sources))], pitch * rng.uniform(0.96, 1.05))[:int(tail * SR)]
        fade = int(0.1 * SR)
        s[-fade:] *= np.linspace(1, 0, fade)
        s = s * rng.uniform(0.85, 1.0)
        # the earlier rounds' tails are cut short by the next round, like a real burst
        if r < rounds - 1:
            keep = int((gap + 0.06) * SR)
            s = s[:keep] * np.concatenate([np.ones(keep - int(0.03 * SR)), np.linspace(1, 0.3, int(0.03 * SR))])
        at = int(r * gap * SR)
        total[at:at + len(s)] += s[:len(total) - at]
    return total


def save(name, x):
    x = x / max(1e-6, np.abs(x).max()) * 0.8  # about -2 dB peak
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    print("wrote", name, f"{len(x) / SR:.2f}s")


if __name__ == "__main__":
    for prefix, (srcs, rounds, gap, pitch, tail) in SETS.items():
        sources = [shot for src in srcs for shot in shots(load(os.path.join(WORK, src)))]
        print(len(sources), "single shots for", prefix)
        rng = np.random.default_rng(7)
        for n in range(1, 4):
            save(f"{prefix}{n}.wav", burst(rng, sources, rounds, gap, pitch, tail))
