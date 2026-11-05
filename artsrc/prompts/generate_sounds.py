#!/usr/bin/env python3
"""
Generates the voice lines in sound-prompts.md with the Gemini text-to-speech API (IDEA-31).
The lines, voices and styles come from make_sound_prompts.py, so both always agree.

  export GEMINI_API_KEY=...                                   # from https://aistudio.google.com/apikey
  python3 artsrc/prompts/generate_sounds.py                   # everything skirmish needs (default)
  python3 artsrc/prompts/generate_sounds.py --group eva-now   # just the 108 announcer lines (start here)
  python3 artsrc/prompts/generate_sounds.py --group units --cast union-inf1
  python3 artsrc/prompts/generate_sounds.py --only conscmp1 --takes 3 --force
  python3 artsrc/prompts/generate_sounds.py --dry-run         # list what would be made

Groups: skirmish (default: eva-now + units + special, without civilians), eva-now, eva-campaign, units, special, all. Files go to assets/sounds/<cast folder>/<file>.wav
(24 kHz mono WAV, as Gemini returns it). Existing files are skipped unless --force, so an interrupted run can
simply be restarted. Extra takes are saved as <file>.take2.wav, <file>.take3.wav... to compare by ear.
Sound effects are not made here: Gemini can't generate them (see sound-prompts.md section 5).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

import make_sound_prompts as sp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "assets", "sounds"))
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = "gemini-3.8-flash-tts"
# Skirmish focus: campaign announcer lines and civilians come later.
SKIRMISH_GROUPS = {"eva-now", "units", "special"}
SKIRMISH_SKIP_CAST = {"civ-male", "civ-female"}


def synthesize(key, model, voice, text, style):
    body = {
        "model": model,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{"type": "speech_metadata", "style": style}],
            }],
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST", headers={
        "x-goog-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    audio = [c for s in resp.get("steps", []) if s.get("type") == "model_output"
             for c in s.get("content", []) if c.get("type") == "audio"]
    if not audio:
        raise RuntimeError("no audio in response: " + json.dumps(resp)[:300])
    return base64.b64decode(audio[-1]["data"])


def synthesize_with_retry(key, model, voice, text, style, tries=5):
    for attempt in range(tries):
        try:
            return synthesize(key, model, voice, text, style)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            # 429 = rate limit, 5xx = server busy: wait and try again. Anything else is a real error.
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"HTTP {e.code}: {msg}")
            wait = 2 ** attempt * 5
            print(f"    HTTP {e.code}, retrying in {wait}s")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as e:
            wait = 2 ** attempt * 5
            print(f"    {e}, retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("gave up after retries")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", default="skirmish",
                    choices=["skirmish", "eva-now", "eva-campaign", "units", "special", "all"])
    ap.add_argument("--cast", help="only this character, e.g. eva-union, union-inf1, tanya")
    ap.add_argument("--only", help="only these file names, comma separated, e.g. conscmp1,unitrdy1")
    ap.add_argument("--takes", type=int, default=1, help="takes per line (extra takes saved as .take2.wav...)")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = [j for j in sp.tts_jobs() if args.group == "all" or j[0] == args.group
            or (args.group == "skirmish" and j[0] in SKIRMISH_GROUPS and j[1] not in SKIRMISH_SKIP_CAST)]
    if args.cast:
        jobs = [j for j in jobs if j[1] == args.cast]
    if args.only:
        names = set(args.only.split(","))
        jobs = [j for j in jobs if j[2] in names]
    if not jobs:
        sys.exit("nothing matches those filters")

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key and not args.dry_run:
        sys.exit("set GEMINI_API_KEY first (create one at https://aistudio.google.com/apikey)")

    made = skipped = failed = 0
    for i, (_group, ck, f, text, style) in enumerate(jobs, 1):
        name, voice, _, folder = sp.CAST[ck]
        for take in range(1, args.takes + 1):
            fn = f"{f}.wav" if take == 1 else f"{f}.take{take}.wav"
            path = os.path.join(OUT, folder, fn)
            label = f"[{i}/{len(jobs)}] {folder}/{fn}  ({voice}) \"{text}\""
            if os.path.exists(path) and not args.force:
                skipped += 1
                continue
            print(label)
            if args.dry_run:
                print(f"    style: {style}")
                continue
            try:
                wav = synthesize_with_retry(key, args.model, voice, text, style)
            except Exception as e:
                print(f"    FAILED: {e}")
                failed += 1
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(wav)
            made += 1
            time.sleep(args.delay)
    print(f"done: {made} made, {skipped} already existed, {failed} failed  ->  {OUT}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
