#!/usr/bin/env python3
"""
Aircraft engine sounds from free recordings (artsrc/audio/aircraft/source/, list and licences in SOURCE.md).
Writes mono 16-bit 22050 Hz WAVs to mods/rapx/audio/aircraft/, played by AmbientSound traits in rules/*.yaml:

  rotor.wav         attack / utility helicopter rotor, seamless loop
  rotor-heavy.wav   twin-rotor Chinook (also the V-22), seamless loop from a real CH-47 fly-over
  jet-engine.wav    jet engine, seamless loop (all jets, MiG, Badger, Spy Plane, An-225)
  jet-pass1-4.wav   the loud moment of real F-18 / F-15 / F-16 passes, one-shots played now and then by jets
  prop-engine.wav   propeller plane loop (Yak, MiG-3, La-11)
  drone-buzz.wav    small quadcopter buzz (Swarm drone): the helicopter loop pitched up
  airship.wav       slow deep engine drone (Zeppelin): the jet idle pitched down

AmbientSound has no volume setting, so the levels are set here (LOOP_DB / PASS_DB in main): loud enough to
carry over the game music (at -28 dB they were barely audible), with a soft limiter against clipping. Needs ffmpeg.
"""

import os
import subprocess
import wave

import numpy as np
from scipy import signal

RATE = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "aircraft", "source")
OUT = os.path.join(HERE, "..", "..", "mods", "rapx", "audio", "aircraft")


def load(name, rate=RATE):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(SRC, name), "-ac", "1", "-ar", str(rate),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def rms_env(x, win=0.25):
    n = int(win * RATE)
    k = len(x) // n
    return np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1) + 1e-12), n


def steady(x, seconds):
    """Start of the loudest stretch whose level varies least (the aircraft overhead, holding steady)."""
    env, n = rms_env(x)
    w = int(seconds * RATE / n)
    best, start = None, 0
    for i in range(len(env) - w):
        seg = env[i:i + w]
        score = seg.mean() / (1 + 4 * seg.std() / seg.mean())
        if best is None or score > best:
            best, start = score, i
    return start * n


def loop(x, seconds, fade=0.6, start=None):
    """A seamless loop: the stretch plus a crossfade of its tail into its head."""
    s = steady(x, seconds + fade) if start is None else start
    n, f = int(seconds * RATE), int(fade * RATE)
    seg = x[s:s + n + f].copy()
    ramp = np.linspace(0, 1, f)
    seg[:f] = seg[:f] * ramp + seg[n:n + f] * (1 - ramp)
    return seg[:n]


def peak_pass(x, before=2.2, after=2.0):
    """The loud moment of a fly-by, faded in and out."""
    env, n = rms_env(x, 0.1)
    p = int(np.argmax(env)) * n
    seg = x[max(0, p - int(before * RATE)):p + int(after * RATE)].copy()
    fi, fo = int(0.5 * RATE), int(1.0 * RATE)
    seg[:fi] *= np.linspace(0, 1, fi)
    seg[-fo:] *= np.linspace(1, 0, fo) ** 2
    return seg


def pitch(x, factor):
    """Resample: factor > 1 raises the pitch (and shortens), < 1 lowers it."""
    return signal.resample(x, int(len(x) / factor))


def highpass(x, hz):
    return signal.sosfilt(signal.butter(2, hz, btype="high", fs=RATE, output="sos"), x)


def level(x, rms_db, peak_db=-1.0):
    x = x - x.mean()
    x = x * 10 ** (rms_db / 20) / np.sqrt((x ** 2).mean())
    peak = np.abs(x).max()
    limit = 10 ** (peak_db / 20)
    if peak > limit:  # soft limit the odd spike instead of lowering the whole sound
        x = np.tanh(x / limit) * limit
    return x


def save(name, x):
    os.makedirs(OUT, exist_ok=True)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"{name:18s} {len(x) / RATE:5.2f} s")


def main():
    LOOP_DB, PASS_DB = -17, -11

    # Light rotor: a designed loop (qubodup) laid over the steady part of a real hovering police helicopter
    designed = load("fs187678-helicopter-loop.mp3")
    designed = loop(designed, len(designed) / RATE - 0.5, fade=0.4, start=0)
    hover = loop(highpass(load("fs454052-heli-hover.mp3"), 60), len(designed) / RATE)
    save("rotor.wav", level(designed / np.abs(designed).max() + 0.35 * hover / np.abs(hover).max(), LOOP_DB))

    # Heavy rotor: the CH-47 over Greenwich, held where it is loudest and steadiest
    save("rotor-heavy.wav", level(loop(highpass(load("wm-chinook-greenwich.ogg"), 40), 6.0), LOOP_DB + 1))

    # Jet engine loop
    save("jet-engine.wav", level(loop(highpass(load("fs269064-jet-loop.mp3"), 50), 8.0), LOOP_DB))

    # Jet passes
    for i, name in enumerate(["fs135495-f18-pass01.mp3", "fs135496-f18-pass02.mp3", "fs324370-f15-flyover.mp3",
                              "fs343747-f16-flyby.mp3"], 1):
        save(f"jet-pass{i}.wav", level(peak_pass(highpass(load(name), 40)), PASS_DB))

    # Propeller planes
    save("prop-engine.wav", level(loop(load("oga-airplane-prop-antumdeluge.ogg"), 4.0, fade=0.4), LOOP_DB))

    # Swarm drone: the designed rotor loop, two and a half times faster
    buzz = pitch(load("fs187678-helicopter-loop.mp3"), 2.5)
    save("drone-buzz.wav", level(loop(buzz, len(buzz) / RATE - 0.3, fade=0.2, start=0), LOOP_DB - 3))

    # Zeppelin: F-22 idle an octave down, a slow heavy drone
    drone = pitch(load("fs187734-f22-idle.mp3"), 0.5)
    save("airship.wav", level(loop(drone, 8.0), LOOP_DB + 1))


if __name__ == "__main__":
    main()
