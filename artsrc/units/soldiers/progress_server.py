#!/usr/bin/env python3
"""
Live progress page for the 3D soldier renders (build_soldier.sh), the ChatGPT image queue and (second tab)
the Sketchfab model renders (artsrc/units/meshes/make_sketchfab.py); the "Ironward map" tab follows the ChatGPT
repaint of the Ironward backdrop (artsrc/maps/ironward/repaint.py).

  python3 artsrc/units/soldiers/progress_server.py [port]      # then open http://localhost:8765

Reads the render folders on every request; nothing to configure. Stop with Ctrl+C.
"""
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
RENDER = os.path.join(HERE, "render")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


UNARMED = {"e6", "medi", "mech", "spy"}  # build_soldier.sh skips their shooting moves


def table(uid=None):
    """[(sequence, frames, facings)] from build_soldier.sh's TABLE."""
    text = open(os.path.join(HERE, "build_soldier.sh")).read()
    block = text.split('TABLE="')[1].split('"')[0]
    rows = []
    for line in block.strip().splitlines():
        seq, clip, frames, opts, facings = line.split("|")
        kind, _, n = frames.partition(":")
        count = int(n) if n else len(frames.split(","))
        if uid in UNARMED and seq in ("shoot", "proneshoot"):
            continue
        rows.append((seq, clip, count, int(facings)))
    return rows


def soldier_status(uid):
    rows = []
    times = []
    latest = None
    for seq, clip, frames, facings in table(uid):
        folder = os.path.join(RENDER, uid, seq)
        files = [f for f in os.listdir(folder) if f.endswith(".png")] if os.path.isdir(folder) else []
        for f in files:
            t = os.path.getmtime(os.path.join(folder, f))
            times.append(t)
            if latest is None or t > latest[0]:
                latest = (t, f"{uid}/{seq}/{f}")
        packed = os.path.exists(os.path.join(ROOT, "mods", "rapx", "bits", "hd", "soldiers", uid, f"{seq}.png"))
        rows.append({"seq": seq, "clip": clip, "done": len(files), "total": frames * facings, "facings": facings,
                     "frames": frames, "packed": packed and len(files) >= frames * facings})
    done = sum(r["done"] for r in rows)
    total = sum(r["total"] for r in rows)
    # Speed from the last 60 frames
    times.sort()
    recent = times[-60:]
    rate = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 5 and recent[-1] > recent[0] else 0
    active = bool(times) and time.time() - times[-1] < 120 and done < total
    current = next((r["seq"] for r in rows if 0 < r["done"] < r["total"]), None)
    if active and not current:
        current = next((r["seq"] for r in rows if r["done"] == 0), None)
    return {"id": uid, "rows": rows, "done": done, "total": total, "rate": rate,
            "eta": (total - done) / rate if rate else None, "active": active, "current": current,
            "latest": latest[1] if latest else None, "latest_age": time.time() - latest[0] if latest else None,
            "recent": recent_images(uid)}


def recent_images(uid, n=12):
    out = []
    base = os.path.join(RENDER, uid)
    if not os.path.isdir(base):
        return out
    for seq in os.listdir(base):
        folder = os.path.join(base, seq)
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.endswith(".png"):
                    out.append((os.path.getmtime(os.path.join(folder, f)), f"{uid}/{seq}/{f}"))
    out.sort(reverse=True)
    return [p for _, p in out[:n]]


def image_queue():
    path = os.path.join(ROOT, "assets", "units", "anim-progress.json")
    if not os.path.exists(path):
        return None
    data = json.load(open(path))
    items = data.get("items", [])
    count = lambda s: sum(1 for i in items if i.get("status") == s)
    return {"updated": data.get("updated"), "stopped": data.get("stopped"), "done": count("done"),
            "failed": count("failed"), "pending": count("pending"), "total": len(items)}


# Every unit planned for the 3D route: (id, name, group)
ROSTER = [
    ("e1", "Rifle Infantry", "Soldiers"), ("e2", "Grenadier", "Soldiers"), ("e3", "Rocket Soldier", "Soldiers"),
    ("e4", "Flame Infantry", "Soldiers"), ("e6", "Engineer", "Soldiers"), ("e7", "Tanya", "Soldiers"),
    ("medi", "Medic", "Soldiers"), ("mech", "Mechanic", "Soldiers"),
    ("shok", "Shock Trooper", "Soldiers"), ("spy", "Spy", "Soldiers"), ("snip", "Sniper", "Soldiers"),
    ("cybt", "Cyborg Trooper", "Humanoid robots"), ("bdrd", "Battle Droid", "Humanoid robots"),
    ("rgun", "Railgun Robot", "Humanoid robots"), ("irgd", "Iron Guard", "Humanoid robots"),
    ("taut", "Tesla Automaton", "Humanoid robots"),
    ("enfw", "Enforcer Walker", "Other (own approach)"), ("strd", "Strider", "Other (own approach)"),
    ("sdrn", "Spider Drone", "Other (own approach)"), ("dog", "Attack Dog", "Other (own approach)"),
]
STEPS = ["concept", "views", "3D body", "rig-ready", "animations", "rendered", "in game"]
UNITS_DIR = os.path.join(ROOT, "assets", "units")
LOGS = [os.path.join(RENDER, "*.log"), os.path.join(ROOT, "assets", "units", "*.out")]


def active_jobs():
    """Running pipeline processes: [{kind, unit, label, step, gpu, elapsed, progress}]."""
    import glob
    import subprocess
    try:
        ps = subprocess.run(["ps", "-Ao", "etime=,command="], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return []
    # latest progress lines from the chain / build logs (newest log first)
    logs = sorted((f for pat in LOGS for f in glob.glob(pat)), key=os.path.getmtime, reverse=True)[:6]
    tails = []
    for f in logs:
        try:
            with open(f, "rb") as fh:
                fh.seek(max(0, os.path.getsize(f) - 6000))
                tails.append(fh.read().decode("utf-8", "replace"))
        except OSError:
            pass
    tail = "\n".join(tails)
    jobs = []
    for line in ps.splitlines():
        line = line.strip()
        if not line or "grep" in line:
            continue
        elapsed, _, cmd = line.partition(" ")
        cmd = cmd.strip()
        job = None
        m = re.search(r"hunyuan_local\.py ([\w-]+)", cmd)
        if m and "Python" in cmd:
            uid = m.group(1).split("-")[0]
            pct = re.findall(r"Diffusion Sampling::\s*(\d+)%", tail)
            dec = re.findall(r"Volume Decoding:\s*(\d+)%", tail)
            prog = f"diffusion {pct[-1]}%" if pct else None
            if dec and pct and int(pct[-1]) >= 98:
                prog = f"decoding {dec[-1]}%"
            job = {"kind": "Hunyuan3D", "unit": uid, "step": "3D body", "gpu": "full",
                   "label": "Generating the 3D body from the concept (AI model on the GPU)", "progress": prog}
        m = re.search(r"render_soldier\.py -- ([\w-]+) \S+ \S+/([\w-]+) ", cmd)
        if m and "Blender" in cmd:
            job = {"kind": "Blender", "unit": m.group(1), "step": "rendered", "gpu": "throttled",
                   "label": f"Rendering the '{m.group(2)}' animation (32 directions)", "progress": None}
        m = re.search(r"prep_mixamo\.py -- ([\w-]+)", cmd)
        if m and "Blender" in cmd:
            job = {"kind": "Blender", "unit": m.group(1), "step": "rig-ready", "gpu": "light",
                   "label": "Cleaning the 3D body for the skeleton (cut weapon, paint colours)", "progress": None}
        m = re.search(r"generate_images\.py --prompts (\S+)", cmd)
        if m and "Python" in cmd:
            items = re.findall(r"\[(\d+)/(\d+)\] (\S+)", tail)
            cur = items[-1] if items else None
            unit = re.sub(r"^views/", "", cur[2]).split("-")[0] if cur else "?"
            job = {"kind": "ChatGPT", "unit": unit, "step": "views" if cur and "views/" in cur[2] else "concept",
                   "gpu": "none (cloud)", "label": f"Drawing {cur[2] if cur else 'images'} ({os.path.basename(m.group(1))})",
                   "progress": f"image {cur[0]} of {cur[1]}" if cur else None}
        m = re.search(r"import_sketchfab\.py -- ([\w.-]+)", cmd)
        if m and "Blender" in cmd:
            job = {"kind": "Blender", "unit": m.group(1), "step": "imported", "gpu": "light",
                   "label": "Importing a Sketchfab model (turret / rotors, team colour)", "progress": None}
        m = re.search(r"units/meshes/([\w.-]+)\.blend -P \S+/(render_\w+)\.py", cmd)
        if m and "Blender" in cmd:
            job = {"kind": "Blender", "unit": m.group(1), "step": "rendered", "gpu": "throttled",
                   "label": f"Rendering a Sketchfab model, HD light ({m.group(2)})", "progress": None}
        m = re.search(r"make\.sh ([\w-]+)", cmd)
        if m and cmd.startswith("sh "):
            job = {"kind": "Blender", "unit": m.group(1), "step": "rendered", "gpu": "full",
                   "label": "Rendering a vehicle / jet (32 directions)", "progress": None}
        if job:
            job["elapsed"] = elapsed
            jobs.append(job)
    return jobs


def unit_status(uid, jobs):
    """Which pipeline steps a unit has passed, and the one it is on now."""
    views_dir = os.path.join(UNITS_DIR, "views")
    concept = os.path.exists(os.path.join(UNITS_DIR, f"{uid}.png"))
    views = (all(os.path.exists(os.path.join(views_dir, f"{uid}-unarmed-{v}.png")) for v in ("front", "back", "left")) or
             all(os.path.exists(os.path.join(views_dir, f"{uid}-{v}.png")) for v in ("back", "left")))
    shape = os.path.join(ROOT, "artsrc", "units", "meshes", "shape")
    body = os.path.exists(os.path.join(shape, f"{uid}.glb")) or os.path.exists(os.path.join(shape, f"{uid}-unarmed-front.glb"))
    upload = os.path.exists(os.path.join(HERE, "upload", f"{uid}.blend"))
    own = os.path.join(HERE, "anim", uid)
    # Animations: his own Mixamo clips, or e1's clips (shared rig) once he has a rig-ready body
    shared = upload and os.path.isdir(os.path.join(HERE, "anim", "e1")) and len(os.listdir(os.path.join(HERE, "anim", "e1"))) >= 10
    anims = (os.path.isdir(own) and len(os.listdir(own)) >= 10) or shared
    rows = table(uid)
    need = sum(f * fc for _, _, f, fc in rows)
    got = 0
    for seq, _, f, fc in rows:
        folder = os.path.join(RENDER, uid, seq)
        got += min(f * fc, len([x for x in os.listdir(folder) if x.endswith(".png")])) if os.path.isdir(folder) else 0
    rendered = got >= need
    seqs = os.path.join(ROOT, "mods", "rapx", "sequences", "hd-soldiers3d.yaml")
    ingame = rendered and os.path.exists(seqs) and re.search(rf"^{re.escape(uid)}:$", open(seqs).read(), re.M) is not None
    flags = [concept, views, body, upload, anims, rendered, ingame]
    running = [j for j in jobs if j["unit"] == uid]
    active = STEPS.index(running[0]["step"]) if running else None
    state = "done" if ingame else ("progress" if any(flags[2:]) or got or running else "remaining")
    return {"steps": flags, "active": active, "state": state, "render": got / need if need else 0,
            "job": running[0] if running else None}


def overview(jobs):
    units = []
    for uid, name, group in ROSTER:
        u = unit_status(uid, jobs)
        u.update({"id": uid, "name": name, "group": group})
        units.append(u)
    count = lambda st: sum(1 for u in units if u["state"] == st)
    return {"units": units, "steps": STEPS, "done": count("done"), "progress": count("progress"),
            "remaining": count("remaining"), "total": len(units)}


MESHES = os.path.join(ROOT, "artsrc", "units", "meshes")
MESH_RENDER = os.path.join(MESHES, "render")
SPRITES = os.path.join(ROOT, "mods", "rapx", "bits", "hd", "units")
# Unit names for the Sketchfab tab (game unit each model replaces)
UNIT_NAMES = {"3tnk": "Heavy Tank", "4tnk": "Mammoth Tank", "v2rl": "V2 Rocket Launcher", "apc": "APC",
              "jet.a10": "Thunderhog jet", "jet.f14": "Bobcat jet", "jet.su35": "Flankard-E jet",
              "jet.f22": "Raptorex jet", "jet.x47": "Stingray drone", "jet.swarm": "Swarm drone",
              "jet.zeppelin": "Zeppelin", "mig": "MiG Attack Plane", "badr": "Badger plane", "tran": "Chinook",
              "heli": "Longbow", "hind": "Hind", "mh60": "Black Hawk"}
# Planned phase of the second download (assets/inbox/new_3d_models_2, folders named <unit>__<model>)
PHASES = {"ships": ("Phase 4 - ships", {"ss", "msub", "dd", "ca", "pt", "lst"}),
          "special": ("Phase 3 - special vehicles", {"mrj", "mgg", "harv", "ttnk-coil"}),
          "later": ("Phase 5 - with the robots", {"sdrn"})}


INBOX3_PLAN = {
    "tu-95m_with_rds-37": "Phase 1 - aircraft: Badger bomber (BADR.Bomber; the C-17 keeps the paradrops)",
    "tiger_russian_military_vehicle": "Phase 2 - ground vehicles: Ranger (JEEP), instead of the Willys jeep",
    "i.j.n._yamato_battleship": "Phase 4 - ships: Cruiser (CA), instead of the Iowa",
    "british_navy_claa_tier__uranus": "Phase 4 - ships: Destroyer (DD), instead of the low-poly Arleigh Burke",
    "buk-m3_9k317_sam": "Later - Russia's medium SAM 'Bukk-M3' (IDEA-26, not built yet)",
    "sky_sabre_sam": "Later - England's medium SAM 'Sky Sabar' (IDEA-26, not built yet)",
    "low-poly_uss_nimitz": "Later - aircraft carrier (IDEA-08, not built yet)",
}


def phase_of(unit):
    if unit.startswith("jet.") or unit in ("yak", "u2"):
        return "Phase 1 - aircraft"
    return next((label for label, units in PHASES.values() if unit in units), "Phase 2 - ground vehicles")


# Downloaded models not in a unit yet (sketchfab_models.py has no entry for them)
SKETCHFAB_WAITING = [
    ("Centurion Heavy Assault Mech", "robot walker: needs walk / attack animation sheets"),
    ("futuristic bipedal combat robot", "robot walker: no animation in the model"),
    ("C-17A Globemaster III (VTX)", "same model as the C-17 used for the Badger"),
    ("Red Alert 2 ApoCalypse (fikriemre)", "second Apocalypse; the Ska-Ara one is used"),
]


def sketchfab_models():
    import importlib.util
    spec = importlib.util.spec_from_file_location("sketchfab_models", os.path.join(MESHES, "sketchfab_models.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MODELS


def licence_of(src):
    path = os.path.join(MESHES, "glb", "sketchfab", os.path.dirname(src), "license.txt")
    info = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"\* (title|author|license type):\s*(.+)", line.strip())
            if m:
                info[m.group(1)] = re.sub(r"\s*\(http[^)]*\)", "", m.group(2)).strip()
    return info


def pngs(folder, since):
    if not os.path.isdir(folder):
        return []
    out = []
    for f in os.listdir(folder):
        if f.endswith(".png"):
            t = os.path.getmtime(os.path.join(folder, f))
            if t >= since:
                out.append((t, os.path.join(folder, f)))
    return out


def sketchfab_status(jobs):
    """Per unit: imported / frames rendered / packed, from files newer than the current model settings."""
    try:
        models = sketchfab_models()
    except Exception as e:
        return {"error": str(e), "units": [], "waiting": SKETCHFAB_WAITING}
    running = {j["unit"] for j in jobs if j.get("kind") == "Blender"}
    units, times = [], []
    for uid, cfg in models.items():
        name, kind = cfg.get("out", uid), cfg["kind"]
        folder = os.path.join(MESH_RENDER, name)
        # make_sketchfab.py stamps each unit when it starts (render folder wiped) and when its sheet is packed
        started_f, finished_f = (os.path.join(folder, f"sketchfab-{x}") for x in ("started", "finished"))
        since = os.path.getmtime(started_f) if os.path.exists(started_f) else float("inf")
        if kind == "heli":
            frames = pngs(os.path.join(folder, "body"), since) + pngs(os.path.join(folder, "rotor-steps"), since)
            total = 32 + 32
        else:
            frames = pngs(folder, since)
            total = 64 if kind in ("tank", "rocket") else 32
        times += [t for t, _ in frames]
        imported = since != float("inf")
        packed = os.path.exists(finished_f) and os.path.getmtime(finished_f) >= since
        latest = max(frames)[1] if frames else None
        group = "Batch 1" if cfg["src"].startswith(("inbox/", "t72b3/")) else phase_of(uid)
        state = "done" if packed else "active" if name in running or uid in running else "progress" if imported or frames else "waiting"
        lic = licence_of(cfg["src"])
        units.append({"id": uid, "unit": cfg.get("name") or UNIT_NAMES.get(uid, uid), "group": group, "sprite": name, "kind": kind, "done": min(len(frames), total),
                      "total": total, "imported": imported, "packed": packed, "state": state,
                      "model": lic.get("title", os.path.dirname(cfg["src"])), "author": lic.get("author", ""),
                      "licence": lic.get("license type", ""),
                      "latest": os.path.relpath(latest, MESH_RENDER) if latest else None})
    times.sort()
    recent = [t for t in times if t > time.time() - 1800][-40:]
    rate = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 5 and recent[-1] > recent[0] else 0
    left = sum(u["total"] - u["done"] for u in units if not u["packed"])
    waiting_units = sum(1 for u in units if not u["packed"])
    cooldown = 90 * max(0, waiting_units - 1)
    latest = max(((os.path.getmtime(os.path.join(MESH_RENDER, u["latest"])), u["latest"]) for u in units if u["latest"]),
                 default=None)
    # Downloaded but not set up yet: the second download's folders no model entry points at
    used = {os.path.dirname(c["src"]).split("/")[-1] for c in models.values()}
    inbox2 = os.path.join(MESHES, "glb", "sketchfab", "inbox2")
    waiting = list(SKETCHFAB_WAITING)
    if os.path.isdir(inbox2):
        for folder in sorted(os.listdir(inbox2)):
            if folder not in used and "__" in folder:
                unit, model = folder.split("__", 1)
                waiting.append((f"{unit}: {model.replace('_', ' ').strip()}", phase_of(unit)))
    # Third download (assets/inbox/models_3): planned slot per model; B-2 duplicate and the two no-derivatives
    # models (ED-209, Shahed 136) are left out
    for folder, plan in INBOX3_PLAN.items():
        if folder not in used:
            waiting.append((folder.replace("_", " "), plan))
    return {"units": units, "waiting": waiting, "done": sum(u["packed"] for u in units), "total": len(units),
            "frames_done": sum(u["done"] for u in units), "frames_total": sum(u["total"] for u in units),
            "rate": rate, "eta": left / rate + cooldown if rate else None,
            "latest": latest[1] if latest else None, "latest_age": time.time() - latest[0] if latest else None}


def loadout_status():
    """IDEA-34 jet loadouts: per jet the weapons, whether it is rendered with them and in the game rules."""
    import importlib.util
    jets = os.path.join(ROOT, "artsrc", "jets")
    try:
        spec = importlib.util.spec_from_file_location("loadout_table", os.path.join(jets, "loadout_table.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        table = mod.LOADOUTS
        models = sketchfab_models()
    except Exception as e:
        return {"error": str(e)}
    table_time = os.path.getmtime(os.path.join(jets, "loadout_table.py"))
    rules_path = os.path.join(ROOT, "mods", "rapx", "rules", "jet-loadouts.yaml")
    rules = open(rules_path).read() if os.path.exists(rules_path) else ""
    rules_time = os.path.getmtime(rules_path) if os.path.exists(rules_path) else 0
    short = {"JetAAM.Short": "short AAM", "JetAAM.Medium": "medium AAM", "JetAAM.Long": "long AAM", "JetAGM": "Maverick",
             "JetBomb": "bombs", "JetGBU": "guided bombs", "JetRockets": "rockets"}
    jobs = {j["unit"] for j in active_jobs() if j.get("kind") == "Blender"}
    out = []
    for unit, cfg in table.items():
        sprite = models.get(unit, {}).get("out", unit)
        name = models.get(unit, {}).get("name") or UNIT_NAMES.get(unit, unit)
        weapons = []
        for st in cfg["stations"]:
            n = st.get("shots", 1) * (1 if st.get("internal") or st.get("centre") else 2)
            src = "bay" if st.get("internal") else "model" if "model" in st else "added"
            weapons.append(f"{n} {short.get(st['weapon'], st['weapon'])} ({src})")
        if cfg.get("gun"):
            weapons.append(f"{cfg['gun']} gun")
        folder = os.path.join(MESH_RENDER, sprite)
        started, finished = (os.path.join(folder, f"sketchfab-{x}") for x in ("started", "finished"))
        t0 = os.path.getmtime(started) if os.path.exists(started) else 0
        t1 = os.path.getmtime(finished) if os.path.exists(finished) else 0
        stores = os.path.join(MESHES, f"{sprite}.stores.json")
        rendered = t1 >= t0 > 0 and os.path.exists(stores) and os.path.getmtime(stores) >= table_time - 1e9 and t1 > os.path.getmtime(stores) - 5
        rendering = sprite in jobs or unit in jobs or (t0 > t1)
        in_rules = re.search(rf"^{re.escape(unit.upper())}:$", rules, re.M) is not None and rules_time >= t1
        frames = len([f for f in os.listdir(folder) if f.startswith("store-")]) if os.path.isdir(folder) else 0
        state = "done" if rendered and in_rules else "active" if rendering else "rules" if rendered else "waiting"
        preview = os.path.relpath(os.path.join(folder, "frame-04.png"), MESH_RENDER) if os.path.exists(os.path.join(folder, "frame-04.png")) else None
        visual = any(not st.get("internal") for st in cfg["stations"])
        took = t1 - t0 if t1 >= t0 > 0 and rendered else None
        out.append({"unit": unit, "name": name, "weapons": weapons, "state": state, "overlays": frames,
                    "visual": visual, "took": took, "started": t0 if rendering else None,
                    "strike": bool(cfg.get("strike")), "fighter": any(st["weapon"].startswith("JetAAM") for st in cfg["stations"]) and not cfg.get("strike"),
                    "preview": preview})
    steps = []
    try:
        steps = json.load(open(os.path.join(jets, "loadout-status.json")))["steps"]
    except Exception:
        pass
    count = lambda st: sum(1 for j in out if j["state"] == st)
    # Time left: average render time of finished jets of the same kind (weapon overlays take ~4x a bay-only jet),
    # minus what the jet on the bench has already spent, plus the driver's cool-down between jets
    cooldown = 30
    def avg(visual):
        t = [j["took"] for j in out if j["took"] and j["visual"] == visual]
        return sum(t) / len(t) if t else (300 if visual else 90)
    left = 0.0
    queued = [j for j in out if j["state"] in ("waiting", "active")]
    for j in queued:
        est = avg(j["visual"])
        if j["state"] == "active" and j["started"]:
            est = max(10.0, est - (time.time() - j["started"]))
        left += est + cooldown
    if queued:
        left -= cooldown
    for j in out:
        j.pop("took", None)
    return {"jets": out, "steps": steps, "eta": left if queued else 0, "eta_at": time.time() + left if queued else None, "done": count("done"), "total": len(out), "active": count("active"),
            "waiting": count("waiting") + count("rules")}


MACTEMP = os.path.join(ROOT, "artsrc", "tools", "mactemp")  # built from artsrc/tools/mactemp.swift
NCPU = os.cpu_count() or 1


def system():
    """Laptop temperatures (no root: HID sensors via the mactemp helper), thermal state, CPU and GPU load."""
    import subprocess
    out = {"cpu": None, "cpu_avg": None, "battery": None, "thermal": None, "cpu_load": None, "gpu_load": None}
    try:
        out.update(json.loads(subprocess.run([MACTEMP], capture_output=True, text=True, timeout=5).stdout))
    except Exception:
        pass
    try:
        total = sum(float(x) for x in subprocess.run(["ps", "-A", "-o", "%cpu="], capture_output=True, text=True,
                                                      timeout=5).stdout.split())
        out["cpu_load"] = min(100.0, total / NCPU)
    except Exception:
        pass
    try:
        io = subprocess.run(["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r'"Device Utilization %"=(\d+)', io)
        out["gpu_load"] = int(m.group(1)) if m else None
    except Exception:
        pass
    return out


# ---- Ironward repaint (artsrc/maps/ironward/repaint.py)
IW_BUILD = os.path.join(ROOT, "artsrc", "maps", "ironward", "build")
IW_TILES = os.path.join(IW_BUILD, "tiles")
IW_PAINT = os.path.join(ROOT, "assets", "maps", "ironward", "paint")
IW_THUMBS = os.path.join(IW_BUILD, "thumbs")
IW_LOG = os.path.join(ROOT, "assets", "generate_images.log")
_iw_scores = {}


def iw_thumb(kind, name):
    """Small JPEG of a render tile or a repainted piece, cached by modification time."""
    src = os.path.join(IW_TILES if kind == "render" else IW_PAINT, name)
    if not os.path.exists(src):
        return None
    os.makedirs(IW_THUMBS, exist_ok=True)
    out = os.path.join(IW_THUMBS, f"{kind}-{name[:-4]}.jpg")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        from PIL import Image
        Image.open(src).convert("RGB").resize((384, 256), Image.LANCZOS).save(out, quality=82)
    return out


def iw_score(name):
    """Drift score of a repainted piece (repaint.py's layout correlation), cached by modification time."""
    path = os.path.join(IW_PAINT, name)
    key = (name, os.path.getmtime(path))
    if key not in _iw_scores:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("iw_repaint", os.path.join(ROOT, "artsrc", "maps", "ironward", "repaint.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _iw_scores[key] = round(mod.score(name), 2)
        except Exception:
            _iw_scores[key] = None
    return _iw_scores[key]


def ironward_status():
    if not os.path.isdir(IW_TILES):
        return None
    names = sorted(f for f in os.listdir(IW_TILES) if f.endswith(".png"))
    pieces = []
    for n in names:
        x, y = (int(v) for v in n[5:-4].split("-"))
        painted = os.path.exists(os.path.join(IW_PAINT, n))
        pieces.append({"name": n, "x": x, "y": y, "done": painted, "score": iw_score(n) if painted else None,
                       "mtime": os.path.getmtime(os.path.join(IW_PAINT, n)) if painted else 0})
    # Generator log: the piece being painted now and the time per piece
    current, started, durations, finished, limit = None, None, [], False, None
    if os.path.exists(IW_LOG):
        with open(IW_LOG, errors="replace") as f:
            lines = f.readlines()[-400:]
        for line in lines:
            if "ironward/paint/" not in line and "finished:" not in line and "limit" not in line.lower():
                continue
            m = re.search(r"\] ironward/paint/(tile-\d+-\d+) .*attempt", line)
            if m:
                current = m.group(1) + ".png"
                started = time.mktime(time.strptime(line[:19], "%Y-%m-%d %H:%M:%S"))
                finished = False
            m = re.search(r"ironward/paint/tile-\d+-\d+\.png \((\d+)s\)", line)
            if m:
                durations.append(int(m.group(1)))
            if "finished:" in line and current:
                finished = True
            if re.search(r"usage limit|rate limit", line, re.I):
                limit = line[11:19]
    running = any("ironward-repaint-prompts" in j.get("cmd", "") for j in active_jobs_raw())
    done = sum(p["done"] for p in pieces)
    avg = sum(durations[-12:]) / len(durations[-12:]) if durations else 80
    remaining = len(pieces) - done
    eta = remaining * avg - (time.time() - started if running and started else 0) if remaining else 0
    newest = max((p for p in pieces if p["done"]), key=lambda p: p["mtime"], default=None)
    drift = [p["name"] for p in pieces if p["score"] is not None and p["score"] < 0.5]
    steps = [
        ("Animated lights in the game (PxBackdropLights, 387 lights)", True),
        ("Style A painted textures in the Blender render", True),
        ("Repaint test pieces checked", True),
        (f"Repaint all {len(pieces)} pieces with ChatGPT", done == len(pieces)),
        ("Drift check and review of every piece", False),
        ("Blend the pieces into one backdrop", os.path.exists(os.path.join(IW_BUILD, "backdrop-painted.png"))),
        ("Match the moving-water mask to the painted canals, cut into the map", False),
    ]
    return {"pieces": pieces, "done": done, "total": len(pieces), "running": running and not finished,
            "current": current if running and not finished else None, "avg": avg, "eta": max(0, eta),
            "newest": newest["name"] if newest else None, "drift": drift, "limit": limit,
            "steps": [{"name": s, "done": d} for s, d in steps]}


def active_jobs_raw():
    try:
        import subprocess
        out = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True, timeout=5).stdout
        return [{"cmd": l} for l in out.splitlines() if "generate_images.py" in l]
    except Exception:
        return []


# GitHub push: bytes sent by git-remote-https (from nettop) against the repo's packed size
_push = {"samples": [], "total": None}


def push_status():
    import subprocess

    def git(*args):
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True).stdout.strip()

    pids = subprocess.run(["pgrep", "-f", "git-remote-https"], capture_output=True, text=True).stdout.split()
    if not pids:
        if not _push["samples"]:
            return None
        ok = git("rev-parse", "main") == git("rev-parse", "origin/main")
        return {"state": "done" if ok else "stopped", "sent": _push["samples"][-1][1], "total": _push["total"]}

    if _push["total"] is None:
        m = re.search(r"size-pack: (\d+)", git("count-objects", "-v"))
        _push["total"] = int(m.group(1)) * 1024 if m else None

    sent = 0
    for pid in pids:
        out = subprocess.run(["nettop", "-p", pid, "-L", "1", "-x", "-J", "bytes_out"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("git-remote-http"):
                sent += int(line.rstrip(",").split(",")[-1] or 0)

    now = time.time()
    samples = _push["samples"] = [x for x in _push["samples"] if now - x[0] < 30] + [(now, sent)]
    rate = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0]) if len(samples) > 1 and samples[-1][0] > samples[0][0] else None
    total = _push["total"]
    eta = (total - sent) / rate if rate and total and total > sent else None
    return {"state": "pushing", "sent": sent, "total": total, "rate": rate, "eta": eta, "remote": git("remote", "get-url", "origin")}


def status():
    soldiers = sorted(d for d in os.listdir(RENDER) if os.path.isdir(os.path.join(RENDER, d))) if os.path.isdir(RENDER) else []
    jobs = active_jobs()
    return {"time": time.strftime("%H:%M:%S"), "system": system(), "jobs": jobs, "overview": overview(jobs),
            "sketchfab": sketchfab_status(jobs), "loadouts": loadout_status(), "ironward": ironward_status(),
            "soldiers": [soldier_status(s) for s in soldiers], "images": image_queue(), "push": push_status()}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Render Progress</title>
<style>
:root { --bg:#14161a; --panel:#1d2026; --line:#2c313a; --text:#e8e6e1; --muted:#9097a3; --accent:#e0483e; --ok:#5fb87a; --bar:#2a2f37; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:15px/1.45 -apple-system, "Segoe UI", sans-serif; }
header { display:flex; align-items:baseline; gap:16px; padding:20px 24px 8px; flex-wrap:wrap; }
h1 { margin:0; font-size:22px; letter-spacing:.02em; }
.sub { color:var(--muted); font-size:13px; }
main { padding:8px 24px 32px; display:grid; gap:20px; max-width:1200px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 20px; }
.top { display:grid; grid-template-columns: 1fr 210px; gap:20px; }
@media (max-width:760px) { .top { grid-template-columns:1fr; } header, main { padding-left:16px; padding-right:16px; } }
.title { display:flex; align-items:center; gap:10px; margin-bottom:6px; }
.title h2 { margin:0; font-size:19px; }
.pill { font-size:12px; padding:2px 9px; border-radius:99px; background:var(--bar); color:var(--muted); }
.pill.live { background:rgba(224,72,62,.18); color:#ff8f86; }
.pill.done { background:rgba(95,184,122,.18); color:#8fdca7; }
.big { font-size:34px; font-weight:650; font-variant-numeric:tabular-nums; }
.stats { display:flex; gap:24px; flex-wrap:wrap; color:var(--muted); font-size:13px; margin:4px 0 14px; }
.stats b { color:var(--text); font-weight:600; font-variant-numeric:tabular-nums; }
.bar { height:8px; background:var(--bar); border-radius:99px; overflow:hidden; }
.bar > i { display:block; height:100%; background:var(--accent); border-radius:99px; transition:width .6s; }
.bar.ok > i { background:var(--ok); }
table { width:100%; border-collapse:collapse; margin-top:14px; font-size:14px; }
td { padding:7px 6px; border-top:1px solid var(--line); vertical-align:middle; }
td.n { text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; white-space:nowrap; width:90px; }
td.s { width:120px; }
td.b { width:40%; }
tr.cur td { background:rgba(224,72,62,.07); }
.tag { font-size:12px; color:var(--muted); }
.preview { background:#7a6852; border-radius:8px; aspect-ratio:1; display:grid; place-items:center; overflow:hidden; }
.preview img { width:100%; image-rendering:auto; }
.cap { font-size:12px; color:var(--muted); margin-top:6px; word-break:break-all; }
.strip { display:flex; gap:6px; margin-top:16px; overflow-x:auto; }
.strip img { width:72px; height:72px; background:#7a6852; border-radius:6px; flex:none; }
.empty { color:var(--muted); }
.counts { display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin:10px 0 14px; }
.count { background:var(--bar); border-radius:8px; padding:10px 14px; }
.count .v { font-size:28px; font-weight:650; font-variant-numeric:tabular-nums; }
.count .l { color:var(--muted); font-size:13px; }
.count.d .v { color:#8fdca7; } .count.p .v { color:#ff8f86; }
.stack { display:flex; height:10px; border-radius:99px; overflow:hidden; background:var(--bar); }
.stack i { display:block; height:100%; } .stack .d { background:var(--ok); } .stack .p { background:var(--accent); }
.group { margin-top:18px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
.units { display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); gap:10px; margin-top:8px; }
.unit { border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
.unit.done { border-color:rgba(95,184,122,.5); } .unit.progress { border-color:rgba(224,72,62,.5); }
.unit .nm { font-weight:600; } .unit .id { color:var(--muted); font-size:12px; margin-left:4px; }
.dots { display:flex; gap:4px; margin-top:8px; } .dots span { flex:1; height:6px; border-radius:3px; background:var(--bar); }
.dots span.on { background:var(--ok); }
.dots span.act { background:var(--accent); animation:pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity:.35; } }
.job { display:grid; grid-template-columns:auto 1fr auto; gap:4px 12px; padding:10px 0; border-top:1px solid var(--line); align-items:center; }
.job:first-of-type { border-top:0; }
.job .k { font-size:12px; padding:2px 9px; border-radius:99px; background:var(--bar); white-space:nowrap; }
.job .k.full { background:rgba(224,72,62,.2); color:#ff8f86; } .job .k.throttled { background:rgba(224,168,62,.2); color:#f2c46b; }
.job .u { font-weight:600; } .job .d { color:var(--muted); font-size:13px; grid-column:2 / 4; }
.job .t { color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; text-align:right; }
.steps-key { display:flex; flex-wrap:wrap; gap:4px 14px; font-size:12px; color:var(--muted); margin-top:10px; }
.unit .st { font-size:12px; color:var(--muted); margin-top:6px; }
.legend { font-size:12px; color:var(--muted); margin-top:10px; }
#sys { position:fixed; right:16px; bottom:16px; z-index:10; width:230px; background:rgba(29,32,38,.96);
  border:1px solid var(--line); border-radius:12px; padding:12px 14px; box-shadow:0 8px 30px rgba(0,0,0,.45);
  backdrop-filter:blur(6px); font-size:13px; }
#sys h3 { margin:0 0 8px; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
  display:flex; justify-content:space-between; align-items:center; }
#sys .temp { font-size:32px; font-weight:650; font-variant-numeric:tabular-nums; line-height:1.1; }
#sys .row { display:flex; justify-content:space-between; margin-top:6px; color:var(--muted); }
#sys .row b { color:var(--text); font-variant-numeric:tabular-nums; font-weight:600; }
#sys .mini { height:5px; background:var(--bar); border-radius:99px; overflow:hidden; margin-top:3px; }
#sys .mini i { display:block; height:100%; border-radius:99px; transition:width .6s; }
.c-ok { color:#8fdca7; } .c-warm { color:#f2c46b; } .c-hot { color:#ff8f86; }
.b-ok { background:var(--ok); } .b-warm { background:#e0a83e; } .b-hot { background:var(--accent); }
.state { font-size:11px; padding:1px 8px; border-radius:99px; background:var(--bar); }
nav.tabs { display:flex; gap:6px; padding:4px 24px 0; flex-wrap:wrap; }
nav.tabs button { font:inherit; font-size:14px; color:var(--muted); background:transparent; border:1px solid var(--line);
  border-radius:99px; padding:6px 14px; cursor:pointer; }
nav.tabs button.on { color:var(--text); background:var(--panel); border-color:#4a515d; }
nav.tabs button .badge { margin-left:6px; font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; }
@media (max-width:760px) { nav.tabs { padding-left:16px; padding-right:16px; } }
.models { display:grid; grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); gap:12px; margin-top:14px; }
.model { border:1px solid var(--line); border-radius:10px; overflow:hidden; display:flex; flex-direction:column; }
.model.done { border-color:rgba(95,184,122,.5); } .model.active { border-color:rgba(224,72,62,.6); }
.model .pic { background:#7a6852; aspect-ratio:1; display:grid; place-items:center; color:#3c3328; font-size:13px; }
.model .pic img { width:100%; height:100%; object-fit:contain; }
.model .info { padding:10px 12px 12px; display:grid; gap:4px; }
.model .nm { font-weight:600; } .model .md { font-size:12px; color:var(--muted); }
.model .row { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:var(--muted); gap:8px; }
.lic { font-size:11px; padding:1px 7px; border-radius:99px; background:var(--bar); white-space:nowrap; }
.lic.nc { background:rgba(224,168,62,.2); color:#f2c46b; }
.waiting li { margin:4px 0; } .waiting { color:var(--muted); font-size:14px; padding-left:18px; margin:8px 0 0; }
.iw-map { position:relative; width:100%; max-width:760px; aspect-ratio:1; margin-top:8px; background:#0b0d10; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.iw-t { position:absolute; width:18.75%; height:12.5%; }
.iw-t img { width:100%; height:100%; display:block; object-fit:cover; opacity:.35; filter:grayscale(.6); }
.iw-t.ok img { opacity:1; filter:none; }
.iw-t.cur { outline:2px solid var(--accent); outline-offset:-2px; }
.iw-t.cur img { opacity:.7; filter:none; }
.iw-t.bad { outline:2px dashed #f2c46b; outline-offset:-2px; }
.iw-cmp { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:8px; }
.iw-cmp figure { margin:0; } .iw-cmp img { width:100%; border-radius:6px; display:block; }
.iw-cmp figcaption { font-size:12px; color:var(--muted); margin-top:4px; }
@media (max-width:520px) { .iw-cmp { grid-template-columns:1fr; } }
@media (max-width:520px) { #sys { left:16px; right:16px; width:auto; } main { padding-bottom:200px; } }
</style></head><body>
<header><h1>Render Progress</h1><span class="sub" id="clock">connecting…</span></header>
<nav class="tabs" id="tabs"><button data-tab="soldiers">Soldiers &amp; robots</button><button data-tab="models">New 3D models<span class="badge" id="badge-models"></span></button><button data-tab="loadouts">Jet loadouts<span class="badge" id="badge-loadouts"></span></button><button data-tab="ironward">Ironward map<span class="badge" id="badge-ironward"></span></button></nav>
<main id="main"><div class="card empty">Waiting for data…</div></main>
<aside id="sys"><h3>Laptop <span class="state" id="sys-state">…</span></h3><div class="temp" id="sys-temp">– °C</div>
<div class="row"><span>CPU hottest / avg</span><b id="sys-cpu">–</b></div>
<div class="row"><span>CPU load</span><b id="sys-load">–</b></div><div class="mini"><i id="sys-load-bar"></i></div>
<div class="row"><span>GPU load</span><b id="sys-gpu">–</b></div><div class="mini"><i id="sys-gpu-bar"></i></div>
<div class="row"><span>Battery</span><b id="sys-batt">–</b></div></aside>
<script>
const fmt = s => s == null ? "–" : s < 60 ? Math.round(s) + " s" : s < 3600 ? Math.round(s / 60) + " min" : (s / 3600).toFixed(1) + " h";
const esc = t => String(t).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function soldier(s) {
  const pct = s.total ? 100 * s.done / s.total : 0;
  const finished = s.done >= s.total;
  const pill = finished ? '<span class="pill done">done</span>' : s.active ? '<span class="pill live">rendering ' + esc(s.current || "") + '</span>' : '<span class="pill">idle</span>';
  const rows = s.rows.map(r => {
    const p = r.total ? 100 * r.done / r.total : 0;
    const ok = r.done >= r.total;
    return '<tr class="' + (r.seq === s.current && s.active ? "cur" : "") + '"><td class="s">' + esc(r.seq) +
      ' <span class="tag">' + r.frames + '×' + r.facings + '</span></td><td class="b"><div class="bar' + (ok ? " ok" : "") +
      '"><i style="width:' + p.toFixed(1) + '%"></i></div></td><td class="n">' + r.done + ' / ' + r.total + '</td><td class="tag">' +
      (r.packed ? "in game files" : ok ? "packing…" : "") + '</td></tr>';
  }).join("");
  const strip = s.recent.map(p => '<img src="/img/' + encodeURI(p) + '" alt="">').join("");
  return '<section class="card"><div class="top"><div><div class="title"><h2>' + esc(s.id) + '</h2>' + pill + '</div>' +
    '<div class="big">' + pct.toFixed(1) + '%</div><div class="stats"><span><b>' + s.done + '</b> of ' + s.total + ' frames</span>' +
    '<span><b>' + (s.rate ? (s.rate * 60).toFixed(0) : "–") + '</b> frames/min</span><span>about <b>' + (finished ? "0 s" : fmt(s.eta)) +
    '</b> left</span><span>last frame <b>' + fmt(s.latest_age) + '</b> ago</span></div>' +
    '<div class="bar' + (finished ? " ok" : "") + '"><i style="width:' + pct.toFixed(1) + '%"></i></div><table>' + rows + '</table></div>' +
    '<div><div class="preview">' + (s.latest ? '<img src="/img/' + encodeURI(s.latest) + '" alt="latest frame">' : '') + '</div>' +
    '<div class="cap">latest: ' + esc(s.latest || "–") + '</div></div></div><div class="strip">' + strip + '</div></section>';
}
function overview(o) {
  const pd = 100 * o.done / o.total, pp = 100 * o.progress / o.total;
  const groups = [...new Set(o.units.map(u => u.group))];
  const cards = groups.map(g => '<div class="group">' + esc(g) + '</div><div class="units">' + o.units.filter(u => u.group === g).map(u => {
    const next = o.steps[u.steps.indexOf(false)];
    const label = u.state === "done" ? "in game" : u.job ? "now: " + esc(u.job.step) + (u.job.progress ? " (" + esc(u.job.progress) + ")" : u.render > 0 && u.render < 1 ? " (" + Math.round(u.render * 100) + "%)" : "")
      : u.state === "progress" ? "next: " + esc(next || "") + (u.render > 0 && u.render < 1 ? " (" + Math.round(u.render * 100) + "% rendered)" : "") : "not started";
    return '<div class="unit ' + u.state + '"><span class="nm">' + esc(u.name) + '</span><span class="id">' + esc(u.id) + '</span>' +
      '<div class="dots">' + u.steps.map((on, i) => '<span class="' + (i === u.active ? "act" : on ? "on" : "") + '" title="' + esc(o.steps[i]) + '"></span>').join("") + '</div>' +
      '<div class="st">' + label + '</div></div>';
  }).join("") + '</div>').join("");
  return '<section class="card"><div class="title"><h2>All units</h2><span class="pill">' + o.done + ' of ' + o.total + ' in game</span></div>' +
    '<div class="counts"><div class="count d"><div class="v">' + o.done + '</div><div class="l">done</div></div>' +
    '<div class="count p"><div class="v">' + o.progress + '</div><div class="l">in progress</div></div>' +
    '<div class="count"><div class="v">' + o.remaining + '</div><div class="l">remaining</div></div></div>' +
    '<div class="stack"><i class="d" style="width:' + pd + '%"></i><i class="p" style="width:' + pp + '%"></i></div>' + cards +
    '<div class="steps-key">' + o.steps.map((s, i) => '<span>' + (i + 1) + '. ' + esc(s) + '</span>').join("") + '<span>· green = done · red pulsing = running now</span></div></section>';
}
function jobsPanel(j) {
  const names = Object.fromEntries((window._roster || []).map(u => [u.id, u.name]));
  const body = j.length ? j.map(x => '<div class="job"><span class="k ' + (x.gpu === "full" ? "full" : x.gpu === "throttled" ? "throttled" : "") + '">' +
    esc(x.kind) + ' · GPU ' + esc(x.gpu) + '</span><span class="u">' + esc(names[x.unit] || x.unit) + ' — ' + esc(x.step) + '</span><span class="t">' +
    esc(x.elapsed) + '</span><span class="d">' + esc(x.label) + (x.progress ? ' · <b>' + esc(x.progress) + '</b>' : '') + '</span></div>').join("")
    : '<div class="empty">Nothing running.</div>';
  return '<section class="card"><div class="title"><h2>Running now</h2><span class="pill' + (j.length ? ' live' : '') + '">' + j.length + ' job' + (j.length === 1 ? '' : 's') + '</span></div>' + body + '</section>';
}
function images(q) {
  if (!q) return "";
  const pct = q.total ? 100 * q.done / q.total : 0;
  return '<section class="card"><div class="title"><h2>ChatGPT image queue</h2><span class="pill">' + esc(q.stopped || "running") +
    '</span></div><div class="stats"><span><b>' + q.done + '</b> done</span><span><b>' + q.pending + '</b> pending</span><span><b>' + q.failed +
    '</b> failed</span><span>updated <b>' + esc(q.updated || "–") + '</b></span></div><div class="bar' + (q.pending ? "" : " ok") +
    '"><i style="width:' + pct.toFixed(1) + '%"></i></div></section>';
}
function models(m) {
  if (!m) return "";
  if (m.error) return '<section class="card">Could not read sketchfab_models.py: ' + esc(m.error) + '</section>';
  const pct = m.frames_total ? 100 * m.frames_done / m.frames_total : 0;
  const all = m.done >= m.total;
  const order = {active: 0, progress: 1, waiting: 2, done: 3};
  const cards = [...m.units].sort((a, b) => order[a.state] - order[b.state]).map(u => {
    const p = u.total ? 100 * u.done / u.total : 0;
    const label = u.state === "done" ? '<span class="pill done">in game files</span>' : u.state === "active" ? '<span class="pill live">rendering</span>'
      : u.state === "progress" ? '<span class="pill">' + (u.done ? "paused" : "imported") + '</span>' : '<span class="pill">queued</span>';
    const nc = /NC/.test(u.licence);
    return '<div class="model ' + u.state + '"><div class="pic">' + (u.latest ? '<img loading="lazy" src="/mimg/' + encodeURI(u.latest) + '" alt="">' : 'not rendered yet') + '</div>' +
      '<div class="info"><div class="row"><span class="nm">' + esc(u.unit) + '</span>' + label + '</div>' +
      '<div class="md">' + esc(u.model) + (u.author ? ' · ' + esc(u.author) : '') + ' · <b>' + esc(u.group) + '</b></div>' +
      '<div class="bar' + (u.packed ? " ok" : "") + '"><i style="width:' + p.toFixed(1) + '%"></i></div>' +
      '<div class="row"><span>' + u.done + ' / ' + u.total + ' frames · ' + esc(u.kind) + '</span><span class="lic' + (nc ? " nc" : "") + '">' + esc(u.licence || "?") + '</span></div></div></div>';
  }).join("");
  const waiting = m.waiting.length ? '<div class="group">Downloaded, not set up yet (' + m.waiting.length + ')</div><ul class="waiting">' +
    m.waiting.map(w => '<li><b>' + esc(w[0]) + '</b> — ' + esc(w[1]) + '</li>').join("") + '</ul>' : "";
  return '<section class="card"><div class="top"><div><div class="title"><h2>Sketchfab models</h2><span class="pill' + (all ? " done" : m.rate ? " live" : "") + '">' +
    m.done + ' of ' + m.total + ' units done</span></div><div class="big">' + pct.toFixed(1) + '%</div>' +
    '<div class="stats"><span><b>' + m.frames_done + '</b> of ' + m.frames_total + ' frames</span><span><b>' + (m.rate ? (m.rate * 60).toFixed(1) : "–") +
    '</b> frames/min</span><span>about <b>' + (all ? "0 s" : fmt(m.eta)) + '</b> left (with cool-downs)</span><span>last frame <b>' + fmt(m.latest_age) + '</b> ago</span></div>' +
    '<div class="bar' + (all ? " ok" : "") + '"><i style="width:' + pct.toFixed(1) + '%"></i></div>' +
    '<div class="legend">HD light, 32 directions per unit (tanks and the V2 64 frames, helicopters 32 + 32 rotor steps). Yellow licence = non-commercial.</div></div>' +
    '<div><div class="preview">' + (m.latest ? '<img src="/mimg/' + encodeURI(m.latest) + '" alt="latest frame">' : '') + '</div><div class="cap">latest: ' + esc(m.latest || "–") + '</div></div></div>' +
    '<div class="models">' + cards + '</div>' + waiting + '</section>';
}
function loadouts(L) {
  if (!L) return "";
  if (L.error) return '<section class="card">Could not read the loadout table: ' + esc(L.error) + '</section>';
  const pct = L.total ? 100 * L.done / L.total : 0;
  const stepsDone = L.steps.filter(s => s.done).length;
  const steps = L.steps.map(s => '<li style="margin:4px 0">' + (s.done ? '<span style="color:#8fdca7">&#10003;</span> ' : '<span style="color:#9097a3">&#9675;</span> ') +
    '<span style="' + (s.done ? '' : 'color:var(--text)') + '">' + esc(s.name) + '</span></li>').join("");
  const label = {done: '<span class="pill done">in game</span>', active: '<span class="pill live">rendering</span>',
    rules: '<span class="pill">rendered, rules next</span>', waiting: '<span class="pill">queued</span>'};
  const order = {active: 0, rules: 1, waiting: 2, done: 3};
  const cards = [...L.jets].sort((a, b) => order[a.state] - order[b.state]).map(j =>
    '<div class="model ' + (j.state === "done" ? "done" : j.state === "active" ? "active" : "") + '"><div class="pic">' +
    (j.preview ? '<img loading="lazy" src="/mimg/' + encodeURI(j.preview) + '" alt="">' : 'not rendered yet') + '</div>' +
    '<div class="info"><div class="row"><span class="nm">' + esc(j.name) + '</span>' + label[j.state] + '</div>' +
    '<div class="md">' + j.weapons.map(esc).join(" · ") + '</div>' +
    '<div class="row"><span>' + (j.fighter ? "engages aircraft on its own" : j.strike ? "ground attack only" : "strike / bomber") + '</span><span class="lic">' +
    (j.overlays ? j.overlays + " weapon sprites" : "internal bay") + '</span></div></div></div>').join("");
  const timer = L.eta > 0 ? '<div class="stats" style="margin-top:10px"><span>time left <b class="countdown" data-end="' + (Date.now() + L.eta * 1000) +
    '" style="font-size:22px">' + clock(L.eta) + '</b></span><span>expected to finish at <b>' +
    new Date(Date.now() + L.eta * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) + '</b></span></div>' : '';
  return '<section class="card"><div class="title"><h2>Jet loadouts (IDEA-34)</h2><span class="pill' + (L.active ? " live" : L.done === L.total ? " done" : "") + '">' +
    L.done + ' of ' + L.total + ' jets in game</span></div><div class="big">' + pct.toFixed(0) + '%</div>' +
    '<div class="stats"><span><b>' + L.done + '</b> done</span><span><b>' + L.active + '</b> rendering</span><span><b>' + L.waiting + '</b> remaining</span>' +
    '<span><b>' + stepsDone + ' / ' + L.steps.length + '</b> tasks</span></div>' +
    '<div class="bar' + (L.done === L.total ? " ok" : "") + '"><i style="width:' + pct.toFixed(1) + '%"></i></div>' + timer +
    '<div class="group">Tasks</div><ul style="list-style:none;padding-left:4px;margin:6px 0 0">' + steps + '</ul>' +
    '<div class="group">Jets</div><div class="models">' + cards + '</div></section>';
}
function ironward(W) {
  if (!W) return '<section class="card">No Ironward repaint pieces yet.</section>';
  const pct = W.total ? 100 * W.done / W.total : 0, all = W.done === W.total;
  const tiles = W.pieces.map(p => {
    const kind = p.done ? "paint" : "render";
    const cur = p.name === W.current;
    return '<div class="iw-t' + (p.done ? " ok" : "") + (cur ? " cur" : "") + (p.score != null && p.score < 0.5 ? " bad" : "") +
      '" style="left:' + (p.x / 128 * 100) + '%;top:' + (p.y / 128 * 100) + '%;z-index:' + (p.done ? 2 : 1) + (cur ? ';z-index:3' : '') +
      '" title="' + esc(p.name) + (p.score != null ? " · drift score " + p.score : "") + '"><img loading="lazy" src="/iimg/' + kind + '/' + encodeURI(p.name) +
      '?' + (p.mtime || 0) + '" alt=""></div>';
  }).join("");
  const nw = W.newest;
  const cmp = nw ? '<div class="iw-cmp"><figure><img src="/iimg/render/' + encodeURI(nw) + '" alt=""><figcaption>Blender render</figcaption></figure>' +
    '<figure><img src="/iimg/paint/' + encodeURI(nw) + '?' + Date.now().toString().slice(0, -4) + '" alt=""><figcaption>ChatGPT repaint · ' + esc(nw) + '</figcaption></figure></div>' : '';
  const steps = W.steps.map(s => '<li style="margin:4px 0">' + (s.done ? '<span style="color:#8fdca7">&#10003;</span> ' : '<span style="color:#9097a3">&#9675;</span> ') +
    '<span style="' + (s.done ? '' : 'color:var(--text)') + '">' + esc(s.name) + '</span></li>').join("");
  const scores = W.pieces.filter(p => p.score != null).map(p => p.score);
  const avgScore = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2) : "–";
  const timer = W.eta > 0 && W.running ? '<span>time left <b class="countdown" data-end="' + (Date.now() + W.eta * 1000) + '">' + clock(W.eta) +
    '</b></span><span>finishes about <b>' + new Date(Date.now() + W.eta * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) + '</b></span>' : '';
  return '<section class="card"><div class="title"><h2>Ironward: ChatGPT repaint (style A)</h2><span class="pill' + (W.running ? " live" : all ? " done" : "") + '">' +
    (W.running ? "painting " + esc(W.current || "") : all ? "all pieces painted" : "stopped") + '</span></div>' +
    '<div class="big">' + pct.toFixed(0) + '%</div><div class="stats"><span><b>' + W.done + '</b> of ' + W.total + ' pieces</span>' +
    '<span><b>' + Math.round(W.avg) + ' s</b> per piece</span>' + timer + '<span>average drift score <b>' + avgScore + '</b> (0.5+ = faithful)</span>' +
    (W.drift.length ? '<span style="color:#ff8f86"><b>' + W.drift.length + '</b> drifted, will be redone</span>' : '') +
    (W.limit ? '<span style="color:#f2c46b">ChatGPT limit hit at <b>' + esc(W.limit) + '</b></span>' : '') + '</div>' +
    '<div class="bar' + (all ? " ok" : "") + '"><i style="width:' + pct.toFixed(1) + '%"></i></div>' +
    '<div class="group">The map filling in (dim = still the Blender render, red outline = painting now)</div><div class="iw-map">' + tiles + '</div>' +
    (cmp ? '<div class="group">Latest piece</div>' + cmp : '') +
    '<div class="group">Tasks</div><ul style="list-style:none;padding-left:4px;margin:6px 0 0">' + steps + '</ul></section>';
}
function clock(sec) {
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0");
}
setInterval(() => {
  for (const el of document.querySelectorAll(".countdown")) el.textContent = clock((+el.dataset.end - Date.now()) / 1000);
}, 1000);
let tab = "soldiers";
try { tab = localStorage.getItem("progress-tab") || "soldiers"; } catch (e) {}
let last = null;
function setTab(t) {
  tab = t;
  try { localStorage.setItem("progress-tab", t); } catch (e) {}
  for (const b of document.querySelectorAll("#tabs button")) b.classList.toggle("on", b.dataset.tab === t);
  if (last) draw(last);
}
document.getElementById("tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) setTab(b.dataset.tab); });
function pushPanel(p) {
  if (!p) return "";
  const mb = b => (b / 1e6).toFixed(0) + " MB";
  const pct = p.total ? Math.min(100, 100 * p.sent / p.total) : 0;
  const done = p.state === "done";
  const pill = done ? '<span class="pill done">pushed</span>' : p.state === "stopped" ? '<span class="pill">stopped – check the terminal</span>' : '<span class="pill live">uploading</span>';
  return '<section class="card"><div class="title"><h2>GitHub push</h2>' + pill + '</div>' +
    '<div class="big">' + (done ? 100 : pct).toFixed(1) + '%</div><div class="stats"><span><b>' + mb(p.sent) + '</b> of ~' + (p.total ? mb(p.total) : "?") + ' sent</span>' +
    (p.rate ? '<span><b>' + (p.rate / 1e6).toFixed(1) + ' MB/s</b></span>' : '') + (p.eta ? '<span>about <b>' + fmt(p.eta) + '</b> left</span>' : '') +
    (p.remote ? '<span>' + esc(p.remote) + '</span>' : '') + '</div><div class="bar' + (done ? " ok" : "") + '"><i style="width:' + (done ? 100 : pct).toFixed(1) + '%"></i></div>' +
    (done ? '' : '<div class="tag" style="margin-top:8px">Size is the local pack size, so the last few percent may finish early or run slightly over.</div>') + '</section>';
}
function draw(d) {
  const m = d.sketchfab;
  document.getElementById("badge-models").textContent = m && m.total ? m.done + "/" + m.total : "";
  const L = d.loadouts;
  document.getElementById("badge-loadouts").textContent = L && L.total ? L.done + "/" + L.total : "";
  const W = d.ironward;
  document.getElementById("badge-ironward").textContent = W && W.total ? W.done + "/" + W.total : "";
  document.getElementById("main").innerHTML = pushPanel(d.push) + jobsPanel(d.jobs) + (tab === "ironward" ? ironward(W) : tab === "loadouts" ? loadouts(L) : tab === "models" ? models(m) :
    overview(d.overview) + (d.soldiers.length ? d.soldiers.map(soldier).join("") : '<div class="card empty">No renders yet.</div>') + images(d.images));
}
function level(v, warm, hot) { return v == null ? "ok" : v >= hot ? "hot" : v >= warm ? "warm" : "ok"; }
function sys(x) {
  if (!x) return;
  const t = x.cpu, lv = level(t, 75, 90);
  const temp = document.getElementById("sys-temp");
  temp.textContent = t == null ? "– °C" : Math.round(t) + " °C"; temp.className = "temp c-" + lv;
  const st = document.getElementById("sys-state");
  const names = {nominal: "normal", fair: "warm", serious: "hot – slowing", critical: "critical"};
  st.textContent = names[x.thermal] || x.thermal || "?";
  st.className = "state c-" + (x.thermal === "critical" || x.thermal === "serious" ? "hot" : x.thermal === "fair" ? "warm" : "ok");
  document.getElementById("sys-cpu").textContent = t == null ? "–" : Math.round(t) + " / " + Math.round(x.cpu_avg) + " °C";
  for (const [id, v] of [["load", x.cpu_load], ["gpu", x.gpu_load]]) {
    document.getElementById("sys-" + id).textContent = v == null ? "–" : Math.round(v) + " %";
    const bar = document.getElementById("sys-" + id + "-bar");
    bar.style.width = (v || 0) + "%"; bar.className = "b-" + level(v, 60, 85);
  }
  document.getElementById("sys-batt").textContent = x.battery == null ? "–" : Math.round(x.battery) + " °C";
}
async function tick() {
  try {
    const d = await (await fetch("/status", {cache: "no-store"})).json();
    document.getElementById("clock").textContent = "updated " + d.time + " · refreshes every 3 s";
    sys(d.system);
    window._roster = d.overview.units;
    last = d;
    draw(d);
  } catch (e) { document.getElementById("clock").textContent = "server not reachable – is progress_server.py running?"; }
}
setTab(tab); tick(); setInterval(tick, 3000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/status":
            self.send(200, json.dumps(status()).encode(), "application/json")
        elif path.startswith("/iimg/"):
            parts = unquote(path[6:]).split("/")
            if len(parts) != 2 or parts[0] not in ("render", "paint") or not re.fullmatch(r"tile-\d+-\d+\.png", parts[1]):
                self.send(404, b"not found", "text/plain")
                return
            thumb = iw_thumb(parts[0], parts[1])
            if not thumb:
                self.send(404, b"not found", "text/plain")
                return
            self.send(200, open(thumb, "rb").read(), "image/jpeg")
        elif path.startswith("/mimg/"):
            full = os.path.normpath(os.path.join(MESH_RENDER, unquote(path[6:])))
            if not full.startswith(MESH_RENDER + os.sep) or not full.endswith(".png") or not os.path.exists(full):
                self.send(404, b"not found", "text/plain")
                return
            self.send(200, open(full, "rb").read(), "image/png")
        elif path.startswith("/img/"):
            rel = unquote(path[5:])
            full = os.path.normpath(os.path.join(RENDER, rel))
            if not full.startswith(RENDER + os.sep) or not re.search(r"\.png$", full) or not os.path.exists(full):
                self.send(404, b"not found", "text/plain")
                return
            self.send(200, open(full, "rb").read(), "image/png")
        else:
            self.send(404, b"not found", "text/plain")


if __name__ == "__main__":
    print(f"Render progress: http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
