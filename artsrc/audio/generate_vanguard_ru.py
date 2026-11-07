#!/usr/bin/env python3
"""
Generates the Vanguard announcer with a Russian accent (IDEA-31): Chatterbox Multilingual (MIT, free, local)
reads the lines in vanguard_ru_lines.py as Russian, in the am_onyx voice copied from a reference clip of the
Kokoro Vanguard takes. Then the same trim / console filter / level step as generate_voices_kokoro.py.

  python3.11 -m venv ~/.venvs/rapx-chatterbox
  ~/.venvs/rapx-chatterbox/bin/pip install chatterbox-tts soundfile "setuptools<81"
  ~/.venvs/rapx-chatterbox/bin/python artsrc/audio/generate_vanguard_ru.py
  ~/.venvs/rapx-chatterbox/bin/python artsrc/audio/generate_vanguard_ru.py --only abldgin1,unitrdy1 --force

Raw takes: assets/sounds/eva/vanguard-ru/<file>.wav. Game files: mods/rapx/audio/eva/vanguard/<file>.mp3.
The first run downloads the model (a few GB).
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_voices_kokoro as kv  # noqa: E402  (trim/filter/level; kokoro itself is not imported)
from vanguard_ru_lines import LINES  # noqa: E402

RAW = os.path.join(kv.RAW, "eva", "vanguard-ru")
GAME = os.path.join(kv.GAME, "eva", "vanguard")
REFERENCE = os.path.join(RAW, "reference-onyx.wav")
# Kokoro am_onyx takes that make up the voice reference (~13 s)
REFERENCE_LINES = ["conscmp1", "baseatk1", "unitrdy1", "lopower1", "bctrinit", "misnwon1"]
SEED = 7


def make_reference():
    parts = []
    for f in REFERENCE_LINES:
        a, sr = sf.read(os.path.join(kv.RAW, "eva", "vanguard", f + ".wav"), dtype="float32")
        parts += [a, np.zeros(int(sr * 0.3), dtype=np.float32)]
    os.makedirs(RAW, exist_ok=True)
    sf.write(REFERENCE, np.concatenate(parts), sr)


def speech_length(path):
    """Seconds of audio left after trimming the silence at both ends (Chatterbox sometimes rambles on)."""
    import subprocess
    out = subprocess.run(["ffmpeg", "-i", path, "-af", kv.TRIM, "-ar", str(kv.RATE), "-ac", "1",
                          "-f", "s16le", "-"], capture_output=True).stdout
    return len(out) / 2 / kv.RATE


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="only these file names, comma separated")
    ap.add_argument("--force", action="store_true", help="re-generate raw takes that already exist")
    ap.add_argument("--process-only", action="store_true", help="only redo trim/filter/level from raw takes")
    ap.add_argument("--exaggeration", type=float, default=0.5)
    ap.add_argument("--cfg", type=float, default=0.5)
    ap.add_argument("--best-of", type=int, default=1,
                    help="make N takes (seeds seed..seed+N-1), keep the one closest in length to the Kokoro take")
    ap.add_argument("--seed", type=int, default=SEED, help="try another seed when a take comes out wrong")
    args = ap.parse_args()

    names = [n for n in LINES if not args.only or n in set(args.only.split(","))]
    if not names:
        sys.exit("nothing matches")
    if not os.path.exists(REFERENCE):
        make_reference()

    model = None
    made = failed = 0
    for i, f in enumerate(names, 1):
        raw = os.path.join(RAW, f + ".wav")
        try:
            if not args.process_only and (args.force or not os.path.exists(raw)):
                if model is None:
                    import torch
                    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                    dev = "mps" if torch.backends.mps.is_available() else "cpu"
                    model = ChatterboxMultilingualTTS.from_pretrained(device=dev)
                print(f"[{i}/{len(names)}] {f}  \"{LINES[f]}\"", flush=True)
                target = speech_length(os.path.join(kv.RAW, "eva", "vanguard", f + ".wav"))
                best = None
                for seed in range(args.seed, args.seed + args.best_of):
                    torch.manual_seed(seed)
                    w = model.generate(LINES[f], language_id="ru", audio_prompt_path=REFERENCE,
                                       exaggeration=args.exaggeration, cfg_weight=args.cfg)
                    sf.write(raw, w.squeeze(0).cpu().numpy(), model.sr)
                    miss = abs(speech_length(raw) - target)
                    if best is None or miss < best[0]:
                        best = (miss, seed, open(raw, "rb").read())
                with open(raw, "wb") as fh:
                    fh.write(best[2])
                if args.best_of > 1:
                    print(f"    kept seed {best[1]} ({best[0]:.2f}s off the Kokoro length)")
            kv.process(raw, os.path.join(GAME, f + ".mp3"), 0, "console")
            made += 1
        except Exception as e:
            print(f"    FAILED {f}: {e}")
            failed += 1
    print(f"done: {made} game files, {failed} failed  ->  {GAME}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
