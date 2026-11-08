#!/usr/bin/env python3
"""
Turns the downloaded Sketchfab models (settings: sketchfab_models.py) into game sprites, one unit at a time:
import (import_sketchfab.py) -> render with the HD light (PX_LIGHT=hd) -> pack into mods/rapx/bits/hd/units/.

  python3 artsrc/units/meshes/make_sketchfab.py <unit id> [...]   (from the repo root; "all" = every model)
  PX_RENDER_ONLY=1   re-render the existing <unit>.blend
  PX_COOLDOWN=<s>    pause between units (laptop heat; default 120)

Ground units and ships render at 2x pixels (sequence Scale 0.2333), aircraft at the jets' 2.6x (Scale 0.3333).
Blender runs niced with 4 threads; never run two at once (they crash writing the Metal kernel cache).
Afterwards: python3 artsrc/fx/make_wreck_fx.py for tank wrecks. Credits: mods/rapx/CREDITS.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from sketchfab_models import MODELS  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "artsrc", "jets"))
from loadout_table import LOADOUTS  # noqa: E402

UNITS = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "units")
SAMPLES = os.environ.get("PX_SAMPLES", "128")
BLENDER = ["nice", "-n", "15", os.environ.get("BLENDER", "blender"), "-b", "-t", "4"]


def blender(args, env=None):
    for attempt in range(2):  # Blender (Metal) crashes now and then; a second run normally goes through
        out = subprocess.run(BLENDER + args, cwd=ROOT, env={**os.environ, **(env or {})},
                             capture_output=True, text=True)
        if out.returncode == 0:
            break
        print("    blender failed, retrying:", (out.stderr or out.stdout)[-300:].strip().replace("\n", " | "))
        time.sleep(20)
    for line in out.stdout.splitlines():
        if "Offset" in line or line.startswith(("parts", "rendered", "Error", "Traceback")):
            print("   ", line)
    if out.returncode:
        print(out.stdout[-3000:], out.stderr[-3000:])
        sys.exit(f"blender failed: {' '.join(args)}")


def pack(src, name):
    subprocess.run([sys.executable, os.path.join(ROOT, "artsrc", "units", "pack_sprites.py"), src,
                    os.path.join(UNITS, f"{name}.png")], check=True)


def make(unit):
    cfg = MODELS[unit]
    kind, name = cfg["kind"], cfg.get("out", unit)
    blend = os.path.join(HERE, f"{name}.blend")
    render = os.path.join(HERE, "render", name)
    print(f"== {unit} ({kind}) -> {name}.png")
    if not os.environ.get("PX_RENDER_ONLY"):
        blender(["-P", os.path.join(HERE, "import_sketchfab.py"), "--", unit, blend])
    subprocess.run(["rm", "-rf", render, blend + "1"])
    stamp(render, "started")
    air = kind in ("air", "heli")
    frame = cfg["frame"] * 26 // 10 if air else cfg["frame"] * 2
    env = {"PX_LIGHT": "hd", "PX_UNIT_PX": "9.1" if air else "7.0"}
    if air:
        env["PX_NO_GROUND"] = "1"
    units = os.path.join(ROOT, "artsrc", "units")
    if kind == "tank":
        if cfg.get("spin"):
            env["PX_SPIN_FRAMES"] = str(cfg["spin"])
        blender([blend, "-P", os.path.join(units, "tanks", "render_tank.py"), "--", render, str(frame), SAMPLES], env)
    elif kind == "rocket":
        blender([blend, "-P", os.path.join(units, "vehicles", "render_vehicle.py"), "--", "v2rl", render,
                 str(frame), SAMPLES], env)
    elif unit in LOADOUTS:
        # IDEA-34: the jet without its weapons + every weapon as an overlay (trimmed sheet <sprite>-stores.png)
        blender([blend, "-P", os.path.join(HERE, "render_loadout.py"), "--", render, str(frame), SAMPLES], env)
        pack(render, name)
        import json
        stations = json.load(open(blend.replace(".blend", ".stores.json")))["stations"]
        dirs = [os.path.join(render, f"store-{i}{st['side']}") for i, s in enumerate(stations) for st in s["stores"]]
        if dirs:  # weapons-bay jets have nothing to show
            subprocess.run([sys.executable, os.path.join(ROOT, "artsrc", "units", "pack_trimmed.py"),
                            os.path.join(UNITS, f"{name}-stores.png")] + dirs, check=True)
        if kind == "heli":  # armed helicopters (IDEA-34): the rotor sheet on top
            blender([blend, "-P", os.path.join(HERE, "render_heli.py"), "--", render, str(frame), SAMPLES,
                     str(cfg.get("blades", 4)), "rotor-only"], env)
            pack(os.path.join(render, "rotor"), f"{name}-rotor")
        stamp(render, "finished")
        return
    elif kind == "heli":
        blender([blend, "-P", os.path.join(HERE, "render_heli.py"), "--", render, str(frame), SAMPLES,
                 str(cfg.get("blades", 4))], env)
        pack(os.path.join(render, "body"), name)
        pack(os.path.join(render, "rotor"), f"{name}-rotor")
        stamp(render, "finished")
        return
    else:
        blender([blend, "-P", os.path.join(units, "render_sprites.py"), "--", "Body", render, "32", str(frame),
                 SAMPLES], env)
    pack(render, name)
    stamp(render, "finished")


def stamp(render, state):
    """render/<sprite>/sketchfab-<state>: the progress page (soldiers/progress_server.py) reads these."""
    os.makedirs(render, exist_ok=True)
    open(os.path.join(render, f"sketchfab-{state}"), "w").write(time.strftime("%Y-%m-%d %H:%M:%S\n"))


# Units by id or by sprite name (meshes/make.sh passes sprite names); --has <name> only checks for one
by_name = {cfg.get("out", unit): unit for unit, cfg in MODELS.items()}
if sys.argv[1] == "--has":
    sys.exit(0 if sys.argv[2] in MODELS or sys.argv[2] in by_name else 1)
units = list(MODELS) if sys.argv[1:] == ["all"] else [by_name.get(u, u) for u in sys.argv[1:]]
for i, unit in enumerate(units):
    if i:
        time.sleep(int(os.environ.get("PX_COOLDOWN", "120")))
    start = time.time()
    make(unit)
    print(f"   {time.time() - start:.0f} s")
