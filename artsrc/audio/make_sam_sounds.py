#!/usr/bin/env python3
"""Procedural sounds for the mobile SAM launchers (rules/mobile-sam.yaml), each system with its own voice:

  gurz-launch1-3   Gurz Mace: a sharp ignition crack and a fast, hissing whoosh (small fast missiles in a ripple)
  gurz-cannon1-2   Gurz Mace: a pair of heavy 35 mm thumps
  gurz-burst1-3    Gurz Mace: proximity-fuse airburst, a hard crack with a short boom
  meads-launch1-2  Aegis Lance: cold launch (a deep gas thump), then the motor lights with a rising roar
  meads-hit1-2     Aegis Lance: hit-to-kill, a metallic clang and crack with a rolling tail
  spyder-launch1-2 Spyder Talon: dual-pulse motor, a roar, a short silence, a pop and a second roar
  spyder-blast1-2  Spyder Talon: a big fireball boom with crackling debris

Writes Ogg Vorbis (ogg.py; never MP3) to mods/rapx/audio/weapons/sam/. No samples are used, so there is nothing to
license. The seed keeps it reproducible.
"""
import os
import tempfile
import wave

import numpy as np
from scipy import signal

from ogg import encode

RATE = 44100
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'mods', 'rapx', 'audio', 'weapons', 'sam')
rng = np.random.default_rng(1150)


def t_axis(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def noise(seconds):
    return rng.standard_normal(int(seconds * RATE))


def band(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype='band', fs=RATE, output='sos')
    return signal.sosfilt(sos, x)


def low(x, hi, order=4):
    return signal.sosfilt(signal.butter(order, hi, btype='low', fs=RATE, output='sos'), x)


def high(x, lo, order=4):
    return signal.sosfilt(signal.butter(order, lo, btype='high', fs=RATE, output='sos'), x)


def sweep_band(x, lo0, lo1, width):
    """Band-pass whose centre glides from lo0 to lo1 (a passing whoosh), processed in short blocks."""
    out = np.zeros_like(x)
    block = 1024
    n = len(x)
    zi = None
    for i in range(0, n, block):
        f = lo0 + (lo1 - lo0) * (i / max(1, n))
        sos = signal.butter(2, [max(40, f), min(RATE / 2 - 100, f * width)], btype='band', fs=RATE, output='sos')
        if zi is None:
            zi = signal.sosfilt_zi(sos) * 0
        out[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return out


def env(t, attack, decay):
    return (1 - np.exp(-t / max(attack, 1e-4))) * np.exp(-t / decay)


def place(dst, src, at):
    i = int(at * RATE)
    n = min(len(src), len(dst) - i)
    dst[i:i + n] += src[:n]


def crackle(seconds, rate, decay):
    """Random sharp ticks (burning propellant, hot debris)."""
    x = np.zeros(int(seconds * RATE))
    t = t_axis(seconds)
    for at in np.sort(rng.uniform(0, seconds, int(seconds * rate))):
        i = int(at * RATE)
        k = rng.uniform(0.3, 1) * np.exp(-at / decay)
        click = band(rng.standard_normal(200), 1500, 7000) * np.exp(-np.arange(200) / 25)
        x[i:i + 200] += k * click[:len(x) - i]
    return x * (t >= 0)


def boom(seconds, f0, f1, decay):
    t = t_axis(seconds)
    f = f1 + (f0 - f1) * np.exp(-t * 18)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * env(t, 0.003, decay)


def stereo_room(x, wet=0.18):
    """A little early reflection so the effects sit in the world rather than in the speaker."""
    out = x.copy()
    for d, g in ((0.031, 0.5), (0.047, 0.35), (0.083, 0.25), (0.121, 0.15)):
        i = int(d * RATE)
        out[i:] += wet * g * x[:-i]
    return out


def save(name, x, gain=0.9):
    os.makedirs(OUT, exist_ok=True)
    x = stereo_room(x)
    fade = int(0.02 * RATE)
    x[-fade:] *= np.linspace(1, 0, fade)
    x = x / max(np.max(np.abs(x)), 1e-9) * gain
    data = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        path = tmp.name
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    encode(path, os.path.join(OUT, name + '.ogg'))
    os.remove(path)
    print(f'{name}.ogg: {len(x) / RATE:.2f} s')


# --- Gurz Mace -------------------------------------------------------------------------------------------------

def gurz_launch(pitch):
    s = 1.3
    t = t_axis(s)
    x = np.zeros(len(t))
    # Ignition crack and the tube's thump
    place(x, 1.2 * band(noise(0.08), 1200, 9000) * env(t_axis(0.08), 0.0005, 0.012), 0)
    place(x, 0.8 * boom(0.25, 160 * pitch, 70, 0.05), 0)
    # Fast hissing whoosh that falls in pitch as the missile streaks away
    w = sweep_band(noise(s), 3800 * pitch, 900 * pitch, 2.4) * env(t, 0.015, 0.38)
    roar = low(noise(s), 900) * env(t, 0.01, 0.22)
    x += 1.4 * w + 0.6 * roar
    x += 0.25 * crackle(s, 40, 0.3)
    return x


def gurz_cannon():
    s = 0.7
    x = np.zeros(int(s * RATE))
    for at in (0, rng.uniform(0.11, 0.14)):
        shot = boom(0.4, 220, 55, 0.07) + 0.7 * band(noise(0.4), 500, 4000) * env(t_axis(0.4), 0.001, 0.025)
        shot += 0.4 * low(noise(0.4), 300) * env(t_axis(0.4), 0.002, 0.12)
        place(x, shot, at)
    return x


def gurz_burst():
    s = 1.0
    t = t_axis(s)
    x = 1.3 * band(noise(s), 1500, 10000) * env(t, 0.0003, 0.01)
    x += 0.9 * boom(s, 140, 48, 0.12)
    x += 0.5 * low(noise(s), 700) * env(t, 0.003, 0.18)
    x += 0.2 * crackle(s, 30, 0.25)
    return x


# --- Aegis Lance (MEADS) ----------------------------------------------------------------------------------------

def meads_launch(pitch):
    s = 3.2
    t = t_axis(s)
    x = np.zeros(len(t))
    # Cold launch: a deep gas thump and a puff of hiss as the canister cover blows
    place(x, 1.3 * boom(0.6, 90 * pitch, 38, 0.14), 0)
    place(x, 0.6 * band(noise(0.5), 300, 2500) * env(t_axis(0.5), 0.002, 0.09), 0)
    # Motor ignition 0.32 s later: a bang, then a swelling roar that fades as the missile climbs away
    ign = 0.32
    tr = t_axis(s - ign)
    place(x, 0.9 * band(noise(0.1), 800, 8000) * env(t_axis(0.1), 0.0005, 0.02), ign)
    roar = low(noise(s - ign), 1400) * env(tr, 0.12, 1.1) + 0.35 * sweep_band(noise(s - ign), 2200 * pitch, 500, 2.0) * env(tr, 0.05, 0.9)
    rumble = low(noise(s - ign), 120) * env(tr, 0.2, 1.3)
    place(x, 1.1 * roar + 1.6 * rumble, ign)
    place(x, 0.3 * crackle(s - ign, 60, 0.8), ign)
    return x


def meads_hit(pitch):
    s = 2.0
    t = t_axis(s)
    # Metallic clang: inharmonic partials ringing out fast
    clang = sum(a * np.sin(2 * np.pi * f * pitch * t + rng.uniform(0, 6)) * np.exp(-t / d)
                for f, a, d in ((610, 1, 0.09), (1043, 0.7, 0.07), (1677, 0.5, 0.05), (2391, 0.35, 0.04), (3310, 0.2, 0.03)))
    x = 0.8 * clang
    x += 1.4 * band(noise(s), 2000, 12000) * env(t, 0.0002, 0.006)
    x += 0.9 * boom(s, 120, 40, 0.18)
    x += 0.6 * low(noise(s), 400) * env(t, 0.01, 0.55)
    x += 0.25 * crackle(s, 50, 0.4)
    return x


# --- Spyder Talon ------------------------------------------------------------------------------------------------

def spyder_launch(pitch):
    s = 2.3
    x = np.zeros(int(s * RATE))
    # First pulse: off the rail with a punchy roar
    p1 = 0.75
    t1 = t_axis(p1)
    place(x, 1.0 * band(noise(0.08), 900, 8000) * env(t_axis(0.08), 0.0005, 0.015), 0)
    first = low(noise(p1), 1800) * env(t1, 0.02, 0.35) + 0.6 * sweep_band(noise(p1), 2600 * pitch, 1100 * pitch, 2.2) * env(t1, 0.01, 0.3)
    place(x, 1.2 * first, 0)
    # Coast, then the second pulse lights: a pop and a thinner, more distant roar
    at = 1.05
    p2 = s - at
    t2 = t_axis(p2)
    place(x, 0.7 * band(noise(0.06), 1500, 9000) * env(t_axis(0.06), 0.0005, 0.01), at)
    second = band(noise(p2), 400, 3500) * env(t2, 0.03, 0.4) + 0.5 * sweep_band(noise(p2), 3200 * pitch, 900, 2.0) * env(t2, 0.02, 0.35)
    place(x, 0.75 * second, at)
    return x


def spyder_blast(pitch):
    s = 2.6
    t = t_axis(s)
    x = 1.6 * boom(s, 100 * pitch, 32, 0.32)
    x += 1.0 * low(noise(s), 900) * env(t, 0.004, 0.35)
    x += 0.7 * band(noise(s), 900, 7000) * env(t, 0.0005, 0.03)
    x += 0.7 * low(noise(s), 160) * env(t, 0.05, 0.9)
    x += 0.35 * crackle(s, 45, 0.9)
    return x


if __name__ == '__main__':
    for i, p in enumerate((1.0, 0.92, 1.08), 1):
        save(f'gurz-launch{i}', gurz_launch(p))
        save(f'gurz-burst{i}', gurz_burst())
    for i in (1, 2):
        save(f'gurz-cannon{i}', gurz_cannon())
    for i, p in enumerate((1.0, 0.9), 1):
        save(f'meads-launch{i}', meads_launch(p))
        save(f'meads-hit{i}', meads_hit(p))
        save(f'spyder-launch{i}', spyder_launch(p))
        save(f'spyder-blast{i}', spyder_blast(p))
