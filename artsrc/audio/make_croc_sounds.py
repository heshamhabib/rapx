#!/usr/bin/env python3
"""Procedural sounds for the Nile Crocodile (rules/infantry.yaml CROC, CrocVoice in audio/voices.yaml), modelled
on the real animal:

  croc-hiss1-2    select: the defensive hiss, a forced breathy exhale with a throaty rasp under it
  croc-growl1-2   move: a short low grunt (the "cough" crocodiles give on the move)
  croc-bellow1-2  attack: the territorial bellow, a deep rumbling roar with a sub-bass throb (crocodiles call
                  partly in infrasound: the water over their backs dances)
  croc-snap1-2    bite (weapon report): the jaws slam shut, a hard crack with a bony thud, and a splash
  croc-die1-2     death: a choked, fading hiss and a heavy thrash

Writes Ogg Vorbis (ogg.py; never MP3) to mods/rapx/audio/croc/. No samples are used, so there is nothing to
license. The seed keeps it reproducible.
"""
import os

import numpy as np

import make_sam_sounds as sam
from make_sam_sounds import RATE, band, env, high, low, noise, place, t_axis

sam.OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'mods', 'rapx', 'audio', 'croc')
rng = np.random.default_rng(1505)


def rough(t, rate, depth):
    """Irregular amplitude flutter (vocal folds / a throat rattling)."""
    jitter = np.cumsum(rng.normal(0, 0.02, len(t)))
    return 1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t + jitter))


def voiced(t, f0, harmonics, wobble=0.04):
    f = f0 * (1 + wobble * np.sin(2 * np.pi * 3.1 * t) + np.cumsum(rng.normal(0, 0.0004, len(t))))
    ph = 2 * np.pi * np.cumsum(f) / RATE
    return sum(np.sin(k * ph) / k ** 0.8 for k in range(1, harmonics + 1))


def hiss(pitch=1.0):
    s = 1.3
    t = t_axis(s)
    shape = env(t, 0.06, 0.55) * (1 - np.exp(-(s - t) / 0.08))
    air = band(noise(s), 1800 * pitch, 7500, 2) * 0.9 + band(noise(s), 500, 1800, 2) * 0.4
    rasp = band(noise(s) * rough(t, 38 * pitch, 0.8), 200, 900) * 0.5
    return (air + rasp) * shape


def growl(pitch=1.0):
    s = 0.7
    t = t_axis(s)
    shape = env(t, 0.03, 0.22)
    x = voiced(t, 62 * pitch, 14) * rough(t, 22, 0.7)
    x = low(x, 900) + 0.25 * band(noise(s), 150, 600) * rough(t, 22, 0.9)
    return x * shape


def bellow(pitch=1.0):
    s = 2.0
    t = t_axis(s)
    shape = env(t, 0.18, 0.9) * (1 - np.exp(-(s - t) / 0.2))
    roar = voiced(t, 48 * pitch, 18, 0.08) * rough(t, 15, 0.75)
    roar = np.tanh(2.2 * low(roar, 700))  # strained, gravelly
    sub = np.sin(2 * np.pi * 19 * pitch * t) * rough(t, 7, 0.4)  # the infrasound throb
    breath = band(noise(s), 300, 1400) * 0.2 * rough(t, 15, 0.8)
    return (roar + 0.7 * sub + breath) * shape


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
    fade = env(t, 0.05, 0.6)
    x = (band(noise(s), 900 * pitch, 5000, 2) * 0.6 + band(noise(s) * rough(t, 30, 0.9), 150, 700) * 0.5) * fade
    x *= 1 - 0.6 * smooth_step(t, 0.3, 1.4)
    place(x, splash(1.0, 1.0), 0.15)
    place(x, 0.6 * low(noise(0.25), 220) * env(t_axis(0.25), 0.005, 0.07), 0.2)  # body hitting the ground
    return x


def smooth_step(t, a, b):
    u = np.clip((t - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


if __name__ == '__main__':
    for i, p in enumerate((1.0, 0.88), 1):
        sam.save(f'croc-hiss{i}', hiss(p))
        sam.save(f'croc-growl{i}', growl(p))
        sam.save(f'croc-bellow{i}', bellow(p), 0.95)
        sam.save(f'croc-snap{i}', snap(p))
        sam.save(f'croc-die{i}', die(p))
