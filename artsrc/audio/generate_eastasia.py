#!/usr/bin/env python3
"""
Generates the East Asian accent voices for Japan, South Korea and China (IDEA-31): Chatterbox Multilingual
(MIT, free, local) reads the lines in eastasia_lines.py. The announcer is English in katakana read as Japanese,
the units are English in Chinese characters read as Chinese. The voices are copied from the two samples the
user picked on 2026-11-15 (jp-eva, cn-unit-hanzi), kept as reference clips next to the raw takes.
All three nations share these files (eva/eastasia, voices/eastasia-*).

  ~/.venvs/rapx-chatterbox/bin/python artsrc/audio/generate_eastasia.py                 # everything
  ~/.venvs/rapx-chatterbox/bin/python artsrc/audio/generate_eastasia.py --part units
  ~/.venvs/rapx-chatterbox/bin/python artsrc/audio/generate_eastasia.py --only conscmp1 --force --seed 11

Raw takes: assets/sounds/eva/eastasia/, assets/sounds/voices/eastasia/ (one take per unit line, made into the
four inf/veh variants by the same pitch + filter step as the Union unit voices).
A take that runs much longer than the Kokoro English take (Chatterbox sometimes rambles) is redone with the
next seed, up to --tries times, and the closest one is kept.
"""
import argparse
import os
import sys

import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_voices_kokoro as kv  # noqa: E402  (trim/filter/level; kokoro itself is not imported)
from generate_vanguard_ru import speech_length  # noqa: E402
from eastasia_lines import EVA, UNITS  # noqa: E402

EVA_RAW = os.path.join(kv.RAW, "eva", "eastasia")
UNIT_RAW = os.path.join(kv.RAW, "voices", "eastasia")
EVA_REFERENCE = os.path.join(EVA_RAW, "reference-jp-eva.wav")
UNIT_REFERENCE = os.path.join(UNIT_RAW, "reference-cn-unit.wav")
VEHICLE_LINES = {"vehic1", "yessir1", "report1", "await1", "ackno", "affirm1"}
# game folder -> (pitch, filter), same as union-inf1/2 and union-veh1/2 in generate_voices_kokoro.VOICES
UNIT_VARIANTS = {"eastasia-inf1": (0, "radio"), "eastasia-inf2": (-1.5, "radio"),
                 "eastasia-veh1": (0, "intercom"), "eastasia-veh2": (-1.5, "intercom")}
SEED = 7


def jobs(part):
    out = []
    if part in ("all", "eva"):
        for f, text in EVA.items():
            out.append(("eva", f, text, "ja", EVA_REFERENCE, os.path.join(EVA_RAW, f + ".wav"),
                        os.path.join(kv.RAW, "eva", "union", f + ".wav")))
    if part in ("all", "units"):
        for f, text in UNITS.items():
            english = os.path.join(kv.RAW, "voices", "union-veh1" if f == "vehic1" else "union-inf1", f + ".wav")
            out.append(("units", f, text, "zh", UNIT_REFERENCE, os.path.join(UNIT_RAW, f + ".wav"), english))
    return out


def process(kind, f, raw):
    if kind == "eva":
        kv.process(raw, os.path.join(kv.GAME, "eva", "eastasia", f + ".ogg"), 0, "console")
        return
    for folder, (pitch, filt) in UNIT_VARIANTS.items():
        if "veh" in folder and f not in VEHICLE_LINES:
            continue
        if "inf" in folder and f == "vehic1":
            continue
        kv.process(raw, os.path.join(kv.GAME, "voices", folder, f + ".ogg"), pitch, filt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", choices=("all", "eva", "units"), default="all")
    ap.add_argument("--only", help="only these file names, comma separated")
    ap.add_argument("--force", action="store_true", help="re-generate raw takes that already exist")
    ap.add_argument("--process-only", action="store_true", help="only redo trim/filter/level from raw takes")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--tries", type=int, default=3, help="seeds to try when a take runs far too long")
    args = ap.parse_args()

    todo = [j for j in jobs(args.part) if not args.only or j[1] in set(args.only.split(","))]
    if not todo:
        sys.exit("nothing matches")
    for ref in (EVA_REFERENCE, UNIT_REFERENCE):
        if not os.path.exists(ref):
            sys.exit(f"missing voice reference {ref}")

    model = None
    made = failed = 0
    for i, (kind, f, text, lang, ref, raw, english) in enumerate(todo, 1):
        try:
            if not args.process_only and (args.force or not os.path.exists(raw)):
                import torch
                if model is None:
                    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                    dev = "mps" if torch.backends.mps.is_available() else "cpu"
                    model = ChatterboxMultilingualTTS.from_pretrained(device=dev)
                print(f"[{i}/{len(todo)}] {kind}/{f}  \"{text}\"", flush=True)
                target = speech_length(english)
                limit = target * 2.2 + 1.0
                best = None
                for seed in range(args.seed, args.seed + args.tries):
                    torch.manual_seed(seed)
                    w = model.generate(text, language_id=lang, audio_prompt_path=ref,
                                       exaggeration=0.5, cfg_weight=0.5)
                    sf.write(raw, w.squeeze(0).cpu().numpy(), model.sr)
                    length = speech_length(raw)
                    if best is None or abs(length - target) < best[0]:
                        best = (abs(length - target), seed, length, open(raw, "rb").read())
                    if length <= limit:
                        break
                    print(f"    seed {seed}: {length:.1f}s, English take is {target:.1f}s, trying again", flush=True)
                with open(raw, "wb") as fh:
                    fh.write(best[3])
                if best[2] > limit:
                    print(f"    CHECK {kind}/{f}: still {best[2]:.1f}s (kept seed {best[1]})", flush=True)
            process(kind, f, raw)
            made += 1
        except Exception as e:
            print(f"    FAILED {kind}/{f}: {e}", flush=True)
            failed += 1
    print(f"done: {made} lines, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
