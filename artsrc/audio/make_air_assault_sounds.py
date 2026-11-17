#!/usr/bin/env python3
"""Procedural sounds for helicopter air assaults (IDEA-47, PxAirAssault).

Writes mono Ogg Vorbis to mods/rapx/audio/sfx/:
  smokelaunch.ogg  a 40 mm smoke round leaving the helicopter's launcher: a hollow "thoonk" and a short whoosh
  ropezip.ogg      a soldier sliding down a fast rope: gloves rasping on braided nylon, braking at the bottom
  ropedrop.ogg     the released rope coil slapping onto the ground
No samples are used, so there is nothing to license. Re-run to tweak; the seed keeps it reproducible.
"""
import os
import sys
import tempfile
import wave

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ogg  # noqa: E402

RATE = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'mods', 'rapx', 'audio', 'sfx')
rng = np.random.default_rng(47)


def band(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype='band', fs=RATE, output='sos')
    return signal.sosfilt(sos, x)


def save(name, x):
    os.makedirs(OUT, exist_ok=True)
    x = x / max(np.max(np.abs(x)), 1e-9) * 0.9
    data = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        wav = tmp.name
    try:
        with wave.open(wav, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(data.tobytes())
        ogg.encode(wav, os.path.join(OUT, name))
    finally:
        os.remove(wav)
    print(f'{name}: {len(x) / RATE:.2f} s')


def smoke_launch():
    """Hollow tube pop (pitch drops fast), a bright crack of the propellant and the round whooshing away."""
    n = int(RATE * 0.7)
    t = np.arange(n) / RATE
    thoonk = np.sin(2 * np.pi * (95 + 140 * np.exp(-t * 30)) * t) * np.exp(-t * 18)
    body = band(rng.standard_normal(n), 180, 900) * np.exp(-t * 35) * 0.5
    crack = band(rng.standard_normal(n), 1500, 6000) * np.exp(-t * 160) * 0.35
    whoosh = band(rng.standard_normal(n), 600, 2600) * np.clip(t / 0.08, 0, 1) * np.exp(-np.maximum(t - 0.08, 0) * 7) * 0.22
    return thoonk + body + crack + whoosh


def rope_zip():
    """0.9 s of friction: a rasp whose pitch and loudness rise with speed, then the brake squeeze at the bottom."""
    n = int(RATE * 0.95)
    t = np.arange(n) / RATE
    speed = np.clip(t / 0.55, 0, 1) ** 1.4 * (1 - np.clip((t - 0.7) / 0.2, 0, 1))
    noise = rng.standard_normal(n)
    # Braided rope: the rasp is amplitude-modulated by the weave passing through the gloves
    weave = 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(25 + 90 * speed) / RATE)
    rasp = band(noise, 900, 4200) * weave * (0.25 + 0.75 * speed)
    low = band(noise, 150, 600) * speed * 0.5
    brake = band(rng.standard_normal(n), 400, 1600) * np.exp(-((t - 0.78) / 0.06) ** 2) * 0.9
    thud = np.sin(2 * np.pi * 70 * t) * np.exp(-np.maximum(t - 0.86, 0) * 30) * (t > 0.86) * 0.8
    return (rasp + low + brake + thud) * np.clip(t / 0.04, 0, 1)


def rope_drop():
    """A heavy coil of rope slapping down: several soft thumps close together and a dusty rustle."""
    n = int(RATE * 0.6)
    t = np.arange(n) / RATE
    x = np.zeros(n)
    for k, (at, amp) in enumerate(((0.0, 1.0), (0.06, 0.6), (0.11, 0.45), (0.19, 0.3))):
        tt = np.maximum(t - at, 0)
        x += (t >= at) * amp * (np.sin(2 * np.pi * (60 + 10 * k) * tt) * np.exp(-tt * 28)
                                + band(rng.standard_normal(n), 200, 1200) * np.exp(-tt * 45) * 0.6)
    rustle = band(rng.standard_normal(n), 1200, 5000) * np.exp(-t * 6) * 0.12
    return x + rustle


if __name__ == '__main__':
    save('smokelaunch.ogg', smoke_launch())
    save('ropezip.ogg', rope_zip())
    save('ropedrop.ogg', rope_drop())
