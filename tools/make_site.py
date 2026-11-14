#!/usr/bin/env python3
"""
Builds the data and images for the RAPX website (a static GitHub Pages site kept outside this repo).

- Exports the Extras catalogue with `./utility.sh --export-catalogue` (OpenRA.Mods.RAPX/UtilityCommands), so the
  site lists exactly the nations, units, stats and weapons the game does, and writes it as <site>/data/catalogue.js.
- Parses mods/rapx/CREDITS into <site>/data/credits.js for the Credits section.
- Copies each entry's catalogue picture (mods/rapx/bits/hd/catalogue/<image>.jpg, else the sidebar cameo) at web size
  to <site>/img/units/, the large lobby flags to <site>/img/flags/ and the README screenshots to <site>/img/shots/.

The page itself (index.html, style.css, app.js) is hand-written in the site folder; this script never touches it.

Run (engine built with `make`): python3 tools/make_site.py [SITE_DIR]   (default: ../rapx-site)
"""

import json
import os
import shutil
import subprocess
import sys
from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MOD = os.path.join(ROOT, "mods", "rapx")
SITE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "rapx-site"))

UNIT_SIZE = (480, 320)
SHOT_WIDTH = 1600

# Row order of uibits/px-flags-large*.png (px-flags-large.yaml, 60x40 per flag at 1x, 41 px apart)
FLAG_ROWS = ["england", "france", "germany", "spain", "turkey", "greece", "pakistan", "russia", "ukraine", "cuba",
             "india", "egypt", "china", "japan", "southkorea", "italy", "usa", "iran"]


def export_catalogue():
    out = os.path.join(SITE, "data", "catalogue.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([os.path.join(ROOT, "utility.sh"), "--export-catalogue", out], check=True, cwd=ROOT)
    with open(out) as f:
        data = json.load(f)
    os.remove(out)
    return data


def unit_picture(names):
    """The first candidate with catalogue art, else with a sidebar cameo; (image name, source path) or None."""
    for name in names:
        path = os.path.join(MOD, "bits", "hd", "catalogue", name + ".jpg")
        if os.path.exists(path):
            return name, path
    for name in names:
        path = os.path.join(MOD, "bits", "hd", "icons", name + "icon.png")
        if os.path.exists(path):
            return name, path
    return None


def write_units(data):
    out = os.path.join(SITE, "img", "units")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    done, missing = {}, []
    for e in data["entries"]:
        images = {}
        for nation, names in e.pop("images").items():
            pic = unit_picture(names)
            if pic is None:
                continue
            name, src = pic
            if name not in done:
                im = Image.open(src).convert("RGB")
                im = im.resize(UNIT_SIZE, Image.LANCZOS) if im.size[0] * 2 == im.size[1] * 3 else cover(im, UNIT_SIZE)
                im.save(os.path.join(out, name + ".jpg"), quality=82, optimize=True, progressive=True)
                done[name] = True
            images[nation] = name
        if not images:
            missing.append(e["id"])
        # Most entries look the same for every nation: store one default plus the nations that differ
        default = max(set(images.values()), key=list(images.values()).count) if images else None
        e["image"] = default
        e["imageBy"] = {n: i for n, i in images.items() if i != default}
    print(f"{len(done)} unit pictures, no picture for: {', '.join(missing) or 'none'}")


def cover(im, size):
    w, h = size
    scale = max(w / im.size[0], h / im.size[1])
    im = im.resize((round(im.size[0] * scale), round(im.size[1] * scale)), Image.LANCZOS)
    x, y = (im.size[0] - w) // 2, (im.size[1] - h) // 2
    return im.crop((x, y, x + w, y + h))


def write_flags(data):
    out = os.path.join(SITE, "img", "flags")
    os.makedirs(out, exist_ok=True)
    sheet = Image.open(os.path.join(MOD, "uibits", "px-flags-large-3x.png")).convert("RGBA")
    for n in data["nations"]:
        row = FLAG_ROWS.index(n["id"])
        sheet.crop((0, row * 41 * 3, 60 * 3, row * 41 * 3 + 40 * 3)).save(os.path.join(out, n["id"] + ".png"), optimize=True)


def write_shots():
    out = os.path.join(SITE, "img", "shots")
    os.makedirs(out, exist_ok=True)
    src = os.path.join(ROOT, "docs", "readme")
    for name in os.listdir(src):
        if not name.endswith(".jpg"):
            continue
        im = Image.open(os.path.join(src, name)).convert("RGB")
        if im.size[0] > SHOT_WIDTH:
            im = im.resize((SHOT_WIDTH, round(im.size[1] * SHOT_WIDTH / im.size[0])), Image.LANCZOS)
        im.save(os.path.join(out, name), quality=84, optimize=True, progressive=True)
    shutil.copy(os.path.join(MOD, "icon-2x.png"), os.path.join(SITE, "img", "icon.png"))


LICENCES = [  # (label, pattern in the entry text), first match wins
    ("Licence pending", r"licence to confirm"),
    ("CC0", r"CC0|No credit required"),
    ("CC BY-NC", r"NonCommercial"),
    ("Sketchfab Standard", r"Sketchfab Standard"),
    ("CC BY 3.0", r"Attribution 3\.0|by/3\.0"),
    ("CC BY 4.0", r"Attribution"),
]


def parse_credits():
    """mods/rapx/CREDITS as sections of entries: subject, the models with their links, artists, licence, changes."""
    import re
    lines = open(os.path.join(MOD, "CREDITS"), encoding="utf-8").read().splitlines()
    # The header (title, "Created by NAME (EMAIL)", "Built on ...") ends at the "Built on" line
    head = next(i for i, l in enumerate(lines) if l.startswith("Built on"))
    creator = next((re.match(r"Created by (.+?) \((.+?)\)", l) for l in lines[:head] if l.startswith("Created by")), None)
    sections, section, entry = [], None, None

    def finish():
        nonlocal entry
        if entry is not None:
            section["items"].append(entry)
            entry = None

    for i, line in enumerate(lines[head + 1:], head + 1):
        if not line.strip():
            continue
        if line.startswith("* "):
            finish()
            entry = [line[2:].strip()]
        elif line.startswith(" "):
            if entry is None or not lines[i - 1].strip():
                finish()
                entry = [line.strip()]
            else:
                entry.append(line.strip())
        else:
            finish()
            # Unindented text before a section's first entry is its intro paragraph; anything else starts a section
            if section is not None and not section["items"]:
                section["intro"] = (section["intro"] + " " + line.strip()).strip()
            else:
                section = {"title": re.sub(r"\s*\(.*\)$", "", line.strip()), "intro": "", "items": []}
                sections.append(section)
    finish()

    out = []
    for s in sections:
        nc = "NonCommercial" in s["intro"]
        items = []
        for raw in s["items"]:
            text = " ".join(raw)
            head, _, rest = text.partition(":")
            subject = head.strip() if rest and '"' not in head and "http" not in head else ""
            body = rest.strip() if subject else text
            models = [{"title": t, "url": u} for t, u in re.findall(r'"(.+?)"\s*\((https?://[^)\s]+)\)', body)]
            changes = re.search(r"Changes: (.+)$", body)
            artists = []
            credit = body.split("Changes:")[0].strip()
            for m in re.finditer(r'\bby (.+?)(?=, (?:both )?licensed|, used under|, and "| licensed|\. |\.$|$)', credit):
                names = re.sub(r"\s*\([^)]*\)", "", m.group(1))
                artists += [n.replace(" SketchFab", "").strip() for n in re.split(r",\s*|\s+and\s+", names) if n.strip()]
            licence = next((label for label, p in LICENCES if re.search(p, body)), "CC BY-NC" if nc else "")
            items.append({
                "subject": subject or (models[0]["title"] if models else s["title"]),
                "models": models,
                "artists": list(dict.fromkeys(artists)),
                "licence": licence,
                "changes": changes.group(1) if changes else "",
                # Entries that are not a model with a link (icons, sounds, notes) show their text instead
                "text": "" if models else re.sub(r"\s*\(https?://[^)]+\)", "", body).strip(),
            })
        out.append({"title": s["title"], "intro": s["intro"], "items": items})
    return {"creator": {"name": creator.group(1), "email": creator.group(2)} if creator else None, "sections": out}


def round_floats(o):
    if isinstance(o, float):
        return round(o, 2)
    if isinstance(o, list):
        return [round_floats(v) for v in o]
    if isinstance(o, dict):
        return {k: round_floats(v) for k, v in o.items()}
    return o


def main():
    data = export_catalogue()
    write_units(data)
    write_flags(data)
    write_shots()
    with open(os.path.join(SITE, "data", "catalogue.js"), "w") as f:
        f.write("// GENERATED by tools/make_site.py in the RAPX repo: do not edit\n")
        f.write("window.RAPX = " + json.dumps(round_floats(data), ensure_ascii=False, separators=(",", ":")) + ";\n")
    with open(os.path.join(SITE, "data", "credits.js"), "w") as f:
        f.write("// GENERATED by tools/make_site.py from mods/rapx/CREDITS: do not edit\n")
        f.write("window.RAPX_CREDITS = " + json.dumps(parse_credits(), ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"Site data written to {SITE}")


if __name__ == "__main__":
    main()
