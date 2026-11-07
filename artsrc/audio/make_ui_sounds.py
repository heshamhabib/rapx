#!/usr/bin/env python3
"""
Synthesises the 15 interface sounds (IDEA-31) that still came from the original game: menu click, chat beep, power
and lobby bleeps, alerts, map beacon ping, radar on/off sweeps, credit ticks and the promotion chime. Same names as
the originals (audio/notifications.yaml `Sounds:`), written to mods/rapx/audio/ui/<name>.ogg.

  python3 artsrc/audio/make_ui_sounds.py
"""
import os
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ogg  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mods", "rapx", "audio", "ui")
SR = 44100
rng = np.random.default_rng(31)


def t_of(dur):
    return np.arange(int(dur * SR)) / SR


def env(t, attack=0.003, decay=10.0):
    return np.minimum(1, t / attack) * np.exp(-t * decay)


def tone(freq, dur, decay=10.0, attack=0.003, harm=0.0):
    """Sine (or a sweep when freq is an array) with an optional soft odd harmonic for a digital edge."""
    t = t_of(dur)
    f = np.broadcast_to(freq, t.shape) if np.ndim(freq) else np.full(t.shape, float(freq))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + harm * np.sin(3 * ph) / 3
    return x * env(t, attack, decay)


def gap(dur):
    return np.zeros(int(dur * SR))


def echo(x, taps):
    out = np.zeros(len(x) + int(max(d for d, _ in taps) * SR))
    out[:len(x)] += x
    for d, g in taps:
        out[int(d * SR):int(d * SR) + len(x)] += x * g
    return out


def static(dur, level):
    n = rng.normal(0, 1, int(dur * SR))
    return np.convolve(n, np.ones(3) / 3, "same") * level


def sweep(f0, f1, dur, curve=1.0):
    k = np.linspace(0, 1, int(dur * SR)) ** curve
    return f0 + (f1 - f0) * k


def sounds():
    s = {}
    # Menu click: tiny noise transient plus a high ping
    t = t_of(0.035)
    s["ramenu1"] = tone(2400, 0.035, decay=120) * 0.8 + static(0.035, 0.5) * np.exp(-t * 400)
    # Chat line: soft two-tone digital beep
    s["rabeep1"] = np.concatenate([tone(880, 0.07, decay=30), gap(0.015), tone(1320, 0.09, decay=25)]) * 0.7
    # Rising bleep (power, player joined) and falling bleep (power, player left)
    s["bleep11"] = tone(sweep(600, 1250, 0.14), 0.14, decay=8, harm=0.5) * 0.7
    s["bleep12"] = tone(sweep(1250, 600, 0.14), 0.14, decay=8, harm=0.5) * 0.7
    # Lobby option changed: very short soft tick
    s["bleep17"] = tone(1800, 0.03, decay=140) * 0.6
    # Base setup: double confirmation bleep
    b = tone(1050, 0.07, decay=22, harm=0.4)
    s["bleep9"] = np.concatenate([b, gap(0.035), b]) * 0.7
    # Alert: three quick urgent bleeps
    a = tone(1450, 0.055, decay=18, attack=0.002, harm=0.6)
    s["bleep6"] = np.concatenate([a, gap(0.03), a, gap(0.03), a]) * 0.75
    # Angry bleep: low digital "denied" buzz
    t = t_of(0.22)
    sq = np.sign(np.sin(2 * np.pi * 165 * t)) * 0.5 + np.sign(np.sin(2 * np.pi * 247 * t)) * 0.3
    s["bleep5"] = np.convolve(sq, np.ones(8) / 8, "same") * np.minimum(1, t / 0.005) * np.minimum(1, (0.22 - t) / 0.03)
    # Alert buzzer: harsh pulsing alarm
    t = t_of(0.6)
    saw = 2 * ((110 * t) % 1) - 1 + 0.6 * (2 * ((165 * t) % 1) - 1)
    am = 0.6 + 0.4 * (np.sin(2 * np.pi * 12 * t) > 0)
    s["buzzy1"] = np.convolve(saw, np.ones(5) / 5, "same") * am * np.minimum(1, t / 0.01) * np.minimum(1, (0.6 - t) / 0.05) * 0.5
    # Map beacon: bright radar ping with echo
    s["beepslct"] = echo(tone(1500, 0.35, decay=9) * 0.8, [(0.12, 0.35), (0.24, 0.15)])
    # Radar online (radar built, minimap appears): a monitor powering on. Soft relay click and mains hum, a gentle
    # rising tone that settles, then two clean radar pings with an echo; only a whisper of static (user, 2026-11-07:
    # the old long sweep with loud fizz was replaced)
    t = t_of(1.6)
    click = tone(900, 0.02, decay=200, attack=0.0005) * 0.6
    hum = (np.sin(2 * np.pi * 60 * t) + 0.5 * np.sin(2 * np.pi * 120 * t)) * np.minimum(1, t / 0.08) \
        * np.exp(-t * 2.2) * 0.25
    rise = tone(sweep(220, 520, 0.6, 0.5), 0.6, decay=3.5, attack=0.06) * 0.35
    ping = tone(1320, 0.3, decay=11) * 0.55 + tone(2640, 0.3, decay=22) * 0.12
    x = np.zeros(len(t))
    x[:len(hum)] += hum
    x[:len(click)] += click
    x[int(0.04 * SR):int(0.04 * SR) + len(rise)] += rise
    for at in (0.55, 0.95):
        x[int(at * SR):int(at * SR) + len(ping)] += ping
    x = echo(x, [(0.11, 0.22)])[:len(t)]
    s["radaron2"] = (x + static(1.6, 0.012) * np.exp(-t * 3)) * np.minimum(1, (1.6 - t) / 0.2)
    # Player joined / opening the lobby: short radio squelch, then a warm two-note "link established" chime
    # (its own sound; it used to share bleep11 with the power-on bleep)
    sq = static(0.04, 0.35) * np.exp(-t_of(0.04) * 60)
    note = lambda f, d: tone(f, d, decay=7, attack=0.004) + 0.25 * tone(f * 2, d, decay=14) + 0.1 * tone(f * 3, d, decay=20)
    s["lobbyjoin"] = np.concatenate([sq, gap(0.02), note(784, 0.12), note(1175, 0.32)]) * 0.6
    # Radar offline: falling tone, static fading out
    t = t_of(1.1)
    dn = tone(sweep(1500, 140, 1.1, 0.6), 1.1, decay=0.0001, attack=0.01, harm=0.35)
    s["radardn1"] = (dn * 0.55 + static(1.1, 0.22) * (1 - t / 1.1)) * (1 - t / 1.1) ** 1.5
    # Credit ticks: tiny bright counter clicks (played very often, at 0.33 volume)
    s["cashup1"] = tone(3200, 0.03, decay=160, attack=0.001) * 0.8
    s["cashdn1"] = tone(2500, 0.03, decay=160, attack=0.001) * 0.8
    # Promotion: three rising bell notes (C6, E6, G6)
    notes = [tone(f, 0.11 if i < 2 else 0.35, decay=12 if i < 2 else 6, harm=0.3)
             + 0.3 * tone(f * 2.01, 0.11 if i < 2 else 0.35, decay=20) for i, f in enumerate((1047, 1319, 1568))]
    s["hydrod1"] = np.concatenate([notes[0], notes[1], notes[2]]) * 0.55
    return s


def write_ogg(path, x):
    x = x / max(1e-9, np.max(np.abs(x))) * 0.7  # -3 dBFS peaks; the yaml sets per-sound volume
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
    ogg.encode(tmp.name, path)
    os.remove(tmp.name)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, x in sounds().items():
        write_ogg(os.path.join(OUT, name + ".ogg"), x)
        print(f"{name}.ogg  {len(x) / SR:.2f}s")


if __name__ == "__main__":
    main()
