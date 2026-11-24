#!/usr/bin/env python3
"""Walking loop for the Spider Tank (rules/vehicles.yaml SPDR, AmbientSound while moving): quick metal feet.

  spider-steps  two touchdowns per gait cycle (render_walk.py spdr: legs in two groups of four, half a cycle apart),
                each four light steel ticks a few ms apart with a short knock under them, plus a servo whine as the
                lifted group swings; one cycle per 0.32 s like the walk animation (8 steps x 40 ms)

Writes Ogg Vorbis (ogg.py; never MP3) to mods/rapx/audio/spider/.
"""
import os

import numpy as np

import make_sam_sounds as sam
from make_elephant_sounds import save_loop
from make_sam_sounds import RATE, band, env, low, noise, place, t_axis

HERE = os.path.dirname(os.path.abspath(__file__))
sam.OUT = os.path.join(HERE, '..', '..', 'mods', 'rapx', 'audio', 'spider')
rng = np.random.default_rng(828)


def foot():
    """One foot: a bright steel tick and a small knock."""
    x = np.zeros(int(0.12 * RATE))
    tick = band(noise(0.05), 2200, 7000) * env(t_axis(0.05), 0.0003, 0.006)
    ring = np.sin(2 * np.pi * rng.uniform(1700, 2300) * t_axis(0.06)) * env(t_axis(0.06), 0.0005, 0.012)
    knock = low(noise(0.08), 350) * env(t_axis(0.08), 0.001, 0.02)
    place(x, 0.5 * tick, 0.0)
    place(x, 0.12 * ring, 0.0)
    place(x, 0.9 * knock, 0.0)
    return x


def servo(seconds):
    t = t_axis(seconds)
    f = np.linspace(780, 980, len(t))
    whine = np.sin(2 * np.pi * np.cumsum(f) / RATE) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / RATE)
    return whine * np.sin(np.pi * t / seconds) ** 2


def steps():
    cycle = 0.32
    n = int(4 * cycle * RATE)  # four cycles, so the loop does not sound mechanical
    x = np.zeros(n + int(0.2 * RATE))
    for k in range(8):  # a group of four lands every half cycle
        at = k * cycle / 2
        for _ in range(4):
            place(x, foot() * rng.uniform(0.6, 1.0), at + rng.uniform(0, 0.025))
        place(x, 0.04 * servo(cycle * 0.45), at + 0.02)
    x[:len(x) - n] += x[n:]  # wrap the tail round, so the loop is seamless
    return x[:n]


if __name__ == '__main__':
    save_loop('spider-steps', steps(), 0.7)
