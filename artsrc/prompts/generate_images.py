#!/usr/bin/env python3
"""
Runs every prompt in gemini-prompts.md through ChatGPT image generation (via the Codex CLI that
ships inside ChatGPT.app, logged in with the ChatGPT account) and saves each picture under its
"Save as" name, with no manual steps.

  python3 generate_images.py                      # everything not generated yet
  python3 generate_images.py --only weap,powr     # just these
  python3 generate_images.py --from 1tnk          # start at the Light Tank (skip buildings)
  python3 generate_images.py --category buildings # buildings | units | environment
  python3 generate_images.py --force --only fact  # regenerate even if the file exists
  python3 generate_images.py --list               # show what would run
  python3 generate_images.py --prompts jet-prompts.md --category jets   # the IDEA-12 jet roster
  python3 generate_images.py --prompts style-prompts.md --category styles --only egypt   # national building styles
  python3 generate_images.py --prompts jet-prompts.md --ref ../../assets/jets/mik-21-fishbone.png
                                                  # attach an approved jet as the style reference

  python3 generate_images.py --prompts env-prompts.md --category env --only trees
                                                  # map environment (attaches each item's classic sprite)
  python3 generate_images.py --prompts env-prompts.md --category env --order mandatory --stop-on-limit \
      --track ../../assets/env/progress.json      # mandatory groups first, stop at the usage limit,
                                                  # keep a progress file + PROGRESS.md report (run_env_images.sh)
  python3 generate_images.py --prompts berlin-prompts.md --category maps --only berlin/style-a
                                                  # painted maps (IDEA-28): style frames repaint a Blender crop;
                                                  # textures take the chosen frame as --ref
  python3 generate_images.py --prompts env-sheets.md --category env --only tech/fcom
                                                  # sheets: several items in one image (fewer requests), cut back
                                                  # into the usual files by slice_sheet.py; the raw sheet stays in
                                                  # assets/env/sheets/ (python3 slice_sheet.py to re-cut by hand)

Output: RedAlertProjectX/assets/{buildings,units,environment,jets,styles,env}/<name>.png (override with --out).
Existing files are skipped, so a stopped run resumes where it left off. Each image takes about a
minute; usage limits on the ChatGPT plan are waited out and retried automatically.
Wrap it in `caffeinate -i` for long runs so the Mac doesn't sleep.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from slice_sheet import SliceError, slice_sheet

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE, "gemini-prompts.md")
# The ChatGPT app moves its bundled Codex CLI between releases; use the first one that exists.
CODEX_CANDIDATES = [
    os.environ.get("CODEX_BIN", ""),
    "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
    "/Applications/ChatGPT.app/Contents/Resources/codex",
    shutil.which("codex") or "",
]


def find_codex():
    return next((c for c in CODEX_CANDIDATES if c and os.path.exists(c)), None)


CODEX = find_codex() or CODEX_CANDIDATES[1]
CODEX_HOME = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
GENERATED = os.path.join(CODEX_HOME, "generated_images")
DEFAULT_OUT = os.path.abspath(os.path.join(HERE, "..", "..", "assets"))
STYLE_REF = os.path.join(HERE, "..", "buildings", "src", "fact-chatgpt.png")
LOG = os.path.join(DEFAULT_OUT, "generate_images.log")

# Markdown "## Section" -> output folder.
FOLDERS = {
    "buildings": "buildings",
    "vehicles": "units",
    "aircraft": "units",
    "ships": "units",
    "infantry": "units",
    "infantry animations": "units",
    "robot animations": "units",
    "soldier views": "units",
    "soldier views unarmed": "units",
    "jets": "jets",
    "jet variants": "jets",
    "other aircraft": "jets",
    "cameos": "cameos",
    "support powers": "cameos",
    "environment": "environment",
    "building styles": "styles",
    "map environment": "env",
    "map environment sheets": "env",
    "map style frames": "maps",
    "map textures": "maps",
}

WRAPPER = """Generate exactly one image with your built-in image generation tool (image_gen). Do not \
write code, do not call the OpenAI API, do not edit or post-process the result, and do not ask \
questions. Pass the prompt below to the tool verbatim{ref}. Generate it only once, then reply with \
the single word DONE.

PROMPT:
{prompt}
"""
REF_LAYOUT = (", prefixed with: \"Use the attached image only as a layout reference: keep the same object, "
              "footprint, composition and camera angle, but redraw it as a high-resolution realistic asset.\"")
REF_REPAINT = (", prefixed with: \"The attached image is a 3D render of a game map seen from straight above. Keep its "
               "layout exactly: every building, street, square, river bank, bridge, crater and object stays in the "
               "same place, with the same size, outline and camera; repaint the whole picture in the style described "
               "below.\"")
REF_CHAR = (", prefixed with: \"The attached image shows the character to draw: keep exactly the same "
            "character, face, outfit, colours, gear and weapon, but draw the poses, layout and camera described "
            "below, not the pose of the attached image.\"")
REF_NOTE = (", prefixed with: \"Match the style, camera angle, lighting and level of detail of the "
            "attached image, but draw the {what} described below.\" Use the attached image only as "
            "a style reference")

# Map environment groups every map needs ("--order mandatory"); the rest (civilian, tiles) come after.
MANDATORY_ENV = ["materials", "trees", "props", "smudges", "walls", "tech"]
LIMIT_EXIT = 75
# Lost connection to chatgpt.com: wait and retry (up to NETWORK_WAITS x 2 min in a row) instead of failing.
NETWORK_RE = re.compile(r"error sending request|connection failed|connection refused|dns error|network is unreachable", re.I)
NETWORK_WAITS = 15  # exit code for --stop-on-limit

# "429" only as a whole number: log timestamps like 15:48:58.742919Z contain it too.
LIMIT_RE = re.compile(r"rate limit|usage limit|too many requests|\b429\b|quota|try again (later|at)", re.I)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(time.strftime("%Y-%m-%d ") + line + "\n")


def parse_prompts(path):
    """Returns [{num, title, name, section, prompt}] from gemini-prompts.md."""
    items, section, cur = [], None, None
    lines = open(path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^## (.+)", line)
        if m:
            section = m.group(1).strip().lower()
        m = re.match(r"^### (\d+)\. (.+)", line)
        if m:
            cur = {"num": int(m.group(1)), "title": m.group(2).strip(), "section": section}
        m = re.match(r"^Save as: `([^`\s]+)", line)
        if m and cur:
            cur["name"] = os.path.splitext(m.group(1))[0]
        m = re.match(r"^Grid: (\d+)x(\d+) (\w+) (\d+):(\d+)", line)
        if m and cur:  # a sheet: several items in one grid image, cut apart by slice_sheet.py
            cur["grid"] = (int(m.group(1)), int(m.group(2)), m.group(3), (int(m.group(4)), int(m.group(5))))
        m = re.match(r"^Parts: (.+)", line)
        if m and cur:
            cur["parts"] = re.findall(r"`([^`]+)`", m.group(1))
        m = re.match(r"^Reference: `([^`]+)`", line)
        if m and cur:
            cur["layout_ref"] = os.path.join(HERE, "..", "..", m.group(1))
        if line.startswith("```") and cur and "name" in cur:
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            cur["prompt"] = "\n".join(body).strip()
            if section in FOLDERS:
                items.append(cur)
            cur = None
        i += 1
    return items


def run_codex(prompt, ref, timeout, what="building", layout=False):
    """Runs one non-interactive Codex turn. Returns (png_path or None, error text)."""
    work = tempfile.mkdtemp(prefix="rapx-img-")
    codex = find_codex()
    if not codex:
        return None, "codex CLI not found (ChatGPT app updating?)"
    cmd = [codex, "exec", "--skip-git-repo-check", "--json", "-s", "read-only",
           "-c", 'model_reasoning_effort="low"', "-C", work]
    if ref:
        cmd += ["-i", ref]
    note = (REF_CHAR if layout == "char" else REF_REPAINT if layout == "repaint" else REF_LAYOUT if layout
            else REF_NOTE.format(what=what))
    text = WRAPPER.format(prompt=prompt, ref=note if ref else "")
    try:
        proc = subprocess.run(cmd + ["-"], input=text, capture_output=True, text=True, timeout=timeout)
        out, err = proc.stdout, proc.stderr
    except OSError as e:
        out, err = "", "could not start codex: %s" % e
    except subprocess.TimeoutExpired as e:
        out, err = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
    finally:
        shutil.rmtree(work, ignore_errors=True)

    thread, messages = None, []
    for raw in out.splitlines():
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if ev.get("type") == "thread.started":
            thread = ev.get("thread_id")
        elif ev.get("type") in ("error", "turn.failed"):
            messages.append(json.dumps(ev))
        elif ev.get("type") == "item.completed" and ev.get("item", {}).get("type") == "agent_message":
            messages.append(ev["item"].get("text", ""))

    if thread:
        folder = os.path.join(GENERATED, thread)
        if os.path.isdir(folder):
            pngs = [os.path.join(folder, f) for f in os.listdir(folder)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
            if pngs:
                return max(pngs, key=os.path.getmtime), ""
    tail = "\n".join(messages[-3:]) + "\n" + "\n".join(
        l for l in err.splitlines()[-15:] if "token has expired" not in l)
    return None, tail.strip()


def group_of(it):
    name = it["parts"][0] if it.get("parts") else it["name"]
    return name.split("/")[0] if "/" in name else FOLDERS[it["section"]]


def outputs(it):
    """[(item name, output png)]: the sheet's parts, or the item itself."""
    return list(zip(it["parts"], it["part_dsts"])) if it.get("parts") else [(it["name"], it["dst"])]


def is_done(it):
    return all(os.path.exists(d) for _, d in outputs(it))


def write_track(path, items, todo_names, status, failed, stopped, cmd):
    """Writes the progress file (JSON) and a PROGRESS.md report next to it."""
    rows = []
    for it in items:
        for name, dst in outputs(it):
            if os.path.exists(dst):
                st = "done"
            elif it["name"] in failed:
                st = "failed"
            else:
                st = "pending"
            group = name.split("/")[0] if "/" in name else group_of(it)
            rows.append({"num": it["num"], "name": name, "title": it["title"], "group": group,
                         "tier": "mandatory" if group in MANDATORY_ENV else "optional", "status": st,
                         "image": it["name"], "dst": os.path.relpath(dst, os.path.dirname(path))})
    state = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "stopped": stopped, "resume": cmd, "items": rows}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(state, f, indent=1)
    os.replace(path + ".tmp", path)

    md = ["# Image generation progress", "",
          "Updated %s. Status: **%s**." % (state["updated"], stopped or "running"), "",
          "Resume (skips everything already saved, retries failures):", "", "```", cmd, "```", "",
          "| Tier | Group | Done | Failed | Pending | Total |", "|---|---|---|---|---|---|"]
    groups = []
    for r in rows:
        if (r["tier"], r["group"]) not in groups:
            groups.append((r["tier"], r["group"]))
    for tier, g in groups:
        rs = [r for r in rows if r["group"] == g]
        c = lambda s: sum(1 for r in rs if r["status"] == s)
        md.append("| %s | %s | %d | %d | %d | %d |" % (tier, g, c("done"), c("failed"), c("pending"), len(rs)))
    c = lambda s: sum(1 for r in rows if r["status"] == s)
    md.append("| | **all** | **%d** | **%d** | **%d** | **%d** |" % (c("done"), c("failed"), c("pending"), len(rows)))
    nxt = [r for r in rows if r["status"] != "done"][:10]
    if nxt:
        md += ["", "Next up:", ""] + ["- #%d %s (%s)" % (r["num"], r["name"], r["status"]) for r in nxt]
    fl = [r for r in rows if r["status"] == "failed"]
    if fl:
        md += ["", "Failed (retried on the next run):", ""] + ["- #%d %s" % (r["num"], r["name"]) for r in fl]
    with open(os.path.join(os.path.dirname(path), "PROGRESS.md"), "w") as f:
        f.write("\n".join(md) + "\n")


def cut(it, force=False):
    """Slices a saved sheet into its parts (only the missing ones unless force). Raises SliceError."""
    rows, cols, kind, aspect = it["grid"]
    cells = slice_sheet(it["dst"], rows, cols, kind, aspect)
    if len(cells) != len(it["parts"]):
        raise SliceError("%d cells for %d parts" % (len(cells), len(it["parts"])))
    for (name, dst), im in zip(outputs(it), cells):
        if force or not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            im.save(dst)
            log("    -> %s" % name)


def save(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if src.lower().endswith(".png"):
        shutil.copyfile(src, dst)
        return
    try:
        from PIL import Image
        Image.open(src).save(dst)
    except ImportError:
        subprocess.run(["sips", "-s", "format", "png", src, "--out", dst], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated Save-as names or numbers (e.g. weap,powr,12)")
    ap.add_argument("--from", dest="start", help="start at this Save-as name or number (e.g. 1tnk or 29)")
    ap.add_argument("--category", choices=sorted(set(FOLDERS.values())))
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--prompts", default=PROMPTS, help="prompt file (default gemini-prompts.md; e.g. jet-prompts.md)")
    ap.add_argument("--ref", help="style reference image to attach to every prompt (except the reference itself)")
    ap.add_argument("--force", action="store_true", help="regenerate files that already exist")
    ap.add_argument("--no-ref", action="store_true", help="don't attach the Construction Yard style image to buildings")
    ap.add_argument("--retries", type=int, default=3, help="attempts per image for non-limit errors")
    ap.add_argument("--limit-wait", type=int, default=20, help="minutes to wait when the usage limit is hit")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per image")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--order", help="comma-separated groups to run first (folder before the '/' in Save as), "
                    "or 'mandatory' for the map-environment essentials")
    ap.add_argument("--stop-on-limit", action="store_true",
                    help="exit (code %d) at the first usage limit instead of waiting it out" % LIMIT_EXIT)
    ap.add_argument("--track", help="progress JSON to keep up to date (PROGRESS.md is written next to it)")
    ap.add_argument("--max-fail-streak", type=int, default=3,
                    help="stop after this many images in a row fail (unrecognised limit / auth problem)")
    args = ap.parse_args()

    if not os.path.exists(CODEX):
        sys.exit("Codex CLI not found at %s (it ships with the ChatGPT desktop app)." % CODEX)

    prompts = args.prompts if os.path.isabs(args.prompts) else os.path.join(HERE, args.prompts)
    items = parse_prompts(prompts)
    if args.only:
        want = {w.strip() for w in args.only.split(",")}
        # "egypt" also selects every "egypt/<building>" (national building styles)
        items = [it for it in items if it["name"] in want or str(it["num"]) in want or it["name"].split("/")[0] in want
                 or any(p in want or p.split("/")[0] in want for p in it.get("parts", []))]
    if args.start:
        nums = [it["num"] for it in items if it["name"] == args.start or str(it["num"]) == args.start]
        if not nums:
            sys.exit("--from %s: no such prompt" % args.start)
        items = [it for it in items if it["num"] >= nums[0]]
    if args.category:
        items = [it for it in items if FOLDERS[it["section"]] == args.category]
    if args.order:
        order = MANDATORY_ENV if args.order == "mandatory" else [g.strip() for g in args.order.split(",")]
        rank = lambda it: order.index(group_of(it)) if group_of(it) in order else len(order)
        items.sort(key=lambda it: (rank(it), it["num"]))  # stable: file order inside a group
    for it in items:
        it["dst"] = os.path.join(args.out, FOLDERS[it["section"]], it["name"] + ".png")
        it["part_dsts"] = [os.path.join(args.out, FOLDERS[it["section"]], p + ".png") for p in it.get("parts", [])]
    todo = [it for it in items if args.force or not is_done(it)]

    if args.list:
        for it in items:
            mark = "run " if it in todo else "skip"
            print("%s %2d %-28s -> %s" % (mark, it["num"], it["title"][:28], it["dst"]))
            for name, dst in outputs(it) if it.get("parts") else []:
                print("        %s %s" % ("have" if os.path.exists(dst) else "new ", dst))
        return

    ref = None if args.no_ref else os.path.abspath(args.ref or STYLE_REF)
    if ref and not os.path.exists(ref):
        log("style reference %s missing, continuing without it" % ref)
        ref = None

    log("%d to generate (%d already done)" % (len(todo), len(items) - len(todo)))
    failed, status, streak, offline = [], {}, 0, 0
    track_cmd = "cd %s && python3 %s" % (HERE, " ".join(
        a if " " not in a else repr(a) for a in [os.path.basename(sys.argv[0])] + sys.argv[1:]))
    todo_names = {it["name"] for it in todo}

    def track(stopped=None):
        if args.track:
            write_track(os.path.abspath(args.track), items, todo_names, status, failed, stopped, track_cmd)

    track()
    for n, it in enumerate(todo, 1):
        if args.ref:
            use_ref = ref if os.path.abspath(it["dst"]) != ref else None
        else:
            use_ref = ref if it["section"] == "buildings" and it["name"] != "fact" else None
        what = ("building" if it["section"] == "buildings" else "aircraft" if FOLDERS[it["section"]] == "jets"
                else "texture" if it["section"] == "map textures"
                else "icon" if FOLDERS[it["section"]] == "cameos" else "object")
        attempt = 0
        while True:
            attempt += 1
            log("[%d/%d] %s (%s), attempt %d" % (n, len(todo), it["name"], it["title"], attempt))
            t0 = time.time()
            layout = False
            if not args.ref and it.get("layout_ref") and os.path.exists(it["layout_ref"]):
                use_ref = os.path.abspath(it["layout_ref"])
                layout = ("char" if it["section"] in ("infantry animations", "robot animations", "soldier views", "soldier views unarmed")
                          else "repaint" if it["section"] == "map style frames" else True)
            src, err = run_codex(it["prompt"], use_ref, args.timeout, what, layout)
            if src and it.get("parts"):
                save(src, it["dst"])
                try:
                    cut(it, args.force)
                except SliceError as e:
                    src, err = None, "sheet rejected: %s" % e
            elif src:
                save(src, it["dst"])
            if src:
                log("  saved %s (%.0fs)" % (it["dst"], time.time() - t0))
                status[it["name"]], streak, offline = "done", 0, 0
                track()
                break
            if LIMIT_RE.search(err) and args.stop_on_limit:
                why = next((l for l in err.splitlines() if LIMIT_RE.search(l)), "")
                log("  usage limit hit, stopping: %s" % why[:300])
                track("stopped: ChatGPT usage limit at %s (%s)" % (it["name"], time.strftime("%Y-%m-%d %H:%M")))
                sys.exit(LIMIT_EXIT)
            if LIMIT_RE.search(err):
                log("  usage limit hit, waiting %d min: %s" % (args.limit_wait, err.splitlines()[-1][:200] if err else ""))
                time.sleep(args.limit_wait * 60)
                attempt -= 1  # limits don't count as failed attempts
                continue
            if NETWORK_RE.search(err) and offline < NETWORK_WAITS:
                offline += 1
                log("  network down, waiting 2 min (%d/%d): %s" % (offline, NETWORK_WAITS, err.splitlines()[-1][:160]))
                time.sleep(120)
                attempt -= 1  # outages don't count as failed attempts
                continue
            log("  no image: %s" % (err[-500:] or "unknown error"))
            if attempt >= args.retries:
                failed.append(it["name"])
                streak += 1
                track()
                if args.max_fail_streak and streak >= args.max_fail_streak:
                    log("%d images in a row failed, stopping" % streak)
                    track("stopped: %d failures in a row at %s (%s)" % (streak, it["name"], time.strftime("%Y-%m-%d %H:%M")))
                    sys.exit(1)
                break
            time.sleep(30)

    track("finished: %d saved, %d failed (%s)" % (len(todo) - len(failed), len(failed), time.strftime("%Y-%m-%d %H:%M")))
    log("finished: %d saved, %d failed%s" % (len(todo) - len(failed), len(failed),
                                             (" (" + ", ".join(failed) + ")") if failed else ""))


if __name__ == "__main__":
    main()
