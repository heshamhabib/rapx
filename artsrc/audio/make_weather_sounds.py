#!/usr/bin/env python3
"""Procedural weather ambience for IDEA-20 (PxWeatherManager).

Writes mono 16-bit 22050 Hz WAVs to mods/rapx/audio/weather/:
  rain.wav, rain-heavy.wav, wind.wav, sand.wav  - seamless loops (crossfaded ends)
  thunder1-3.wav                                 - one-shots: crack + rolling rumble
No samples are used, so there is nothing to license. Re-run to tweak; the seed keeps it reproducible.
"""
import os
import wave

import numpy as np
from scipy import signal

RATE = 22050
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'mods', 'rapx', 'audio', 'weather')
rng = np.random.default_rng(20)


def band(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype='band', fs=RATE, output='sos')
    return signal.sosfilt(sos, x)


def lowpass(x, hi, order=4):
    return signal.sosfilt(signal.butter(order, hi, fs=RATE, output='sos'), x)


def highpass(x, lo, order=4):
    return signal.sosfilt(signal.butter(order, lo, btype='high', fs=RATE, output='sos'), x)


def slow(n, period, depth, smooth=4):
    """Random slow modulation in [1-depth, 1]."""
    k = max(4, int(n / RATE / period * smooth))
    pts = rng.random(k + 3)
    curve = signal.resample(pts, n + n // k * 3)[:n]
    curve = (curve - curve.min()) / max(np.ptp(curve), 1e-9)
    return 1 - depth + depth * curve


def drops(n, rate, lo, hi, decay_ms):
    """Random droplet ticks: short filtered noise bursts."""
    out = np.zeros(n)
    count = int(n / RATE * rate)
    length = int(RATE * decay_ms / 1000 * 5)
    env = np.exp(-np.arange(length) / (RATE * decay_ms / 1000))
    for _ in range(count):
        at = rng.integers(0, n - length)
        burst = rng.standard_normal(length) * env * rng.uniform(0.2, 1.0) ** 2
        out[at:at + length] += burst
    return band(out, lo, hi, 2)


def loop(x, fade_s=1.5):
    """Crossfade the tail into the head so the sound loops without a seam."""
    f = int(fade_s * RATE)
    head, tail = x[:f], x[-f:]
    t = np.linspace(0, 1, f)
    mixed = tail * np.cos(t * np.pi / 2) + head * np.sin(t * np.pi / 2)
    return np.concatenate([mixed, x[f:-f]])


def normalize(x, peak):
    return x / max(np.max(np.abs(x)), 1e-9) * peak


def save(name, x):
    os.makedirs(OUT, exist_ok=True)
    data = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(os.path.join(OUT, name), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    print(f'{name}: {len(x) / RATE:.1f} s')


def rain(seconds, heavy):
    n = int((seconds + 1.5) * RATE)
    white = rng.standard_normal(n)
    hiss = band(white, 900, 9000) * slow(n, 3, 0.25)
    body = band(white, 250, 1800) * (0.6 if heavy else 0.3) * slow(n, 5, 0.4)
    ticks = drops(n, 900 if heavy else 380, 1500, 9500, 1.2) * (1.4 if heavy else 1.0)
    big = drops(n, 60 if heavy else 25, 300, 2500, 6) * 0.8
    x = hiss + body + ticks + big
    if heavy:
        rumble = lowpass(rng.standard_normal(n), 160) * 3.0 * slow(n, 4, 0.6)
        x += rumble
    return normalize(loop(x), 0.8 if heavy else 0.6)


def wind(seconds, sand=False):
    n = int((seconds + 1.5) * RATE)
    white = rng.standard_normal(n)
    x = np.zeros(n)

    # Overlapping resonances with their own gusts give a moving, howling timbre
    for lo, hi, g in [(90, 220, 1.0), (180, 420, 0.9), (350, 800, 0.55), (700, 1500, 0.3)]:
        x += band(white, lo, hi, 2) * g * slow(n, rng.uniform(2.5, 6), 0.85) ** 2
    x *= slow(n, 7, 0.5)
    if sand:
        grains = drops(n, 2500, 3000, 10000, 0.4) * 0.6
        hiss = band(white, 2500, 10000) * 0.35 * slow(n, 3, 0.5)
        x = x * 0.7 + (grains + hiss) * slow(n, 4, 0.6)
    return normalize(loop(x), 0.75)


def thunder(seconds, crack, rolls):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    x = np.zeros(n)

    # Sharp crack at the start (close strikes)
    if crack > 0:
        length = int(0.35 * RATE)
        burst = rng.standard_normal(length) * np.exp(-np.arange(length) / (0.06 * RATE))
        x[:length] += highpass(burst, 600) * crack

    # Rolling rumble: several low bursts arriving later and later, each fading
    brown = np.cumsum(rng.standard_normal(n))
    brown = highpass(brown - np.mean(brown), 25)
    brown = lowpass(brown, 220)
    brown /= np.max(np.abs(brown))
    env = np.zeros(n)
    for i in range(rolls):
        at = 0.05 + i * rng.uniform(0.3, 0.9)
        width = rng.uniform(0.6, 1.6)
        env += rng.uniform(0.5, 1.0) * np.exp(-np.clip(t - at, 0, None) / width) * (t >= at) * (1 - np.exp(-np.clip(t - at, 0, None) / 0.06))
    mid = band(rng.standard_normal(n), 80, 600) * 0.25
    x += (brown + mid) * env
    x *= np.minimum(1, (seconds - t) / 0.8)  # fade out
    return normalize(x, 0.95)


if __name__ == '__main__':
    save('rain.wav', rain(10, heavy=False))
    save('rain-heavy.wav', rain(10, heavy=True))
    save('wind.wav', wind(14))
    save('sand.wav', wind(12, sand=True))
    save('thunder1.wav', thunder(7.0, crack=1.0, rolls=5))
    save('thunder2.wav', thunder(8.0, crack=0.4, rolls=7))
    save('thunder3.wav', thunder(6.0, crack=0.0, rolls=4))
