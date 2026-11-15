#!/usr/bin/env python3
"""Sounds for the Nile Crocodile (rules/infantry.yaml CROC, CrocVoice in audio/voices.yaml). The calls are real
American alligator recordings (public domain, sources: artsrc/audio/croc/SOURCE.md; the crocodile's close cousin
makes the same calls), cleaned of the insects and birds behind them and given weight; the bite is procedural.

  croc-hiss1-2    select: the real defensive hiss, with a clean breathy layer on top (the recording's highs are
                  full of birdsong, so they are cut and replaced)
  croc-growl1-2   move: the start of a bellow, a short low grunt
  croc-bellow1-2  attack: the full territorial bellow, with a sub-bass throb under it (crocodilians call partly in
                  infrasound: the water over their backs dances)
  croc-snap1-2    bite (weapon report): the jaws slam shut, a hard crack with a bony thud, and a splash
  croc-die1-2     death: a fading real hiss, a splash and a heavy thrash

Writes Ogg Vorbis (ogg.py; never MP3) to mods/rapx/audio/croc/. The seed keeps it reproducible.
"""
import os

import numpy as np

from make_elephant_sounds import compress, fades, load

import make_sam_sounds as sam
from make_sam_sounds import RATE, band, env, high, low, noise, place, t_axis

sam.OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'mods', 'rapx', 'audio', 'croc')
rng = np.random.default_rng(1505)
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'croc', 'source')


def clean(x, top=1400):
    """The recordings' calls live below ~1.4 kHz; insects and birds above it go."""
    return low(high(x, 28), top, 6)


def real_bellow(file, start, end, pitch=1.0):
    x = compress(clean(load(os.path.join(SRC, file), start, end)), 2.2)
    t = np.arange(len(x)) / RATE
    e = low(np.abs(x), 10)
    throb = np.sin(2 * np.pi * 21 * pitch * t) * e / max(e.max(), 1e-9)
    return fades(x + 0.45 * throb, 0.03, 0.3)


def real_hiss(pitch=1.0, seconds=None):
    x = band(load(os.path.join(SRC, 'alligatorhiss.ogg'), 4.8, 7.6), 200, 1300, 6)
    x = compress(x, 1.6)
    air = hiss(pitch)[:len(x)]
    air = high(air, 1300)
    x = 0.8 * x[:len(air)] + 0.7 * air / max(np.abs(air).max(), 1e-9)
    if seconds:
        x = x[:int(seconds * RATE)]
    return fades(x, 0.04, 0.35)


def rough(t, rate, depth):
    """Irregular amplitude flutter (vocal folds / a throat rattling)."""
    jitter = np.cumsum(rng.normal(0, 0.02, len(t)))
    return 1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t + jitter))


def hiss(pitch=1.0):
    s = 1.3
    t = t_axis(s)
    shape = env(t, 0.06, 0.55) * (1 - np.exp(-(s - t) / 0.08))
    air = band(noise(s), 1800 * pitch, 7500, 2) * 0.9 + band(noise(s), 500, 1800, 2) * 0.4
    rasp = band(noise(s) * rough(t, 38 * pitch, 0.8), 200, 900) * 0.5
    return (air + rasp) * shape


def splash(s, amount):
    t = t_axis(s)
    x = band(noise(s), 400, 5000) * env(t, 0.005, 0.12) * 0.8
    for at in np.sort(rng.uniform(0.02, s * 0.6, int(14 * amount))):  # droplets
        d = t_axis(0.03)
        place(x, np.sin(2 * np.pi * rng.uniform(900, 2600) * d) * env(d, 0.001, 0.008) * rng.uniform(0.1, 0.35), at)
    return x * amount


def snap(pitch=1.0):
    s = 0.8
    t = t_axis(s)
    x = np.zeros(len(t))
    crack = high(noise(0.05), 1500) * env(t_axis(0.05), 0.0004, 0.006)
    thud = np.sin(2 * np.pi * 140 * pitch * t_axis(0.18)) * env(t_axis(0.18), 0.001, 0.045)
    place(x, 1.2 * crack, 0.0)
    place(x, 0.9 * thud, 0.002)
    place(x, 0.5 * band(noise(0.08), 200, 1200) * env(t_axis(0.08), 0.001, 0.02), 0.004)  # teeth on bone
    place(x, splash(0.6, 0.6), 0.05)
    return x


def die(pitch=1.0):
    s = 1.8
    t = t_axis(s)
    x = np.zeros(len(t))
    h = real_hiss(pitch, 1.6)
    place(x, h * (1 - 0.8 * smooth_step(t_axis(len(h) / RATE), 0.2, 1.5)), 0.0)
    place(x, splash(1.0, 1.0), 0.15)
    place(x, 0.6 * low(noise(0.25), 220) * env(t_axis(0.25), 0.005, 0.07), 0.2)  # body hitting the ground
    return x


def smooth_step(t, a, b):
    u = np.clip((t - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


if __name__ == '__main__':
    # bellow pulses (s) in the recordings, found from their loudness and spectrograms
    sam.save('croc-bellow1', real_bellow('27alligator2bellow.ogg', 0.7, 2.7), 0.95)
    sam.save('croc-bellow2', real_bellow('alligatorbellowedit.ogg', 6.8, 9.6), 0.95)
    sam.save('croc-growl1', real_bellow('27alligator2bellow.ogg', 4.8, 5.7), 0.85)
    sam.save('croc-growl2', real_bellow('27alligator2bellow.ogg', 8.9, 9.8), 0.85)
    for i, p in enumerate((1.0, 0.88), 1):
        sam.save(f'croc-hiss{i}', real_hiss(p))
        sam.save(f'croc-snap{i}', snap(p))
        sam.save(f'croc-die{i}', die(p))
