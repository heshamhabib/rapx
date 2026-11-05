#!/usr/bin/env python3
"""
Speeds up making images by hand in ChatGPT in the browser: you paste and download, this does the rest.

For each prompt that has no image yet it copies the prompt to the clipboard, then watches
~/Downloads. As soon as you download the image from ChatGPT it is converted to PNG, saved under its
"Save as" name (same folders as generate_images.py) and the next prompt is copied.

  python3 browser_helper.py --prompts jet-prompts.md --category jets
  python3 browser_helper.py --prompts jet-prompts.md --only mik-3-strela,swarm-drone
  python3 browser_helper.py --prompts jet-prompts.md --ref ../../assets/jets/mik-3-strela.png

While it waits for a download:  c = copy the prompt again   r = copy the reference image
                                s = skip this one           q = quit

Images that already exist are skipped, so it can run next to generate_images.py: whichever
finishes an image first wins, and the other moves on.
"""
import argparse
import os
import select
import subprocess
import sys
import termios
import time
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from generate_images import DEFAULT_OUT, FOLDERS, PROMPTS, log, parse_prompts  # noqa: E402

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
PARTIAL_EXTS = (".crdownload", ".download", ".part")
REF_PREFIX = ("Match the style, camera angle, lighting and level of detail of the attached image, "
              "but draw the {what} described below.\n\n")


def copy_text(text):
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)


def copy_image(path):
    script = f'set the clipboard to (read (POSIX file "{os.path.abspath(path)}") as «class PNGf»)'
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True)


def ding():
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def images_in(folder):
    result = {}
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if name.lower().endswith(IMAGE_EXTS) and not name.startswith(".") and os.path.isfile(path):
            result[path] = os.path.getmtime(path)
    return result


def finished(path):
    """True once a download has stopped growing (browsers write the final file in one go, but be safe)."""
    size = os.path.getsize(path)
    time.sleep(0.6)
    return os.path.exists(path) and os.path.getsize(path) == size and size > 0


def save_png(src, dst):
    from PIL import Image
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.open(src).save(dst)


def read_key():
    """Returns a pressed key, or None after a short wait."""
    if not sys.stdin.isatty():
        time.sleep(0.5)
        return None
    if select.select([sys.stdin], [], [], 0.5)[0]:
        return sys.stdin.read(1).lower()
    return None


def wait_for_download(downloads, before, it, prompt, ref):
    """Returns the downloaded file, "skip" or "quit"."""
    while True:
        if os.path.exists(it["dst"]):
            print("  already made elsewhere (generate_images.py?), moving on")
            return "skip"

        for path, mtime in images_in(downloads).items():
            if (path not in before or mtime > before[path]) and not any(
                    os.path.exists(path + ext) for ext in PARTIAL_EXTS) and finished(path):
                return path

        key = read_key()
        if key == "q":
            return "quit"
        if key == "s":
            return "skip"
        if key == "c":
            copy_text(prompt)
            print("  prompt copied again")
        if key == "r":
            if ref:
                copy_image(ref)
                print("  reference image copied: paste it into the chat, then press c for the prompt")
            else:
                print("  no --ref image given")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", default=PROMPTS, help="prompt file (default gemini-prompts.md; e.g. jet-prompts.md)")
    ap.add_argument("--only", help="comma-separated Save-as names or numbers")
    ap.add_argument("--from", dest="start", help="start at this Save-as name or number")
    ap.add_argument("--category", choices=sorted(set(FOLDERS.values())))
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ref", help="style reference image; the prompt asks ChatGPT to match it (press r to copy it)")
    ap.add_argument("--downloads", default=os.path.expanduser("~/Downloads"))
    ap.add_argument("--keep", action="store_true", help="leave the downloaded file in Downloads")
    ap.add_argument("--new-chat", action="store_true", help="open a new ChatGPT chat in the browser for every prompt")
    args = ap.parse_args()

    prompts = args.prompts if os.path.isabs(args.prompts) else os.path.join(HERE, args.prompts)
    items = parse_prompts(prompts)
    if args.only:
        want = {w.strip() for w in args.only.split(",")}
        # "egypt" also selects every "egypt/<building>" (national building styles)
        items = [it for it in items if it["name"] in want or str(it["num"]) in want or it["name"].split("/")[0] in want]
    if args.start:
        nums = [it["num"] for it in items if it["name"] == args.start or str(it["num"]) == args.start]
        if not nums:
            sys.exit("--from %s: no such prompt" % args.start)
        items = [it for it in items if it["num"] >= nums[0]]
    if args.category:
        items = [it for it in items if FOLDERS[it["section"]] == args.category]
    for it in items:
        it["dst"] = os.path.join(args.out, FOLDERS[it["section"]], it["name"] + ".png")

    if not os.path.isdir(args.downloads):
        sys.exit(f"--downloads {args.downloads}: no such folder")
    try:
        images_in(args.downloads)
    except PermissionError:
        sys.exit(f"macOS does not let this terminal read {args.downloads}.\n"
                 "Either allow it (System Settings > Privacy & Security > Files and Folders > your terminal app >\n"
                 "Downloads Folder, then restart the terminal), or download to another folder and pass it with\n"
                 "--downloads, e.g. --downloads ../../assets/inbox")

    todo = [it for it in items if not os.path.exists(it["dst"])]
    ref = os.path.abspath(args.ref) if args.ref else None
    if ref and not os.path.exists(ref):
        sys.exit("--ref %s not found" % ref)

    print(f"{len(todo)} images to make ({len(items) - len(todo)} already done). Keys while waiting: "
        "c = copy prompt again, r = copy reference image, s = skip, q = quit\n")

    # Single key presses without Enter
    old = termios.tcgetattr(sys.stdin) if sys.stdin.isatty() else None
    if old:
        tty.setcbreak(sys.stdin.fileno())
    saved = 0
    try:
        for n, it in enumerate(todo, 1):
            if os.path.exists(it["dst"]):
                continue

            what = "aircraft" if FOLDERS[it["section"]] == "jets" else "building" if it["section"] == "buildings" else "object"
            use_ref = ref if ref and os.path.abspath(it["dst"]) != ref else None
            prompt = (REF_PREFIX.format(what=what) if use_ref else "") + it["prompt"]

            before = images_in(args.downloads)
            copy_text(prompt)
            if args.new_chat:
                subprocess.run(["open", "https://chatgpt.com/"])
            print(f"[{n}/{len(todo)}] {it['title']}  ->  {os.path.relpath(it['dst'], args.out)}")
            print("  prompt copied: paste it in a new ChatGPT chat"
                + (" (press r first to copy the reference image)" if use_ref else "") + ", then download the image")

            result = wait_for_download(args.downloads, before, it, prompt, use_ref)
            if result == "quit":
                break
            if result == "skip":
                continue

            save_png(result, it["dst"])
            if not args.keep:
                os.remove(result)
            saved += 1
            log(f"browser helper: saved {it['dst']} from {os.path.basename(result)}")
            ding()
    finally:
        if old:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)

    print(f"\n{saved} saved.")


if __name__ == "__main__":
    main()
