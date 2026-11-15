#!/usr/bin/env python3
"""
Generates England's British-accent voices (IDEA-31) with Kokoro's British English voices: the same lines as the
Union announcer and Union units (from generate_voices_kokoro.jobs()), then the same trim / filter / level step.

  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_england.py
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_england.py --only conscmp1,ackno --force
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_england.py --process-only

Raw takes: assets/sounds/<folder>/<file>.wav. Game files: mods/rapx/audio/eva/england/ and voices/england-*/.
"""
import argparse
import os
import sys

import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_voices_kokoro as kv  # noqa: E402

# England folder -> (Union cast whose lines it speaks, Kokoro voice, speed, pitch, filter)
CASTS = {
    "eva/england": ("eva-union", "bf_emma", 1.0, 0, "console"),
    "voices/england-inf1": ("union-inf1", "bm_george", 1.05, 0, "radio"),
    "voices/england-inf2": ("union-inf2", "bm_lewis", 1.0, 0, "radio"),
    "voices/england-veh1": ("union-veh1", "bm_george", 1.0, 0, "intercom"),
    "voices/england-veh2": ("union-veh2", "bm_lewis", 0.95, 0, "intercom"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="only these file names, comma separated")
    ap.add_argument("--force", action="store_true", help="re-generate raw takes that already exist")
    ap.add_argument("--process-only", action="store_true", help="only redo trim/filter/level from raw takes")
    args = ap.parse_args()

    lines = {}
    for ck, f, text in kv.jobs():
        lines.setdefault(ck, {}).setdefault(f, text)
    todo = [(folder, f, text) for folder, (ck, *_rest) in CASTS.items() for f, text in lines[ck].items()
            if not args.only or f in set(args.only.split(","))]
    if not todo:
        sys.exit("nothing matches")

    pipes, KPipeline = {}, None
    made = failed = 0
    for i, (folder, f, text) in enumerate(todo, 1):
        _ck, voice, speed, pitch, filt = CASTS[folder]
        raw = os.path.join(kv.RAW, folder, f + ".wav")
        try:
            if not args.process_only and (args.force or not os.path.exists(raw)):
                if KPipeline is None:
                    from kokoro import KPipeline
                print(f"[{i}/{len(todo)}] {folder}/{f}  ({voice}) \"{kv.clean_text(text)}\"", flush=True)
                os.makedirs(os.path.dirname(raw), exist_ok=True)
                sf.write(raw, kv.synth(pipes, KPipeline, voice, speed, text), kv.RATE)
            kv.process(raw, os.path.join(kv.GAME, folder, f + ".ogg"), pitch, filt)
            made += 1
        except Exception as e:
            print(f"    FAILED {folder}/{f}: {e}", flush=True)
            failed += 1
    print(f"done: {made} game files, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
