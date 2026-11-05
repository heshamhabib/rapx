#!/usr/bin/env python3
"""
Generates artsrc/prompts/env-prompts.md: one ChatGPT image prompt per map-environment asset listed in
docs/ENVIRONMENT-ASSETS.md (trees, rocks, props, civilian/tech buildings, walls, crates, smudges,
bridges, debris tiles and seamless terrain materials).

Every prompt carries a `Reference:` line pointing at the classic sprite exported by
artsrc/env-inventory/export_classic.py. generate_images.py attaches it as a LAYOUT reference (same
object, footprint and composition, redrawn in high resolution).

  python3 artsrc/env-inventory/make_inventory.py      # inventory (docs/environment-assets.csv)
  python3 artsrc/env-inventory/export_classic.py      # classic reference sprites
  python3 artsrc/prompts/make_env_prompts.py          # this file -> env-prompts.md
  python3 artsrc/prompts/generate_images.py --prompts env-prompts.md --category env --only trees
                                                       # -> assets/env/trees/*.png

Edit the description tables below and re-run.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "env-prompts.md")
CSV = os.path.join(ROOT, "docs", "environment-assets.csv")
CLASSIC = "artsrc/env-inventory/classic"

CLIMATE = {  # tileset -> (save-name suffix, look of the world)
    "TEMPERAT": ("temperate", "temperate European summer: lush green foliage, healthy natural colours"),
    "SNOW": ("snow", "deep winter: the object is covered in a layer of fresh white snow and frost, cold bluish light"),
    "DESERT": ("desert", "arid North-African desert: sun-bleached, dusty, warm sandy tones"),
    "INTERIOR": ("interior", "inside a military underground bunker: artificial cold light"),
}
EXT_TS = {"tem": "TEMPERAT", "sno": "SNOW", "des": "DESERT", "int": "INTERIOR"}

VIEW = ("View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees "
        "from the south, no perspective distortion")
TOPDOWN = "View: straight top-down orthographic view, camera pointing straight down, no perspective"
QUALITY = ("Ultra high resolution, photorealistic, highly detailed physically based materials, crisp and sharp, "
           "subtle ambient occlusion, no painterly blur")
SHADOW = ("Lighting: sun from the top-left; the object casts a clearly visible soft dark shadow onto the "
          "background, falling to the bottom-right")
MAGENTA = ("Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, "
           "no terrain base, no text, no labels, no logo, no watermark, no border")
NO_GREEN_KEY = "Do not use pure bright green (#00FF00) anywhere."
TWO_UP = ("showing the same {what} twice, side by side in one wide image: LEFT half = {left}, RIGHT half = {right}. "
          "Both copies have exactly the same size, angle and position within their half, each centred in its half "
          "with a clear gap of empty background between them; nothing crosses the middle; no dividing line")

# ---------------------------------------------------------------- descriptions (from the classic sprites)
TREES = {
    "t01": "a tall slender spruce with drooping branches",
    "t02": "a dense, perfectly conical fir tree",
    "t03": "a thin young birch with a straight pale trunk and sparse light foliage",
    "t04": "a small saguaro-style cactus with two short arms",
    "t05": "a broad conical spruce, full and dense",
    "t06": "a medium spruce with a slightly ragged outline",
    "t07": "a slim spruce with layered branches",
    "t08": "a small young fir sapling next to a low bush",
    "t09": "a tall single-stem cactus with one arm",
    "t10": "a large old oak with a wide round crown and a thick trunk",
    "t11": "a large round broadleaf tree (lime / linden) with a dense crown",
    "t12": "a slender young broadleaf tree with a small bush and a rock at its foot",
    "t13": "a round maple tree with a dense crown on a short trunk",
    "t14": "a bushy broadleaf tree with a low wide crown and a bush beside it",
    "t15": "a very wide, bushy broadleaf tree, almost a big shrub",
    "t16": "a medium spruce with a pointed top",
    "t17": "a thin young deciduous tree with a narrow open crown",
    "tc01": "a tight clump of three spruces of different heights",
    "tc02": "a dense cluster of five or six firs and spruces of mixed heights",
    "tc03": "a loose scattered group of eight to ten small young firs and saplings",
    "tc04": "a large group of six or seven tall firs spread over the area",
    "tc05": "a mixed grove: one large round oak, several firs, bushes and a boulder",
}
DESERT_TREES = {  # trees whose desert version is a different plant
    "t08": "a low flat-topped acacia tree with a sparse dusty olive-brown crown",
    "tc01": "a large umbrella-shaped acacia tree with a wide sparse dusty crown and a twisted trunk",
}

ROCKS = {
    "rock1": "a single large weathered sandstone boulder",
    "rock2": "a low ridge of jagged sandstone rocks",
    "rock3": "a tall wind-eroded hoodoo rock pillar with a flat cap stone, on a rocky base",
    "rock4": "a small pointed sandstone rock",
    "rock5": "a small rounded sandstone boulder",
    "rock6": "a large tall sandstone butte with a smaller rock beside it",
    "rock7": "a long low sandstone ridge stretching across the whole width",
}
ICE = {
    "ice01": "a large cluster of cracked ice floes, one big slab broken into several pieces",
    "ice02": "a long narrow ice floe with a few small chunks",
    "ice03": "a long low flat ice floe with small chunks breaking off",
    "ice04": "three or four small ice floes",
    "ice05": "a single medium triangular ice floe",
}
PROPS = {
    "barl": "a single rusty steel oil drum with hazard markings (explosive barrel)",
    "brl3": "a group of three rusty steel oil drums with hazard markings (explosive barrels)",
    "ammobox1": "a wide open wooden military ammunition crate full of shells",
    "ammobox2": "a tall narrow stack of military ammunition crates",
    "ammobox3": "a square military ammunition crate with stencilled markings and visible shells",
    "utilpol1": "a tall wooden utility pole with a cross-arm and insulators",
    "utilpol2": "a tall wooden utility pole with a T-shaped cross-arm and a transformer",
    "tanktrap1": "a steel Czech hedgehog anti-tank obstacle made of three crossed girders",
    "tanktrap2": "a large rusty Czech hedgehog anti-tank obstacle with a coil of barbed wire",
    "ctflag": "a flag on a tall wooden pole, the cloth waving to the right",
}
BOXES = {f"boxes0{n}": d for n, d in enumerate([
    "a stack of wooden shipping crates", "a single large wooden crate", "two wooden crates side by side",
    "a pallet with cardboard boxes wrapped in plastic", "a stack of steel ammo cases",
    "a pile of sandbags and a crate", "an open crate with supplies spilling out",
    "a stack of fuel jerrycans on a pallet", "a large crate covered with a tarpaulin"], 1)}

CIVILIAN = {
    "v01": "a white village church with a tall pointed steeple, slate roof and a small graveyard path",
    "v02": "two attached European farmhouses with ochre walls and thatched roofs",
    "v03": "a large European farmhouse with an orange haystack and a smaller house beside it",
    "v04": "a white two-storey European house with a grey roof and a chimney",
    "v05": "a small red farmhouse and a stone shed on a dirt yard",
    "v06": "a big red wooden barn with a curved roof, a fence and a hay wagon",
    "v07": "a long stone cottage with a wooden fence",
    "v08": "a small grey stone hut",
    "v09": "a small yellow cottage with a thatched roof",
    "v10": "a small red-roofed stone house with a chimney",
    "v11": "a small red-roofed shed built into a mound",
    "v20": "a flat-roofed North-African adobe house with a smaller house and crates",
    "v21": "a mud-brick house with a small well and a pile of stones",
    "v22": "a whitewashed flat-roofed house with a low wall",
    "v23": "a small stone well with a few clay pots",
    "v24": "a two-storey white adobe house with a water well",
    "v25": "a whitewashed desert church with a tall bell tower",
    "v26": "a row of two connected flat-roofed adobe houses",
    "v27": "a tall square white stone tower house",
    "v28": "a small adobe house with a cart",
    "v29": "a small mud-brick hut",
    "v30": "a long flat-roofed adobe house with a cart",
    "v31": "two small round mud huts with clay jars",
    "v32": "two round mud-brick huts with straw roofs",
    "v33": "a cluster of three round mud huts and a cart",
    "v34": "a single round mud hut with a straw roof",
    "v35": "a single round mud hut with a dark doorway",
    "v36": "a small round mud hut, partly broken",
    "v37": "a large sandstone warehouse with an arched front, a car park and a strip of irrigated lawn",
    "rushouse": "a grey Soviet five-storey concrete apartment block (khrushchyovka)",
    "asianhut": "a small East-Asian wooden house with a red tiled roof",
    "snowhut": "a wooden log cabin with a snow-covered roof, lit windows and a smoking chimney",
    "lhus": "a white and red striped stone lighthouse with a lantern room on top",
    "windmill": "an old wooden windmill with four large sails",
    "v19": "an oil pumpjack (nodding donkey) on a concrete pad",
    "railmine": "an abandoned mine entrance with a wooden headframe, rusty mine cart and rails leading out",
}
FIELDS = {  # flat field / haystack objects (no damaged version)
    "v12": ("two round haystacks", "two snow-covered igloos made of ice blocks"),
    "v13": ("a single round haystack", "a single igloo made of ice blocks"),
    "v14": ("a square field of ripe orange-gold wheat", None),
    "v15": ("a square freshly ploughed brown field", None),
    "v16": ("a square field of tall golden corn in rows", None),
    "v17": ("a square field of dark green potato plants in rows", None),
    "v18": ("a square field of leafy vegetables in rows", None),
    "rice": ("a square flooded rice paddy with bright green rice shoots in water", None),
}
TECH = {
    "fcom": "a Forward Command post: a fortified sand-coloured bunker with a sloped armoured front, blue lit windows and stairs",
    "miss": "a Communications Center: three large silver domes on a curved concrete base with gold trim",
    "bio": "a Biological Research Lab: a white laboratory with a domed containment tank, chimneys and yellow chemical tanks",
    "oilb": "an Oil Derrick: a steel lattice drilling tower beside two round yellow oil storage tanks on a concrete pad",
}
WALLS = {
    "cycl": "chain-link barrier: steel posts with chain-link fence panels and a concrete footing",
    "barb": "barbed-wire fence: wooden posts strung with coils of razor wire",
    "wood": "wooden fence: rustic split-rail farm fence with wooden posts",
}
CRATES = {
    "wcrate": "a reinforced wooden supply crate with metal corners and stencilled markings",
    "scrate": "a heavy steel supply crate with yellow hazard edges and a glowing indicator light",
}

# ---------------------------------------------------------------- seamless terrain materials
MATERIALS = {
    "TEMPERAT": {
        "clear": "short green meadow grass with small patches of clover and bare soil",
        "rough": "rough uneven ground: patchy grass, stones, gravel and bare dirt",
        "road": "a worn dirt road surface: compacted brown earth with tyre ruts and small stones",
        "cliff": "a vertical grey granite cliff face with cracks, ledges and moss",
        "beach": "wet and dry coarse sand with small pebbles and shells",
        "water": "deep dark blue-green sea water with gentle small waves",
        "river": "shallow clear river water flowing over pebbles",
    },
    "SNOW": {
        "clear": "fresh packed snow with a few blades of frozen grass poking through",
        "rough": "rough frozen ground: snow, ice, exposed rocks and frozen dirt",
        "road": "a snowy road with packed snow, slush and dark tyre tracks",
        "cliff": "a vertical dark grey rock cliff face with snow on the ledges and icicles",
        "beach": "an icy frozen shoreline of grey pebbles, frost and snow",
        "water": "cold deep dark blue Arctic sea water with small floating ice crystals",
        "river": "a cold shallow river, dark water over grey stones with ice at the edges",
    },
    "DESERT": {
        "clear": "fine wind-rippled desert sand with small stones",
        "rough": "rough rocky desert: gravel, cracked dry earth and scattered stones",
        "road": "a dusty desert track: compacted sand with tyre ruts",
        "cliff": "a vertical layered red-orange sandstone cliff face",
        "beach": "a sandy shoreline with dry and wet sand",
        "water": "warm turquoise sea water with gentle small waves",
        "river": "a shallow muddy oasis river over sand",
    },
    "INTERIOR": {
        "floor": "a worn grey concrete bunker floor with painted yellow safety lines and stains",
        "floor-metal": "a steel diamond-plate floor with bolts and scuffs",
        "wall": "a thick bunker wall seen from above: concrete with steel reinforcement and pipes along the top",
    },
}

# ---------------------------------------------------------------- prompt builders


def ref(ts, name):
    p = f"{CLASSIC}/{ts}/{name}.png"
    return p if os.path.exists(os.path.join(ROOT, p)) else None


def footprint(size):
    w, h = size.split("x")
    return f"Its base covers a {w} x {h} square-tile footprint (width {w}, depth {h}) on the map"


def tree_prompt(desc, ts, size):
    _, look = CLIMATE[ts]
    burnt = ("the exact same tree after a fire: completely burnt, charred black trunk and bare blackened branches, "
             "no leaves" + (", a little snow on the branches" if ts == "SNOW" else ""))
    return (
        "Game asset sheet for a top-down real-time strategy game, "
        + TWO_UP.format(what="tree", left="the living tree", right=burnt) + ". "
        + f"The tree: {desc}. Setting: {look}. {VIEW}, the whole tree visible. {footprint(size)}. "
        + f"{QUALITY}. {SHADOW}. {NO_GREEN_KEY} {MAGENTA}. Wide image, aspect ratio 2:1.")


def object_prompt(desc, ts, size, extra=""):
    _, look = CLIMATE[ts]
    return (f"Game asset for a top-down real-time strategy game: a single map object, {desc}. "
            f"Setting: {look}. {VIEW}, centred, the whole object visible. {footprint(size)}. {extra}"
            f"{QUALITY}. {SHADOW}. {NO_GREEN_KEY} {MAGENTA}. Square image.")


def building_prompt(desc, ts, size):
    _, look = CLIMATE[ts]
    damaged = ("the exact same building heavily battle-damaged: scorch marks, broken windows, holes in the roof, "
               "cracked walls, rubble and small fires; still standing and clearly the same building")
    return (
        "Game asset sheet for a top-down real-time strategy game, "
        + TWO_UP.format(what="building", left="the building intact", right=damaged) + ". "
        + f"The building: {desc}. Setting: {look}. {VIEW}, the front faces the bottom of the image. "
        + f"{footprint(size)}. Realistic modern-day civilian architecture with believable wear and grime. "
        + f"{QUALITY}. {SHADOW}. {NO_GREEN_KEY} {MAGENTA}. Wide image, aspect ratio 2:1.")


def wall_prompt(desc):
    return ("Game asset sheet for a top-down real-time strategy game: three pieces of the same wall in one wide image, "
            "left to right with clear gaps: (1) a single standalone post / end piece, (2) a straight section running "
            "left-right (east-west) that fills exactly one map tile width, (3) a straight section running away from the "
            f"camera (north-south) that fills exactly one map tile depth. The wall: {desc}. Neutral military look, "
            f"works in any climate. {VIEW}. {QUALITY}. {SHADOW}. {NO_GREEN_KEY} {MAGENTA}. Wide image, aspect ratio 3:1.")


def smudge_prompt(kind, ts):
    _, look = CLIMATE[ts]
    what = ("scorch marks: blackened burnt ground with soot, ash and charred grass, different shapes and sizes"
            if kind == "scorch" else
            "shell craters: blast craters dug into the ground with a dark centre, a raised rim of thrown-up earth "
            "and scattered clods, different sizes")
    return (f"Game decal sheet for a top-down real-time strategy game: six different {what}, arranged in a 3 x 2 grid "
            f"with clear gaps between them. Ground type: {look}. {TOPDOWN}. Each decal fits inside one square map "
            f"tile, with an irregular natural outline (no soft fade into the background). {QUALITY}. No shadows "
            f"outside the decals. {NO_GREEN_KEY} {MAGENTA}. Wide image, aspect ratio 3:2.")


def tile_prompt(cat, image, ts, size):
    _, look = CLIMATE[ts]
    w, h = size.split("x")
    kind = {"Bridge": "a bridge terrain tile: the bridge together with the water, river banks and ground "
                      "around it, exactly as laid out in the reference",
            "Debris": "a ground terrain tile with natural features on it (rocks, rubble, mounds or wreckage) "
                      "exactly as laid out in the reference"}[cat]
    state = ""
    stem = image.rsplit(".", 1)[0]
    if cat == "Bridge":
        if stem.endswith("d") or stem.endswith("c") or stem[-1] in "ef" and stem.startswith("br3"):
            state = " The bridge is destroyed: collapsed spans, broken stonework and rubble in the water. "
        elif stem.endswith("h") or stem.endswith("b"):
            state = " The bridge is badly damaged: cracked deck, craters and broken railings, but still standing. "
    return (f"Terrain tile for a top-down real-time strategy game: {kind}.{state} Setting: {look}. "
            f"The image is a grid of {w} x {h} square map tiles; paint the full rectangle edge to edge. Keep the "
            f"positions of water, banks, roads and the bridge exactly where the reference has them, so the edges "
            f"join the neighbouring terrain tiles. {VIEW}. {QUALITY}. Sun from the top-left, short soft shadows to "
            f"the bottom-right. No text, no labels, no watermark, no border. Aspect ratio {w}:{h}.")


def material_prompt(desc, ts):
    _, look = CLIMATE[ts]
    return (f"Seamless tileable ground texture for a top-down real-time strategy game: {desc}. Setting: {look}. "
            f"{TOPDOWN}. Even, flat lighting with very soft sun from the top-left, no strong shadows, no vignette, "
            f"no single dominant feature. The texture must tile seamlessly on all four edges. {QUALITY}. "
            f"No text, no watermark, no border. Square image.")


# ---------------------------------------------------------------- sheets (several items per image)
# Each image request counts against the ChatGPT usage limit, so env-sheets.md packs related items into one
# grid image; generate_images.py cuts it back into the same per-item files (slice_sheet.py).
SHEETS_OUT = os.path.join(HERE, "env-sheets.md")
SHEET_REFS = "artsrc/env-inventory/sheets"
REF_LONG_SIDE = 1024

SHEET_RULES = {  # kind -> (plural, rule for every cell)
    "tree2": ("trees", "Every cell shows one tree twice side by side: LEFT = the living tree, RIGHT = the exact same tree "
              "after a fire: completely burnt, charred black trunk and bare blackened branches, no leaves. Both copies in "
              "a cell have exactly the same size, angle and position, with empty background between them."),
    "bld2": ("buildings", "Every cell shows one building twice side by side: LEFT = the building intact, RIGHT = the exact "
             "same building heavily battle-damaged: scorch marks, broken windows, holes in the roof, cracked walls, rubble "
             "and small fires; still standing and clearly the same building. Both copies in a cell have exactly the same "
             "size, angle and position, with empty background between them. The front of every building faces the bottom "
             "of the image. Realistic modern-day civilian architecture with believable wear and grime."),
    "obj": ("map objects", "Every cell holds one single map object, centred in its cell, the whole object visible."),
    "wall3": ("wall sets", "Every cell holds three pieces of the same wall, left to right with clear gaps: (1) a single "
              "standalone post / end piece, (2) a straight section running left-right (east-west) that fills exactly one "
              "map tile width, (3) a straight section running away from the camera (north-south) that fills exactly one "
              "map tile depth. Neutral military look, works in any climate."),
    "smudge": ("decal sets", "Every cell holds six different ground decals in a 3 x 2 sub-grid with clear gaps; each decal "
               "fits inside one square map tile, with an irregular natural outline (no soft fade into the background)."),
    "tile": ("terrain tiles", "Every cell is one terrain tile: paint the cell's full rectangle edge to edge with terrain (no "
             "magenta inside a tile) and keep water, banks, roads and features exactly where the reference has them, so "
             "the edges join the neighbouring terrain tiles."),
}
GRID_SIZES = (9, 6, 4, 3, 2, 1)


def it(title, name, reference, prompt, kind="single", cell="", aspect=(1, 1), gkey=None, maxk=1, refs=None):
    return {"title": title, "name": name, "ref": reference, "prompt": prompt, "kind": kind, "cell": cell,
            "aspect": aspect, "gkey": gkey or name, "maxk": maxk, "refs": refs}


def collect():
    """Returns [(section title, note, [item])] for every map-environment asset."""
    rows = list(csv.DictReader(open(CSV)))
    objects = {r["id/actor"].lower(): r for r in rows if r["kind"] == "object"}
    items = []

    def climates(actor):
        r = objects[actor]
        return [EXT_TS.get(f.rsplit(".", 1)[-1], "TEMPERAT") for f in r["source_files"].split(", ")]

    def cell(desc, ts, size, extra=""):
        return f"{desc}. Setting: {CLIMATE[ts][1]}. {footprint(size)}.{(' ' + extra.strip()) if extra else ''}"

    # trees
    out = []
    for t, desc in TREES.items():
        for ts in climates(t):
            d = DESERT_TREES.get(t, desc) if ts == "DESERT" else desc
            suf, size = CLIMATE[ts][0], objects[t]["size_cells"]
            out.append(it(f"Tree {t.upper()} ({suf})", f"trees/{t}-{suf}", ref(ts, t), tree_prompt(d, ts, size),
                          "tree2", cell(d, ts, size), (2, 1), ("tree", t), 3))
    items.append(("Trees", "Each image: living tree (left) + burnt husk (right). The burnt half replaces the `.Husk` actor.", out))

    # rocks, ice, props, boxes
    out = []
    for group, table in (("Rock", ROCKS), ("Ice floe", ICE)):
        for a, desc in table.items():
            ts, size = climates(a)[0], objects[a]["size_cells"]
            extra = "The ice floats on water, but draw only the ice. " if group == "Ice floe" else ""
            out.append(it(f"{group} {a.upper()}", f"props/{a}", ref(ts, a), object_prompt(desc, ts, size, extra),
                          "obj", cell(desc, ts, size, extra), (1, 1), ("obj", group), 4))
    for a, desc in {**PROPS, **BOXES}.items():
        size, extra = objects[a]["size_cells"] or "1x1", "Neutral look that works in any climate. "
        out.append(it(a.upper(), f"props/{a}", ref("TEMPERAT", a) or ref("INTERIOR", a),
                      object_prompt(desc, "TEMPERAT", size, extra),
                      "obj", cell(desc, "TEMPERAT", size, extra), (1, 1), ("obj", "props"), 4))
    items.append(("Rocks, ice and props", "", out))

    # civilian buildings
    out = []
    for a, desc in CIVILIAN.items():
        cl = climates(a)
        for ts in cl:
            suf, size = CLIMATE[ts][0], objects[a]["size_cells"]
            name = f"civilian/{a}" + ("" if len(cl) == 1 else f"-{suf}")
            # every climate of a building on one sheet (consistent look); single-climate ones in pairs
            gkey, maxk = (("bld", a), 3) if len(cl) > 1 else (("bld", "single"), 2)
            out.append(it(f"{a.upper()} ({suf})", name, ref(ts, a), building_prompt(desc, ts, size),
                          "bld2", cell(desc, ts, size), (2, 1), gkey, maxk))
    for a, (summer, winter) in FIELDS.items():
        for ts in climates(a):
            suf, size = CLIMATE[ts][0], objects[a]["size_cells"]
            desc = winter if ts == "SNOW" and winter else summer
            if ts == "SNOW" and not winter:
                desc = summer.replace("a square", "a square snow-covered").replace("ripe ", "").replace("tall ", "")
            name = f"civilian/{a}" + ("" if len(climates(a)) == 1 else f"-{suf}")
            extra = "Seen from above it fills the tile; keep the edges straight. " if "field" in desc else ""
            out.append(it(f"{a.upper()} ({suf})", name, ref(ts, a), object_prompt(desc, ts, size, extra),
                          "obj", cell(desc, ts, size, extra), (1, 1), ("obj", "fields"), 4))
    items.append(("Civilian buildings", "Each building image: intact (left) + damaged (right). Fields and haystacks are single images.", out))

    # tech buildings, walls, crates, gem mine
    out = []
    for a, desc in TECH.items():
        size = objects[a]["size_cells"]
        out.append(it(a.upper(), f"tech/{a}", ref("TEMPERAT", a), building_prompt(desc, "TEMPERAT", size),
                      "bld2", cell(desc, "TEMPERAT", size), (2, 1), ("bld", "tech"), 2))
    for a, desc in WALLS.items():
        out.append(it(f"Wall {a.upper()}", f"walls/{a}", ref("TEMPERAT", a), wall_prompt(desc),
                      "wall3", f"{desc}.", (3, 1), ("wall",), 3))
    for a, desc in CRATES.items():
        out.append(it(f"Crate {a.upper()}", f"props/{a}", ref("TEMPERAT", a), object_prompt(desc, "TEMPERAT", "1x1"),
                      "obj", cell(desc, "TEMPERAT", "1x1"), (1, 1), ("obj", "crates"), 2))
    gem = ("a gem mine: a rocky mound split open with clusters of glowing purple, red and blue gem crystals "
           "growing out of it")
    for ts in ("TEMPERAT", "SNOW", "DESERT"):
        suf = CLIMATE[ts][0]
        out.append(it(f"Gem mine ({suf})", f"props/gmine-{suf}", ref(ts, "gmine"), object_prompt(gem, ts, "1x1"),
                      "obj", cell(gem, ts, "1x1"), (1, 1), ("obj", "gmine"), 3))
    items.append(("Tech buildings, walls, crates and mines",
                  "Walls: the three pieces are composed into all 16 connection shapes by the pipeline.", out))

    # smudges
    out = []
    for ts in ("TEMPERAT", "SNOW", "DESERT"):
        suf = CLIMATE[ts][0]
        for kind, prefix in (("scorch", "sc"), ("crater", "cr")):
            what = smudge_prompt(kind, ts).split("six different ", 1)[1].split(", arranged", 1)[0]
            out.append(it(f"{kind.title()} marks ({suf})", f"smudges/{kind}-{suf}", ref(ts, prefix + "1"),
                          smudge_prompt(kind, ts), "smudge", f"six {what}. Ground type: {CLIMATE[ts][1]}.",
                          (3, 2), ("smudge", ts), 2, [ref(ts, f"{prefix}{n}") for n in range(1, 7)]))
    items.append(("Smudges", "Six variants per sheet (sc1-sc6 / cr1-cr6), cut apart by the pipeline.", out))

    # bridge + debris tiles (bridges stay one per image: their edges must line up exactly)
    for cat, title in (("Bridge", "Bridge tiles"), ("Debris", "Debris tiles")):
        out = []
        for r in rows:
            if r["kind"] != "tile" or r["category"] != cat:
                continue
            ts, image, size = r["tileset"], r["source_files"], r["size_cells"]
            stem = image.rsplit(".", 1)[0]
            name = f"tiles/{ts.lower()}/{stem}"
            if any(o["name"] == name for o in out):
                continue
            w, h = (int(v) for v in size.split("x"))
            prompt = tile_prompt(cat, image, ts, size)
            if cat == "Bridge":
                out.append(it(f"{stem} {size} ({CLIMATE[ts][0]})", name, ref(ts, stem), prompt))
            else:
                maxk = 9 if w * h == 1 else 6 if w * h <= 2 else 4 if w * h <= 6 else 2
                c = (f"a ground terrain tile of {w} x {h} map tiles with natural features on it (rocks, rubble, mounds "
                     f"or wreckage) exactly as laid out in the reference. Setting: {CLIMATE[ts][1]}.")
                out.append(it(f"{stem} {size} ({CLIMATE[ts][0]})", name, ref(ts, stem), prompt,
                              "tile", c, (w, h), ("tile", ts, size), maxk))
        note = ("Full tiles including water and banks. Transparent cells of the reference are cut away again "
                "by the pipeline, so paint the whole rectangle.")
        items.append((title, note, out))

    # materials
    out = []
    for ts, mats in MATERIALS.items():
        suf = CLIMATE[ts][0]
        for m, desc in mats.items():
            out.append(it(f"{m} ({suf})", f"materials/{suf}-{m}", None, material_prompt(desc, ts)))
    items.append(("Terrain materials",
                  "Roads, cliffs, beaches, rivers, shores and interior floors are ~800 edge-matched tiles. Generating each "
                  "one separately would not line up at the seams, so they are re-textured from these seamless materials, "
                  "using the classic tiles as masks.", out))
    return items


def grid_for(k, aspect):
    """rows x cols for k cells of the given aspect, keeping the whole sheet as close to square as possible."""
    aw, ah = aspect
    pairs = [(r, k // r) for r in range(1, k + 1) if k % r == 0]
    return min(pairs, key=lambda rc: (abs(math.log(rc[1] * aw / (rc[0] * ah))), -rc[1]))


def sheet_ratio(k, aspect):
    rows, cols = grid_for(k, aspect)
    return cols * aspect[0] / (rows * aspect[1])


def chunk(group, maxk):
    """Splits a list into evenly sized chunks whose sizes have a clean grid (GRID_SIZES) no wider or taller
    than 2:1 (the widest shape ChatGPT has delivered so far)."""
    out, rest = [], list(group)
    aspect = group[0]["aspect"]
    while rest:
        n = math.ceil(len(rest) / maxk)
        size = next(s for s in GRID_SIZES if s <= min(maxk, math.ceil(len(rest) / n))
                    and (s == 1 or 0.5 <= sheet_ratio(s, aspect) <= 2))
        out.append(rest[:size])
        rest = rest[size:]
    return out


def sheet_prompt(parts, rows, cols):
    kind = parts[0]["kind"]
    plural, rule = SHEET_RULES[kind]
    aw, ah = parts[0]["aspect"]
    g = math.gcd(cols * aw, rows * ah)
    ratio = f"{cols * aw // g}:{rows * ah // g}"
    cells = []
    for n, p in enumerate(parts):
        r, c = divmod(n, cols)
        where = f"row {r + 1}, column {c + 1}" if rows > 1 and cols > 1 else f"row {r + 1}" if cols == 1 else f"column {c + 1}"
        cells.append(f"Cell {n + 1} ({where}): {p['cell']}")
    head = (f"Game asset sheet for a top-down real-time strategy game: {len(parts)} separate {plural}, laid out in a grid "
            f"of {rows} row{'s' if rows > 1 else ''} by {cols} column{'s' if cols > 1 else ''} of equal-size cells, "
            "numbered left to right, top to bottom. Wide clear gaps of empty magenta background separate the cells; "
            "nothing crosses from one cell into another (shadows included); no dividing lines, no numbers, no labels. "
            "The attached reference image shows the same grid: draw each cell's subject where the reference has it, at "
            f"the same relative size. {rule}")
    if kind == "tile":
        tail = (f"All cells share one camera and one scale: {VIEW}. {QUALITY}. Sun from the top-left, short soft shadows "
                f"to the bottom-right. {NO_GREEN_KEY} The gaps between the tiles and the margin around them are flat "
                f"solid magenta (#FF00FF); no text, no watermark, no border. Aspect ratio {ratio}.")
    elif kind == "smudge":
        tail = (f"{TOPDOWN}. {QUALITY}. No shadows outside the decals. {NO_GREEN_KEY} {MAGENTA}. Aspect ratio {ratio}.")
    else:
        tail = (f"All cells share one camera and one scale (one map tile is the same size in every cell): {VIEW}. "
                f"{QUALITY}. {SHADOW}, staying inside its own cell. {NO_GREEN_KEY} {MAGENTA}. Aspect ratio {ratio}.")
    return "\n\n".join([head] + cells + [tail])


def sheet_reference(parts, rows, cols, path):
    """The classic sprites laid out in the sheet's grid on magenta, all at one scale (relative sizes stay true)."""
    from PIL import Image
    kind = parts[0]["kind"]
    aw, ah = parts[0]["aspect"]
    unit = REF_LONG_SIDE / max(cols * aw, rows * ah)
    cw, ch = aw * unit, ah * unit
    sheet = Image.new("RGB", (round(cols * cw), round(rows * ch)), (255, 0, 255))
    slots = []  # (sprite path, x, y, w, h) boxes to fit a sprite into
    for n, p in enumerate(parts):
        r, c = divmod(n, cols)
        x0, y0 = c * cw, r * ch
        if kind in ("tree2", "bld2"):
            for half in (0, 1):
                slots.append((p["ref"], x0 + half * cw / 2, y0, cw / 2, ch))
        elif kind == "smudge":
            for i, sp in enumerate(p["refs"] or []):
                slots.append((sp, x0 + (i % 3) * cw / 3, y0 + (i // 3) * ch / 2, cw / 3, ch / 2))
        else:
            slots.append((p["ref"], x0, y0, cw, ch))
    sprites = {s[0]: Image.open(os.path.join(ROOT, s[0])).convert("RGBA") for s in slots if s[0]}
    margin = 0.04 if kind == "tile" else 0.12
    fits = [min(w * (1 - 2 * margin) / sprites[sp].width, h * (1 - 2 * margin) / sprites[sp].height)
            for sp, x, y, w, h in slots if sp]
    scale = min(fits) if fits else 1
    for sp, x, y, w, h in slots:
        if not sp:
            continue
        im = sprites[sp]
        s = min(w * (1 - 2 * margin) / im.width, h * (1 - 2 * margin) / im.height) if kind == "tile" else scale
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.NEAREST)
        if kind == "tile":  # transparent cells of a tile are terrain to paint, not background
            bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
            im = Image.alpha_composite(bg, im)
        sheet.paste(im, (round(x + (w - im.width) / 2), round(y + (h - im.height) / 2)), im)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)


def write_sheets(sections):
    lines = [
        "# RedAlert Project X - map environment prompts as sheets (ChatGPT)",
        "",
        "GENERATED by `artsrc/prompts/make_env_prompts.py` - edit that script, not this file.",
        "Same assets as `env-prompts.md`, but related items share one image to save ChatGPT usage: each sheet is a",
        "grid, its `Parts:` are the cells in reading order, and `generate_images.py` cuts it back into the usual",
        "`assets/env/<group>/<name>.png` files (`slice_sheet.py`). Bridges and materials stay one per image.",
        "",
        "Unattended: `artsrc/prompts/run_env_images.sh`.",
        "",
    ]
    body, n, nparts, seen = [], 0, 0, set()
    for title, note, out in sections:
        groups = {}
        for p in out:
            groups.setdefault(p["gkey"], []).append(p)
        entries = []
        for g in groups.values():
            entries += chunk(g, g[0]["maxk"])
        body += [f"**{title}** ({len(out)} items in {len(entries)} images)", ""]
        if note:
            body += [note, ""]
        for parts in entries:
            n += 1
            nparts += len(parts)
            if len(parts) == 1:
                p = parts[0]
                body += [f"### {n}. {p['title']}", f"Save as: `{p['name']}.png`"]
                if p["ref"]:
                    body.append(f"Reference: `{p['ref']}`")
                body += ["", "```", p["prompt"], "```", ""]
                continue
            rows, cols = grid_for(len(parts), parts[0]["aspect"])
            sname = parts[0]["name"].replace("/", "-") + "--" + parts[-1]["name"].split("/")[-1]
            assert sname not in seen, sname
            seen.add(sname)
            refpath = f"{SHEET_REFS}/{sname}.png"
            sheet_reference(parts, rows, cols, os.path.join(ROOT, refpath))
            body += [f"### {n}. Sheet: {', '.join(p['title'] for p in parts)}",
                     f"Save as: `sheets/{sname}.png`",
                     f"Grid: {rows}x{cols} {parts[0]['kind']} {parts[0]['aspect'][0]}:{parts[0]['aspect'][1]}",
                     "Parts: " + ", ".join(f"`{p['name']}`" for p in parts),
                     f"Reference: `{refpath}`", "", "```", sheet_prompt(parts, rows, cols), "```", ""]
    lines += [f"Total: {nparts} items in {n} images.", "", "## Map environment sheets", ""] + body
    open(SHEETS_OUT, "w").write("\n".join(lines))
    print(f"wrote {SHEETS_OUT}: {nparts} items in {n} images")


# ---------------------------------------------------------------- assemble the markdown


def main():
    sections = collect()
    lines = [
        "# RedAlert Project X - map environment prompts (ChatGPT)",
        "",
        "GENERATED by `artsrc/prompts/make_env_prompts.py` - edit that script, not this file.",
        "Inventory: `docs/ENVIRONMENT-ASSETS.md`.",
        "",
        "**How to use**",
        "",
        "- Unattended: `python3 artsrc/prompts/generate_images.py --prompts env-prompts.md --category env` "
        "(add `--only trees` or similar for one group, or `--list` to preview). Images go to `assets/env/<group>/<name>.png`.",
        "- Fewer requests: `env-sheets.md` packs related items into one image (`run_env_images.sh`).",
        "- By hand: start a new chat for each item, attach the **Reference** image (the classic sprite, 4x enlarged) "
        "and paste the prompt, prefixed with: *\"Use the attached image only as a layout reference: keep the same "
        "object, footprint, composition and camera angle, but redraw it as a high-resolution realistic asset.\"*",
        "- Reject an image if the angle changes, it adds ground under an object, the background is not flat magenta, "
        "or (on two-up sheets) the two copies differ in size or position.",
        "",
    ]
    n = 0
    total = sum(len(o) for _, _, o in sections)
    lines += [f"Total: {total} prompts.", "", "## Map environment", ""]
    for title, note, out in sections:
        lines += [f"**{title}** ({len(out)})", ""]
        if note:
            lines += [note, ""]
        for p in out:
            n += 1
            lines += [f"### {n}. {p['title']}", f"Save as: `{p['name']}.png`"]
            if p["ref"]:
                lines.append(f"Reference: `{p['ref']}`")
            lines += ["", "```", p["prompt"], "```", ""]
    open(OUT, "w").write("\n".join(lines))
    print(f"wrote {OUT}: {n} prompts")
    for title, _, out in sections:
        print(f"  {title}: {len(out)}")
    write_sheets(sections)


if __name__ == "__main__":
    main()
