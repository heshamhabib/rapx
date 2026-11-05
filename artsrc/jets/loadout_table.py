"""
IDEA-34 loadout table: what each jet carries, fires and loses from its sprite. The single source for the station
overlays (artsrc/units/meshes/import_sketchfab.py + render_loadout.py) and the rules (artsrc/jets/make_loadouts.py).

Per unit:
  real_length  metres, sizes the procedural weapons against the model
  gun          gun weapon (weapons/jet-ordnance.yaml JetGun.<gun>) or None
  stations     outer first (fired first); every station is a left/right pair unless "centre": True
     weapon    family (JetAAM.Short, JetAAM.Medium, JetAAM.Long, JetAGM, JetBomb, JetGBU, JetRockets)
     model     (x, y, z, rx, ry, rz): the right-hand station on the model, unit coordinates (survey:
               artsrc/jets/loadouts/<unit>.png/.json); every model store centred within the tolerances joins it
               (a triple rack is one station), mirrored for the left
     add       procedural weapon kind (artsrc/jets/ordnance.py) at "at" (x, y): hung under the airframe there;
               y "lead" hangs it forward from the wing's leading edge (its front half shows from above)
     shots     missiles per side (default 1; a triple rack fires 3 before its sprite goes)
     internal  True: a weapons bay (stealth jets, bombers): shots in total, nothing shown on the sprite
  strike     True: never engages aircraft on its own even if it carries air-to-air missiles
"""

LOADOUTS = {
    # F-16D: wingtip and outer AMRAAMs, triple Maverick racks; tanks stay on as scenery
    "jet.f16": {"real_length": 15.06, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Medium", "model": (2.32, -0.6, 1.37, 0.12, 0.6, 0.15)},
        {"weapon": "JetAAM.Medium", "model": (1.95, -0.6, 1.17, 0.1, 0.7, 0.15)},
        {"weapon": "JetAGM", "model": (1.46, -0.55, 1.05, 0.2, 0.6, 0.2), "shots": 3},
    ]},
    # A-10C: six Mavericks; the GAU-8 is the real weapon
    "jet.a10": {"real_length": 16.26, "gun": "GAU8", "stations": [
        {"weapon": "JetAGM", "model": (1.59, 0.62, 0.16, 0.2, 0.6, 0.15)},
        {"weapon": "JetAGM", "model": (0.72, 0.62, 0.13, 0.2, 0.6, 0.15)},
        {"weapon": "JetAGM", "model": (0.25, 0.6, 0.13, 0.15, 0.6, 0.15)},
    ]},
    # F-14A: the model came clean; Sidewinders on the glove pylons, four Phoenix under the fuselage
    "jet.f14": {"real_length": 19.1, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Short", "add": "aim9", "at": (1.35, "lead")},
        {"weapon": "JetAAM.Long", "add": "aim54", "at": (1.0, "lead")},
    ]},

    # --- Fighters with weapons on their models -------------------------------------------------------------------
    # KF-21: wingtip IRIS-Ts, Meteors semi-recessed under the fuselage
    "jet.f22": {"real_length": 16.9, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Short", "model": (2.27, -0.91, 0.74, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Medium", "model": (0.38, -0.03, 0.47, 0.12, 0.6, 0.15)},
    ]},
    # Harrier: Sidewinders outboard, rocket pods inboard: close support
    "jet.harrier": {"real_length": 14.1, "gun": "GSh30", "strike": True, "stations": [
        {"weapon": "JetAAM.Short", "model": (1.43, 0.23, 0.5, 0.15, 0.5, 0.15)},
        {"weapon": "JetRockets", "model": (0.85, 0.41, 0.53, 0.15, 0.5, 0.15), "shots": 4},
    ]},
    # Mirage 2000: Magic II outboard, MICA inboard; DEFA 30 mm
    "jet.m2000": {"real_length": 14.4, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "model": (1.52, -0.92, 0.1, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Medium", "model": (0.44, -1.48, 0.11, 0.15, 0.6, 0.2)},
    ]},
    # MiG-23: R-60 short-range and R-24 medium-range
    "jet.mig23": {"real_length": 16.7, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "add": "r73", "at": (1.0, "lead")},  # the model has one only, on the right
        {"weapon": "JetAAM.Medium", "model": (0.67, -0.08, 0.84, 0.15, 0.6, 0.2)},
    ]},
    # MiG-25 interceptor: four big R-40s, the fastest jet; no gun, never strikes the ground
    "jet.mig25": {"real_length": 19.75, "gun": None, "stations": [
        {"weapon": "JetAAM.Long", "model": (2.38, -1.88, 0.9, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Long", "model": (1.6, -0.8, 0.7, 0.15, 0.6, 0.2)},
    ]},
    # F-5E Tiger II: two wingtip Sidewinders and two 20 mm guns: cheap and light
    "jet.saeqeh": {"real_length": 14.45, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Short", "model": (1.84, -1.04, 0.58, 0.15, 0.6, 0.15)},
    ]},
    # Su-27: wingtip R-73s plus R-27s added under the wings
    "jet.su27": {"real_length": 21.9, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "model": (2.99, 1.21, 1.11, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Medium", "add": "r77", "at": (1.9, "lead")},
        {"weapon": "JetAAM.Medium", "add": "r77", "at": (1.3, "lead")},
    ]},
    # MiG-35: R-73s under the wings, R-77s added inboard
    "mig": {"real_length": 17.3, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "model": (1.84, -1.33, 0.79, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Short", "model": (0.75, -1.23, 0.88, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Medium", "add": "r77", "at": (1.2, "lead")},
    ]},
    # Sea Vixen: Firestreaks and rocket packs
    "jet.seavixen": {"real_length": 16.94, "gun": None, "stations": [
        {"weapon": "JetAAM.Short", "model": (2.11, -0.6, 0.72, 0.15, 0.6, 0.2)},
        {"weapon": "JetRockets", "model": (1.03, 0.13, 0.68, 0.15, 0.6, 0.2), "shots": 4},
    ]},
    # F-4 Phantom: Sparrow / Sidewinder era, Maverick racks inboard
    "jet.f4": {"real_length": 19.2, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Short", "add": "aim9", "at": (1.8, "lead")},
        {"weapon": "JetAGM", "model": (0.97, 0.59, 0.16, 0.2, 0.6, 0.15), "shots": 2},
    ]},

    # --- Fighters whose models came without weapons: procedural ones --------------------------------------------
    "jet.f104": {"real_length": 16.7, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Short", "add": "aim9", "at": (1.15, "lead")},
    ]},
    "jet.mig21": {"real_length": 14.5, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "add": "r73", "at": (1.3, "lead")},
        {"weapon": "JetAAM.Short", "add": "r73", "at": (0.9, "lead")},
    ]},
    "jet.typhoon": {"real_length": 15.96, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "add": "aim9", "at": (1.95, "lead")},
        {"weapon": "JetAAM.Medium", "add": "aim120", "at": (1.45, "lead")},
        {"weapon": "JetGBU", "add": "gbu", "at": (0.95, "lead")},
    ]},
    "jet.rafale": {"real_length": 15.27, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "add": "aim9", "at": (1.9, "lead")},
        {"weapon": "JetAAM.Medium", "add": "aim120", "at": (1.35, "lead")},
        {"weapon": "JetAGM", "add": "agm65", "at": (0.85, "lead")},
    ]},
    "jet.su35": {"real_length": 21.9, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Short", "model": (2.84, -1.44, 1.04, 0.15, 0.6, 0.2)},
        {"weapon": "JetAAM.Medium", "add": "r77", "at": (1.9, "lead")},
        {"weapon": "JetAAM.Long", "add": "aim54", "at": (1.2, "lead")},
    ]},
    # --- Ground attack ---------------------------------------------------------------------------------------------
    "jet.su25": {"real_length": 15.53, "gun": "GSh30", "strike": True, "stations": [
        {"weapon": "JetRockets", "add": "pod", "at": (2.3, "lead"), "shots": 4},
        {"weapon": "JetAGM", "add": "agm65", "at": (1.6, "lead")},
        {"weapon": "JetBomb", "add": "mk82", "at": (1.0, "lead")},
    ]},
    "jet.l39": {"real_length": 12.13, "gun": "GSh30", "strike": True, "stations": [
        {"weapon": "JetRockets", "add": "pod", "at": (1.3, "lead"), "shots": 4},
    ]},

    # --- Weapons bays: stealth jets, bombers, drones -------------------------------------------------------------
    "jet.j20": {"real_length": 20.4, "gun": None, "stations": [
        {"weapon": "JetAAM.Medium", "internal": True, "shots": 4},
        {"weapon": "JetAAM.Short", "internal": True, "shots": 2},
    ]},
    "jet.yf23": {"real_length": 20.6, "gun": "M61", "stations": [
        {"weapon": "JetAAM.Medium", "internal": True, "shots": 4},
        {"weapon": "JetAAM.Short", "internal": True, "shots": 2},
    ]},
    "jet.su47": {"real_length": 22.6, "gun": "GSh30", "stations": [
        {"weapon": "JetAAM.Medium", "internal": True, "shots": 4},
        {"weapon": "JetAAM.Short", "internal": True, "shots": 2},
    ]},
    "jet.f117": {"real_length": 20.1, "gun": None, "stations": [
        {"weapon": "JetGBU", "internal": True, "shots": 2},
    ]},
    "jet.b2": {"real_length": 21.0, "gun": None, "stations": [
        {"weapon": "JetGBU", "internal": True, "shots": 8},
    ]},
    "jet.b52": {"real_length": 48.5, "gun": None, "stations": [
        {"weapon": "JetBomb", "internal": True, "shots": 14},
    ]},
    "jet.vulcan": {"real_length": 29.6, "gun": None, "stations": [
        {"weapon": "JetBomb", "internal": True, "shots": 10},
    ]},
    "jet.tu160": {"real_length": 54.1, "gun": None, "stations": [
        {"weapon": "JetGBU", "internal": True, "shots": 6},
    ]},
    "jet.grom": {"real_length": 10.0, "gun": None, "stations": [
        {"weapon": "JetGBU", "internal": True, "shots": 2},
    ]},
    "jet.x47": {"real_length": 11.6, "gun": None, "stations": [
        {"weapon": "JetGBU", "internal": True, "shots": 2},
    ]},
}
