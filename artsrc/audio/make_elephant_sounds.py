#!/usr/bin/env python3
"""Sounds for the Elephanta (rules/vehicles.yaml ELPH, ElephantaVoice in audio/voices.yaml): real elephant calls
from CC0 recordings (sources: artsrc/audio/elephant/SOURCE.md), finished for the game, plus a mechanical stride.

  eleph-trumpet1-3  attack: the full trumpet blast, with a faint metal ring under it (a war machine, not a zoo)
  eleph-call1-3     select: short trumpets
  eleph-rumble1-2   move: the deep rumble elephants talk in, with a low engine growl
  eleph-steps       walking loop (AmbientSound while moving): heavy footfalls on the fore feet, lighter on the hind
                    ones, each a deep thud, a steel clank and a hydraulic hiss; one gait cycle per 0.8 s like the
                    walk animation (8 steps x 100 ms)

Writes Ogg Vorbis (ogg.py; never MP3) to mods/rapx/audio/elephant/.
"""
import os
import subprocess

import numpy as np
from scipy import signal

import make_sam_sounds as sam
from make_sam_sounds import RATE, band, env, high, low, noise, place, t_axis

HERE = os.path.dirname(os.path.abspath(__file__))
sam.OUT = os.path.join(HERE, '..', '..', 'mods', 'rapx', 'audio', 'elephant')
SRC = os.path.join(HERE, 'elephant', 'source', 'elephant-sound-effect.wav')
rng = np.random.default_rng(2207)


def load(path, start, end):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-to', str(end), '-i', path, '-ac', '1',
                          '-ar', str(RATE), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def fades(x, fade_in=0.01, fade_out=0.15):
    x = x.copy()
    a, b = int(fade_in * RATE), int(fade_out * RATE)
    x[:a] *= np.linspace(0, 1, a)
    x[-b:] *= np.linspace(1, 0, b) ** 2
    return x


def compress(x, drive=2.0):
    """Even out the level (soft saturation), so short calls carry as well as long ones."""
    x = x / max(np.max(np.abs(x)), 1e-9)
    return np.tanh(drive * x) / np.tanh(drive)


def metal(x, amount):
    """A faint metallic ring (comb filter): the call sounds as if from inside armour."""
    out = x.copy()
    for d, g in ((0.0041, 0.5), (0.0067, 0.35), (0.0093, 0.25)):
        i = int(d * RATE)
        out[i:] += g * x[:-i]
    return x * (1 - amount) + amount * high(out, 300)


def sub(x, f, amount):
    """Low body under a call, following its loudness."""
    e = low(np.abs(x), 12)
    t = np.arange(len(x)) / RATE
    return x + amount * np.sin(2 * np.pi * f * t) * e / max(e.max(), 1e-9)


def trumpet(start, end):
    x = high(load(SRC, start, end), 110)
    x = metal(compress(x, 1.8), 0.18)
    return fades(sub(x, 55, 0.25))


def rumble(start, end):
    x = low(high(load(SRC, start, end), 35), 900)
    x = compress(x, 2.5)
    t = np.arange(len(x)) / RATE
    engine = low(rng.standard_normal(len(x)), 120) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * t))
    return fades(x + 0.25 * engine / max(np.abs(engine).max(), 1e-9), 0.05, 0.4)


def footfall(weight):
    s = 0.36
    t = t_axis(s)
    x = np.zeros(len(t))
    thud = np.sin(2 * np.pi * np.cumsum(48 + 40 * np.exp(-t * 30)) / RATE) * env(t, 0.002, 0.07)
    place(x, thud, 0.0)
    clank = band(noise(0.12), 900, 4200) * env(t_axis(0.12), 0.0005, 0.018)
    ring = sum(np.sin(2 * np.pi * f * t_axis(0.2)) / i for i, f in enumerate((612, 1377, 2210), 1)) * env(t_axis(0.2), 0.001, 0.05)
    place(x, 0.35 * clank, 0.01)
    place(x, 0.12 * ring, 0.01)
    whine = np.sin(2 * np.pi * np.cumsum(np.linspace(420, 260, int(0.2 * RATE))) / RATE) * env(t_axis(0.2), 0.03, 0.06)
    place(x, 0.06 * whine, 0.06)
    hiss = band(noise(0.18), 2500, 8000) * env(t_axis(0.18), 0.01, 0.05)
    place(x, 0.12 * hiss, 0.12)
    return x * weight


def steps():
    cycle = 0.8
    n = int(2 * cycle * RATE)  # two cycles, so the loop does not sound mechanical
    x = np.zeros(n + int(0.4 * RATE))
    # lateral sequence walk: left hind, left fore, right hind, right fore, a quarter cycle apart (render_walk.py)
    for k in range(8):
        weight = (1.0 if k % 2 else 0.55) * rng.uniform(0.85, 1.0)
        place(x, footfall(weight), 0.005 + k * cycle / 4 + rng.uniform(0, 0.01))
    # wrap the tail of the last footfall to the start, so the loop is seamless
    x[:len(x) - n] += x[n:]
    return x[:n]


def save_loop(name, x, gain=0.8):
    """sam.save without its end fade, so the loop joins up."""
    import tempfile
    import wave
    from ogg import encode
    os.makedirs(sam.OUT, exist_ok=True)
    x = x / max(np.max(np.abs(x)), 1e-9) * gain
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        path = tmp.name
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
    encode(path, os.path.join(sam.OUT, name + '.ogg'))
    os.remove(path)
    print(f'{name}.ogg: {len(x) / RATE:.2f} s (loop)')


if __name__ == '__main__':
    # times (s) in elephant-sound-effect.wav, found from its spectrogram: clear harmonic trumpets and long rumbles
    for i, (a, b) in enumerate(((8.0, 10.5), (16.0, 19.0), (12.1, 14.2)), 1):
        sam.save(f'eleph-trumpet{i}', trumpet(a, b), 0.95)
    for i, (a, b) in enumerate(((20.0, 21.8), (121.6, 122.9), (135.1, 136.8)), 1):
        sam.save(f'eleph-call{i}', trumpet(a, b), 0.85)
    for i, (a, b) in enumerate(((62.0, 64.8), (70.4, 73.2)), 1):
        sam.save(f'eleph-rumble{i}', rumble(a, b), 0.9)
    save_loop('eleph-steps', steps())
