#!/usr/bin/env python3
"""List every map-environment asset (terrain tiles + placeable map objects)
so each one can be replaced with a high-resolution render.

Writes docs/ENVIRONMENT-ASSETS.md and docs/environment-assets.csv.
Run from anywhere: python3 artsrc/env-inventory/make_inventory.py
"""
import csv
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / "mods/rapx"
TILESETS = ["TEMPERAT", "SNOW", "DESERT", "INTERIOR"]
TILESET_FILES = {"TEMPERAT": "temperat", "SNOW": "snow", "DESERT": "desert", "INTERIOR": "interior"}
TILE_EXT = {"TEMPERAT": "tem", "SNOW": "sno", "DESERT": "des", "INTERIOR": "int"}

# Map-editor categories that are part of the environment (not units / player buildings).
ENV_CATEGORIES = ["Tree", "Decoration", "Civilian building", "Tech building", "Wall", "Resource spawn"]
# Environment actors that the editor files under other categories / none.
EXTRA_ACTORS = {"CRATE", "MONEYCRATE", "HEALCRATE", "WCRATE", "SCRATE", "MINE", "GMINE", "RAILMINE",
                "MINV", "MINP"}


class Node:
    def __init__(self, key, value):
        self.key, self.value, self.children = key, value, []

    def get(self, key):
        for c in self.children:
            if c.key == key:
                return c
        return None


def parse_miniyaml(path):
    root = Node("", "")
    stack = [(-1, root)]
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip("\t"))
        key, _, value = line.strip().partition(":")
        node = Node(key.strip(), value.strip())
        while stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1].children.append(node)
        stack.append((depth, node))
    return root


def merge(dst, src):
    """dst/src: OrderedDict trait -> {field: value}. Handles -Trait: removals."""
    for trait, fields in src.items():
        if trait.startswith("-"):
            dst.pop(trait[1:], None)
            continue
        cur = dst.setdefault(trait, {})
        for k, v in fields.items():
            if k.startswith("-"):
                cur.pop(k[1:], None)
            else:
                cur[k] = v


def load_actors():
    defs = OrderedDict()
    for f in sorted((MOD / "rules").glob("*.yaml")):
        if f.name.startswith("campaign") or f.name.startswith("coop"):
            continue
        for top in parse_miniyaml(f).children:
            entry = defs.setdefault(top.key, {"file": f.name, "inherits": [], "traits": OrderedDict()})
            for c in top.children:
                if c.key.startswith("Inherits"):
                    entry["inherits"].append(c.value)
                else:
                    entry["traits"][c.key] = {g.key: g.value for g in c.children}
    cache = {}

    def resolve(name):
        if name in cache:
            return cache[name]
        d = defs.get(name)
        out = OrderedDict()
        if d:
            for parent in d["inherits"]:
                merge(out, resolve(parent))
            merge(out, d["traits"])
        cache[name] = out
        return out

    return defs, resolve


def load_fluent():
    names = {}
    for f in (MOD / "fluent").glob("*.ftl"):
        key = None
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([a-z0-9.\-]+)\s*=\s*(.*)$", line)
            if m:
                key = m.group(1)
                if m.group(2):
                    names[key] = m.group(2).strip()
            elif key and line.strip().startswith("."):
                sub, _, val = line.strip()[1:].partition("=")
                names[key + "." + sub.strip()] = val.strip()
    return names


def load_sequence_files():
    """image name -> {tileset: filename} for the first sequence of each image."""
    files = {}
    for f in sorted((MOD / "sequences").glob("*.yaml")):
        if f.name.startswith("hd-"):
            continue
        for top in parse_miniyaml(f).children:
            base, per = None, {}
            nodes = [top.get("Defaults")] + [c for c in top.children if c.key != "Defaults"]
            for n in nodes:
                if n is None:
                    continue
                fn = n.get("Filename")
                if fn and base is None:
                    base = fn.value
                tf = n.get("TilesetFilenames")
                if tf and not per:
                    per = {c.key: c.value for c in tf.children}
                if base:
                    break
            if base or per:
                files[top.key.lower()] = (base, per)
    return files


def hd_overrides():
    """Images that already have an HD replacement (sequences/hd-*.yaml)."""
    done = set()
    for f in (MOD / "sequences").glob("hd-*.yaml"):
        for top in parse_miniyaml(f).children:
            done.add(top.key.lower())
    return done


def tiles():
    rows = []
    for ts in TILESETS:
        root = parse_miniyaml(MOD / "tilesets" / f"{TILESET_FILES[ts]}.yaml")
        for t in root.get("Templates").children:
            terr = sorted({c.value for c in (t.get("Tiles").children if t.get("Tiles") else [])})
            rows.append({
                "tileset": ts,
                "id": t.get("Id").value,
                "image": t.get("Images").value,
                "size": t.get("Size").value.replace(",", "x"),
                "category": t.get("Categories").value if t.get("Categories") else "",
                "terrain": ", ".join(terr),
                "pickany": bool(t.get("PickAny")),
            })
    return rows


def actors():
    defs, resolve = load_actors()
    names = load_fluent()
    seqs = load_sequence_files()
    hd = hd_overrides()
    rows = []
    for name, d in defs.items():
        if name.startswith("^") or name.lower() != name and not name[0].isupper():
            continue
        t = resolve(name)
        med = t.get("MapEditorData", {})
        cat = med.get("Categories", "")
        if cat not in ENV_CATEGORIES and name not in EXTRA_ACTORS:
            continue
        if name.endswith(".Husk") and cat == "Husk" or name == "FLARE":
            continue
        tip = t.get("Tooltip", {}).get("Name") or t.get("Tooltip@SUMMER", {}).get("Name", "")
        image = (t.get("RenderSprites", {}).get("Image") or name).lower()
        base, per = seqs.get(image, (None, {}))
        tilesets = [ts for ts in TILESETS
                    if (not med.get("RequireTilesets") or ts in med["RequireTilesets"])
                    and ts not in med.get("ExcludeTilesets", "")]
        files = []
        for ts in tilesets:
            fn = per.get(ts, base)
            if fn and fn not in files:
                files.append(fn)
        dims = t.get("Building", {}).get("Dimensions", "")
        rows.append({
            "actor": name,
            "name": names.get(tip, names.get(tip + ".name", tip)) if tip else "",
            "category": cat or ("Crate" if "CRATE" in name else "Mine"),
            "size": dims.replace(",", "x"),
            "tilesets": ", ".join(tilesets),
            "files": ", ".join(files) or f"{image}.shp",
            "husk": t.get("SpawnActorOnDeath", {}).get("Actor", ""),
            "hd": "yes" if image in hd else "",
            "rules": d["file"],
        })
    return rows


def bridges():
    """Bridge actors: drawn with terrain templates, swapped as they take damage."""
    defs, resolve = load_actors()
    rows = []
    for name, d in defs.items():
        if "^Bridge" not in d["inherits"]:
            continue
        b = resolve(name).get("Bridge", {})
        tmpl = [b.get(k) for k in ("Template", "DamagedTemplate", "DestroyedTemplate",
                                   "DestroyedPlusNorthTemplate", "DestroyedPlusSouthTemplate",
                                   "DestroyedPlusBothTemplate") if b.get(k)]
        rows.append((name, ", ".join(tmpl)))
    return rows


def main():
    trows, arows = tiles(), actors()
    docs = ROOT / "docs"
    with open(docs / "environment-assets.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "tileset", "id/actor", "name", "category", "size_cells", "source_files", "notes"])
        for r in arows:
            notes = "; ".join(x for x in [f"husk {r['husk']}" if r["husk"] else "",
                                          "already HD" if r["hd"] else ""] if x)
            w.writerow(["object", r["tilesets"], r["actor"], r["name"], r["category"], r["size"], r["files"], notes])
        for r in trows:
            w.writerow(["tile", r["tileset"], r["id"], "", r["category"], r["size"], r["image"],
                        ("random variants; " if r["pickany"] else "") + "terrain: " + r["terrain"]])

    out = ["# Environment assets inventory", "",
           "Generated by `artsrc/env-inventory/make_inventory.py` (do not edit by hand).",
           "Spreadsheet version: `docs/environment-assets.csv`.", "",
           "Sizes are in map cells (1 cell = 24x24 px in the classic art).",
           "Shadows are baked into each classic sprite (shadow palette pixels), so a replacement",
           "image must include its own shadow.", ""]

    out += ["## 1. Placeable map objects", ""]
    bycat = defaultdict(list)
    for r in arows:
        bycat[r["category"]].append(r)
    for cat in sorted(bycat, key=lambda c: (ENV_CATEGORIES + ["Crate", "Mine"]).index(c)
                      if c in ENV_CATEGORIES + ["Crate", "Mine"] else 99):
        rs = bycat[cat]
        out += [f"### {cat} ({len(rs)})", "", "| Actor | Name | Cells | Tilesets | Source files | Notes |",
                "|---|---|---|---|---|---|"]
        for r in rs:
            notes = ", ".join(x for x in [f"burns into {r['husk']}" if r["husk"] else "",
                                          "already HD" if r["hd"] else ""] if x)
            out.append(f"| {r['actor']} | {r['name']} | {r['size']} | {r['tilesets']} | {r['files']} | {notes} |")
        out.append("")

    imgs = {}
    for r in trows:
        imgs.setdefault(r["id"], r["image"])
    out += ["### Bridges (actors drawn with Bridge terrain tiles)", "",
            "Each bridge swaps between these tile templates as it is damaged/destroyed;",
            "replace the template images listed in the Bridge tile category below.", "",
            "| Actor | Templates (intact, damaged, destroyed, ...) | Images |", "|---|---|---|"]
    for name, tmpl in bridges():
        ims = ", ".join(imgs.get(t.strip(), "?") for t in tmpl.split(",") if t.strip())
        out.append(f"| {name} | {tmpl} | {ims} |")
    out += ["| BRIDGEHUT / BRIDGEHUT.small | invisible repair huts (no art) | |", ""]

    out += ["### Smudges (drawn by the engine, not placed)", "",
            "| Sequence | Files | Notes |", "|---|---|---|",
            "| scorches | sc1-sc6 (.tem/.sno/.des) | burn marks, saved in maps by index |",
            "| craters | cr1-cr6 (.tem/.sno/.des) | shell craters, saved in maps by index |",
            "| scorch_flames / smoke_m | effect sprites | flames and smoke on fresh smudges |", ""]

    out += ["## 2. Terrain tiles", "",
            "Each template is one image made of `Size` cells. The same image name exists per tileset",
            "with the tileset's extension (.tem temperate, .sno snow, .des desert, .int interior).", ""]
    summary = defaultdict(lambda: defaultdict(int))
    for r in trows:
        summary[r["category"]][r["tileset"]] += 1
    out += ["| Category | " + " | ".join(TILESETS) + " |", "|---|" + "---|" * len(TILESETS)]
    for cat in sorted(summary):
        out.append(f"| {cat} | " + " | ".join(str(summary[cat].get(ts, "")) for ts in TILESETS) + " |")
    out.append(f"| **Total** | " + " | ".join(str(sum(1 for r in trows if r['tileset'] == ts)) for ts in TILESETS) + " |")
    out.append("")

    for ts in TILESETS:
        out += [f"### {ts}", ""]
        bc = defaultdict(list)
        for r in trows:
            if r["tileset"] == ts:
                bc[r["category"]].append(r)
        for cat in sorted(bc):
            out += [f"<details><summary>{cat} ({len(bc[cat])})</summary>", "",
                    "| Id | Image | Cells | Terrain types |", "|---|---|---|---|"]
            out += [f"| {r['id']} | {r['image']} | {r['size']} | {r['terrain']} |" for r in bc[cat]]
            out += ["", "</details>", ""]

    (docs / "ENVIRONMENT-ASSETS.md").write_text("\n".join(out))
    print(f"{len(arows)} objects, {len(trows)} tile templates")
    for cat, rs in bycat.items():
        print(f"  {cat}: {len(rs)}")


if __name__ == "__main__":
    main()
