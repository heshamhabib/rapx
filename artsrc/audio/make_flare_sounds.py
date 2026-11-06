#!/usr/bin/env python3
"""Procedural countermeasure-flare sounds for PxFlareDispenser (jets dropping flares at incoming missiles).

Writes mono 16-bit 22050 Hz WAVs to mods/rapx/audio/aircraft/flares1-3.wav: a rapid string of ejection pops (one per
flare, about a game tick apart) over the hiss of burning magnesium. No samples are used, so there is nothing to
license. Re-run to tweak; the seed keeps it reproducible.
"""
import os
import wave

import numpy as np
from scipy import signal

RATE = 22050
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'mods', 'rapx', 'audio', 'aircraft')
rng = np.random.default_rng(31)


def band(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype='band', fs=RATE, output='sos')
    return signal.sosfilt(sos, x)


def save(name, x):
    os.makedirs(OUT, exist_ok=True)
    x = x / max(np.max(np.abs(x)), 1e-9) * 0.9
    data = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(os.path.join(OUT, name), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    print(f'{name}: {len(x) / RATE:.2f} s')


def pop(n):
    """One flare punched out of its cartridge: a dull thump and a sharp crack."""
    t = np.arange(n) / RATE
    thump = np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 40)) * t) * np.exp(-t * 45)
    crack = band(rng.standard_normal(n), 900, 5000) * np.exp(-t * 120)
    return 0.8 * thump + 0.9 * crack


def flares(count, gap, seconds):
    n = int(seconds * RATE)
    out = np.zeros(n)
    p = int(0.12 * RATE)
    for i in range(count):
        at = int((0.02 + i * gap * rng.uniform(0.8, 1.2)) * RATE)
        if at + p < n:
            out[at:at + p] += pop(p) * rng.uniform(0.6, 1.0)

    # Burning flares: a fizzing hiss that swells with each flare and fades as they fall away
    t = np.arange(n) / RATE
    fizz = band(rng.standard_normal(n), 2500, 8000) * (0.6 + 0.4 * rng.standard_normal(n).clip(-1, 1))
    crackle = band((rng.random(n) > 0.997) * rng.standard_normal(n), 1500, 6000) * 3
    swell = np.clip(t / (count * gap + 0.05), 0, 1) * np.exp(-np.clip(t - count * gap, 0, None) * 2.2)
    return out + (0.35 * fizz + 0.5 * crackle) * swell


if __name__ == '__main__':
    save('flares1.wav', flares(12, 0.04, 1.8))
    save('flares2.wav', flares(10, 0.05, 1.8))
    save('flares3.wav', flares(14, 0.035, 1.8))
