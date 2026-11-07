#!/usr/bin/env python3
"""
Generates the EVA announcers and unit voices with Kokoro-82M, a free local text-to-speech model (IDEA-31).
No account or API key: the model (Apache-2.0, ~330 MB) downloads once and then runs offline.
The lines come from artsrc/prompts/make_sound_prompts.py, the same list as the Gemini script.

  python3.11 -m venv ~/.venvs/rapx-tts && ~/.venvs/rapx-tts/bin/pip install "kokoro>=0.9" soundfile
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_voices_kokoro.py              # everything
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_voices_kokoro.py --cast eva-union --only conscmp1 --force
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_voices_kokoro.py --process-only   # redo filters, keep raw takes

Raw takes go to assets/sounds/<folder>/<file>.wav; the game files (trimmed, filtered, levelled)
go to mods/rapx/audio/<folder>/<file>.ogg (Ogg Vorbis, see ogg.py). Existing raw takes are reused unless --force.
The Vanguard announcer is made by generate_vanguard_ru.py (Russian accent); this script skips it unless --cast eva-vanguard.
Voices picked by the user 2026-11-07: af_heart (Union EVA), am_onyx (Vanguard EVA), am_eric (units).
"""
import argparse
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "artsrc", "prompts"))
import make_sound_prompts as sp  # noqa: E402

sys.path.insert(0, HERE)
import ogg  # noqa: E402

RAW = os.path.join(ROOT, "assets", "sounds")
GAME = os.path.join(ROOT, "mods", "rapx", "audio")
RATE = 24000

# cast -> (Kokoro voice, speed, pitch shift in semitones, filter)
VOICES = {
    "eva-union": ("af_heart", 1.0, 0, "console"),
    "eva-vanguard": ("am_onyx", 1.0, 0, "console"),  # was 0.9: "Building." sounded lazy (user, 2026-11-07)
    "union-inf1": ("am_eric", 1.05, 0, "radio"),
    "union-inf2": ("am_eric", 1.0, -1.5, "radio"),
    "union-veh1": ("am_eric", 1.0, 0, "intercom"),
    "union-veh2": ("am_eric", 0.95, -1.5, "intercom"),
    "vanguard-inf1": ("am_eric", 1.0, -3, "radio"),
    "vanguard-inf2": ("am_eric", 0.92, -4.5, "radio"),
    "vanguard-veh1": ("am_eric", 0.95, -3, "intercom"),
    "vanguard-veh2": ("am_eric", 0.9, -4.5, "intercom"),
    "engineer": ("am_eric", 1.1, 1, "radio"),
    "mechanic": ("am_eric", 0.9, -1, "radio"),
    "spy": ("am_eric", 0.92, -2, "radio"),
    "shock": ("am_eric", 1.05, -3.5, "radio"),
    "medic": ("af_sarah", 1.0, 0, "radio"),
    "tanya": ("af_bella", 1.05, 0, "radio"),
    "dying": ("am_eric", 1.0, 0, "none"),
}
# Extra speed per EVA delivery (make_sound_prompts.DELIVERY keys), so short confirmations stay crisp and alarms
# sound urgent. Only Vanguard for now; Union was approved as it is.
EVA_SPEED = {"eva-vanguard": {"ok": 1.12, "urgent": 1.08, "warn": 1.06}}
DELIVERY_OF = {f: d for _k, f, _t, d in sp.EVA_NOW + sp.EVA_CAMPAIGN}

SKIP_CAST = {"thief", "civ-male", "civ-female"}  # removed from the mod 2026-11-06
REPLACED_CAST = {"eva-vanguard"}  # now generate_vanguard_ru.py; only made here with an explicit --cast

FILTERS = {
    "console": "highpass=f=120,lowpass=f=8000,acompressor=threshold=-20dB:ratio=3:attack=5:release=80",
    "radio": "highpass=f=300,lowpass=f=3400,acompressor=threshold=-18dB:ratio=4:attack=3:release=60",
    "intercom": "highpass=f=400,lowpass=f=3000,acompressor=threshold=-22dB:ratio=6:attack=2:release=50,"
                "aecho=0.8:0.4:8:0.2",
    "none": "anull",
}
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,"
        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")

# Announcements still listed in notifications.yaml but never played in skirmish (EVA_SKIP in make_sound_prompts.py).
# Recorded anyway with neutral text so every yaml entry has a file and nothing loads from the original game.
EVA_UNPLAYED = [
    ("aarive1", "Reinforcements arriving, east."), ("aarrivn1", "Reinforcements arriving, north."),
    ("aarrivs1", "Reinforcements arriving, south."), ("aarrivw1", "Reinforcements arriving, west."),
    ("aavail1", "Atom bomb available."), ("atlnch1", "Atom bomb launch detected."), ("atprep1", "Atom bomb prepping."),
    ("aselect1", "Forces selected."), ("sovemp1", "Forces selected."),
    ("afallen1", "Our forces have fallen."), ("sovefal1", "Our forces have fallen."),
    ("sovforc1", "Our forces have fallen."), ("bldgprg1", "Building in progress."),
    ("chroyes1", "Chronosphere test successful."), ("opterm1", "Operation control terminated."),
    ("comndof1", "Commando freed."), ("comndor1", "Commando rescued."),
    ("tanyaf1", "Commando freed."), ("tanyar1", "Commando rescued."),
    ("kosyfre1", "Defector freed."), ("kosyres1", "Defector rescued."),
    ("mercf1", "Mercenary freed."), ("mercr1", "Mercenary rescued."),
]


def jobs():
    out = []
    for _group, ck, f, text, _style in sp.tts_jobs():
        if ck not in SKIP_CAST:
            out.append((ck, f, text))
    for side in ("eva-union", "eva-vanguard"):
        for f, text in EVA_UNPLAYED:
            out.append((side, f, text))
    return out


def folder(ck):
    return sp.CAST[ck][3]


def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text)          # Gemini tags like <laugh>
    return text.replace("—", "!").strip()


def synth(pipes, KPipeline, voice, speed, text):
    lang = voice[0]  # 'a' = American, 'b' = British
    p = pipes.get(lang) or pipes.setdefault(lang, KPipeline(lang_code=lang))
    parts = [np.asarray(r.audio, dtype=np.float32) for r in p(clean_text(text), voice=voice, speed=speed)]
    if not parts:
        raise RuntimeError("no audio")
    return np.concatenate(parts)


def process(raw_path, game_path, pitch, filt):
    chain = []
    if pitch:
        r = 2 ** (pitch / 12)
        chain += [f"asetrate={RATE * r:.0f}", f"aresample={RATE}", f"atempo={1 / r:.4f}"]
    chain += [TRIM, FILTERS[filt]]
    os.makedirs(os.path.dirname(game_path), exist_ok=True)
    tmp = game_path + ".tmp.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw_path, "-af", ",".join(chain),
                    "-ar", str(RATE), "-ac", "1", tmp], check=True)
    a, _ = sf.read(tmp, dtype="float32")
    peak = float(np.max(np.abs(a))) if len(a) else 0
    if peak > 0:
        a = a * (0.89 / peak)  # -1 dBFS
    fade = min(len(a), int(RATE * 0.01))
    a[len(a) - fade:] *= np.linspace(1, 0, fade)
    sf.write(tmp, a, RATE, subtype="PCM_16")
    ogg.encode(tmp, game_path)
    os.remove(tmp)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cast", help="only this character, e.g. eva-union, union-inf1, tanya")
    ap.add_argument("--only", help="only these file names, comma separated")
    ap.add_argument("--force", action="store_true", help="re-generate raw takes that already exist")
    ap.add_argument("--process-only", action="store_true", help="only redo trim/filter/level from raw takes")
    args = ap.parse_args()

    todo = jobs()
    if args.cast:
        todo = [j for j in todo if j[0] == args.cast]
    else:
        todo = [j for j in todo if j[0] not in REPLACED_CAST]
    if args.only:
        names = set(args.only.split(","))
        todo = [j for j in todo if j[1] in names]
    if not todo:
        sys.exit("nothing matches those filters")

    pipes, KPipeline = {}, None
    made = failed = 0
    for i, (ck, f, text) in enumerate(todo, 1):
        voice, speed, pitch, filt = VOICES[ck]
        speed *= EVA_SPEED.get(ck, {}).get(DELIVERY_OF.get(f), 1.0)
        raw = os.path.join(RAW, folder(ck), f + ".wav")
        game = os.path.join(GAME, folder(ck), f + ".ogg")
        try:
            if not args.process_only and (args.force or not os.path.exists(raw)):
                if KPipeline is None:
                    from kokoro import KPipeline
                print(f"[{i}/{len(todo)}] {folder(ck)}/{f}  ({voice}) \"{clean_text(text)}\"")
                os.makedirs(os.path.dirname(raw), exist_ok=True)
                sf.write(raw, synth(pipes, KPipeline, voice, speed, text), RATE)
            process(raw, game, pitch, filt)
            made += 1
        except Exception as e:
            print(f"    FAILED {folder(ck)}/{f}: {e}")
            failed += 1
    print(f"done: {made} game files, {failed} failed  ->  {GAME}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
