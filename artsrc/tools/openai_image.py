#!/usr/bin/env python3
"""
Generate an image with the OpenAI Images API (no extra dependencies).
The API key is read from ~/.openai_key (or $OPENAI_API_KEY) and never printed.

  python3 artsrc/tools/openai_image.py out.png --prompt-file prompt.txt [--size 2048x1024] [--quality high]
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request


def api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        with open(os.path.expanduser("~/.openai_key")) as f:
            key = f.read().strip()
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--model", default="gpt-image-2")
    ap.add_argument("--size", default="2048x1024")
    ap.add_argument("--quality", default="high")
    args = ap.parse_args()

    prompt = open(args.prompt_file).read().strip()
    body = json.dumps({"model": args.model, "prompt": prompt, "size": args.size, "quality": args.quality, "n": 1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body, headers={
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    })

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"API error {e.code}: {e.read().decode(errors='replace')[:800]}", file=sys.stderr)
        sys.exit(1)

    with open(args.out, "wb") as f:
        f.write(base64.b64decode(result["data"][0]["b64_json"]))

    usage = result.get("usage", {})
    print(f"wrote {args.out} in {time.time() - start:.0f}s; usage: {json.dumps(usage)}")


if __name__ == "__main__":
    main()
