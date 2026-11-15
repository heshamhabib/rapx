#!/usr/bin/env python3
"""
Generates the Indian accent voices for India and Pakistan (IDEA-31) with Kokoro's Hindi voices reading the
English lines written in Devanagari (southasia_lines.py): hf_alpha announcer, hm_psi units (user's picks
2026-11-15). Then the same trim / filter / level step as generate_voices_kokoro.py.

  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_southasia.py
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_southasia.py --only conscmp1,ackno --force
  ~/.venvs/rapx-tts/bin/python artsrc/audio/generate_southasia.py --process-only

Raw takes: assets/sounds/eva/southasia/, assets/sounds/voices/southasia/ (one take per unit line, made into the
four inf/veh variants by pitch + filter). Game files: mods/rapx/audio/eva/southasia/, voices/southasia-*/.
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_voices_kokoro as kv  # noqa: E402
from southasia_lines import EVA, UNITS  # noqa: E402

EVA_VOICE = "hf_alpha"
UNIT_VOICE = "hm_psi"
VEHICLE_LINES = {"vehic1", "yessir1", "report1", "await1", "ackno", "affirm1"}
# game folder -> (pitch, filter), same as union-inf1/2 and union-veh1/2 in generate_voices_kokoro.VOICES
UNIT_VARIANTS = {"southasia-inf1": (0, "radio"), "southasia-inf2": (-1.5, "radio"),
                 "southasia-veh1": (0, "intercom"), "southasia-veh2": (-1.5, "intercom")}


def process(kind, f, raw):
    if kind == "eva":
        kv.process(raw, os.path.join(kv.GAME, "eva", "southasia", f + ".ogg"), 0, "console")
        return
    for folder, (pitch, filt) in UNIT_VARIANTS.items():
        if "veh" in folder and f not in VEHICLE_LINES:
            continue
        if "inf" in folder and f == "vehic1":
            continue
        kv.process(raw, os.path.join(kv.GAME, "voices", folder, f + ".ogg"), pitch, filt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="only these file names, comma separated")
    ap.add_argument("--force", action="store_true", help="re-generate raw takes that already exist")
    ap.add_argument("--process-only", action="store_true", help="only redo trim/filter/level from raw takes")
    args = ap.parse_args()

    todo = [("eva", f, t, EVA_VOICE, os.path.join(kv.RAW, "eva", "southasia", f + ".wav")) for f, t in EVA.items()]
    todo += [("units", f, t, UNIT_VOICE, os.path.join(kv.RAW, "voices", "southasia", f + ".wav"))
             for f, t in UNITS.items()]
    todo = [j for j in todo if not args.only or j[1] in set(args.only.split(","))]
    if not todo:
        sys.exit("nothing matches")

    pipe = None
    made = failed = 0
    for i, (kind, f, text, voice, raw) in enumerate(todo, 1):
        try:
            if not args.process_only and (args.force or not os.path.exists(raw)):
                if pipe is None:
                    from kokoro import KPipeline
                    pipe = KPipeline(lang_code="h")
                print(f"[{i}/{len(todo)}] {kind}/{f}  ({voice}) \"{text}\"", flush=True)
                parts = [np.asarray(r.audio, dtype=np.float32) for r in pipe(text, voice=voice, speed=1.0)]
                os.makedirs(os.path.dirname(raw), exist_ok=True)
                sf.write(raw, np.concatenate(parts), kv.RATE)
            process(kind, f, raw)
            made += 1
        except Exception as e:
            print(f"    FAILED {kind}/{f}: {e}", flush=True)
            failed += 1
    print(f"done: {made} lines, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
