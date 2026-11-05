#!/usr/bin/env python3
"""
Generates artsrc/prompts/gemini-prompts.md: one image-generation prompt per building, unit and
environment object in RedAlert Project X. Edit the tables below and re-run.
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gemini-prompts.md")

STYLE = {
    "allied": "Allied faction style: sleek modern 2026 NATO high-tech, angular composite armour, gunmetal grey and steel-blue panels, clean edges, glass sensor domes, small antennas",
    "soviet": "Soviet faction style: heavy brutalist 2026 Soviet industrial, thick riveted steel and weathered concrete, dark olive-grey with rust-red accents, exposed pipes, massive bolts, small red star emblems",
    "neutral": "Shared military style: modern 2026 military engineering, reinforced concrete, dark steel and olive-grey paint, hazard stripes, realistic wear and grime",
}

TEAM = "Paint the team-colour areas ({areas}) in flat pure bright green (#00FF00); use no other green anywhere on the object."

BUILDING = (
    "Game asset sheet for a top-down real-time strategy game, showing the same building twice, side by side in one wide image: "
    "LEFT half = the building intact and new, RIGHT half = the exact same building heavily battle-damaged. "
    "{desc} "
    "View (identical for both): classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees from the south, "
    "the front of the building faces the bottom of the image, no perspective distortion. "
    "The building's base covers a {w} x {h} square-tile footprint (width {w}, depth {h}). "
    "Both copies have exactly the same size, angle and position within their half, each centred in its half with a clear gap of empty background between them; nothing crosses the middle. "
    "{style}. Highly detailed, physically based realistic materials, crisp and sharp, subtle ambient occlusion. "
    "Lighting (identical for both): sun from the top-left; each copy casts a clearly visible soft dark shadow onto the magenta background, falling to the bottom-right. "
    "{team} "
    "Damaged copy: blackened scorch marks, cracked and broken armour panels, a partly collapsed roof section, bent and broken parts{extra}, "
    "exposed rebar and twisted metal, debris on the building itself, small fires and thin dark smoke; still standing and clearly the same building, not destroyed; "
    "its surviving team-colour areas stay green. "
    "Isolated on a flat, solid magenta (#FF00FF) background across the whole image: no ground, no grass, no terrain, no text, no labels, no logo, no watermark, no border, no dividing line. "
    "Wide image, aspect ratio 2:1."
)

UNIT = (
    "3D model reference image of a single {kind} for a real-time strategy game. {desc} "
    "View: three-quarter view from the front-left and slightly above (about 30 degrees), the whole {kind} visible and centred, orthographic, no perspective distortion. "
    "{style}. Highly detailed hard-surface design, realistic physically based materials, readable bold silhouette. "
    "Neutral even studio lighting, no dramatic shadows. "
    "{team} "
    "Isolated on a flat plain white background, no ground, no shadow on the background, no text, no logo, no watermark. Square image."
)

INFANTRY = (
    "3D character reference image of a single soldier for a real-time strategy game. {desc} "
    "Full body, standing in a neutral A-pose (arms slightly away from the body, legs apart), facing the camera, front view, orthographic, whole figure visible. "
    "{style}. Realistic proportions, detailed modern 2026 gear, realistic physically based materials. "
    "Neutral even studio lighting. "
    "{team} "
    "Isolated on a flat plain white background, no ground shadow, no text, no logo, no watermark. Portrait image (3:4)."
)

ENVIRONMENT = (
    "Game asset for a top-down real-time strategy game. {desc} "
    "View: classic RTS three-quarter overhead view, orthographic camera looking down at about 55 degrees, centred, whole object visible. "
    "Photorealistic, highly detailed, natural colours. Lighting: sun from the top-left, short soft shadow to the bottom-right. "
    "Isolated on a flat, solid magenta (#FF00FF) background: no ground, no text, no watermark. Square image."
)

# Building-specific damage details for the damaged prompt
DAMAGE_EXTRA = {
    "fact": ", the crane arm snapped and hanging",
    "powr": ", one cooling stack cracked and leaning, sparking cables",
    "apwr": ", one reactor vent blown open with an orange glow, sparking transformers",
    "proc": ", a silo punctured and leaking ore, the conveyor broken",
    "weap": ", the big vehicle door buckled and half torn off",
    "dome": ", the radome shell holed and cracked open",
    "hpad": ", the landing pad cracked and lights smashed",
    "afld": ", the hangar roof caved in",
    "syrd": ", a gantry crane collapsed",
    "spen": ", the pen roof partly collapsed",
    "pdox": ", the sphere flickering with cracked emitter arms",
    "iron": ", the emitter dish cracked and sparking",
    "tsla": ", the coil sparking erratically with broken rings",
    "gun": ", the cannon barrel bent",
    "agun": ", one cannon barrel snapped",
    "sam": ", one missile missing and the rail bent",
}

# id, name, footprint (w, h), style, team-colour areas, description
BUILDINGS = [
    ("fact", "Construction Yard", (3, 4), "neutral", "roof panels and the crane arm", "A Construction Yard: the main base building, a large fortified assembly plant with a big crane arm, landing pad and folded-down vehicle bay doors."),
    ("powr", "Power Plant", (2, 3), "neutral", "the roof trim and cooling stack bands", "A Power Plant: compact generator hall with two smoking cooling stacks, transformers and thick power cables."),
    ("apwr", "Advanced Power Plant", (3, 3), "neutral", "roof panels and stack bands", "An Advanced Power Plant: larger fusion-style generator complex with three glowing reactor cores visible through vents, cooling towers and transformer yard."),
    ("proc", "Ore Refinery", (3, 4), "neutral", "the roof stripes and silo bands", "An Ore Refinery: industrial ore-processing plant with a truck unloading dock at the front, conveyor, crushers and two storage silos."),
    ("silo", "Silo", (1, 1), "neutral", "a band around the top", "An Ore Silo: a single squat armoured storage tank with gauges and a hatch."),
    ("weap", "War Factory", (3, 3), "neutral", "roof stripes and door frame", "A War Factory: large vehicle production hall with a wide armoured roll-up door at the front, gantry cranes and vents on the roof."),
    ("fix", "Service Depot", (3, 3), "neutral", "the corner posts of the pad", "A Service Depot: open repair pad with a central lift platform, robotic repair arms and tool racks around it."),
    ("dome", "Radar Dome", (2, 3), "neutral", "the base trim", "A Radar Dome: radar station with a large white geodesic radome on a fortified bunker base, antennas and satellite dishes."),
    ("hpad", "Helipad", (2, 3), "allied", "the landing circle markings", "A Helipad: raised armoured helicopter landing pad with an H marking, lights and a small control booth."),
    ("afld", "Airfield", (3, 2), "soviet", "runway markings and hangar roof stripe", "An Airfield: short runway with an arched aircraft hangar, fuel tanks and a radio mast."),
    ("tent", "Allied Barracks", (2, 3), "allied", "the roof stripes and flag", "Allied Barracks: modern military training barracks, modular prefab buildings with a flagpole and sandbag entrance."),
    ("barr", "Soviet Barracks", (2, 3), "soviet", "the roof stripes and banner", "Soviet Barracks: heavy concrete barracks bunker with a watchtower, banner and barbed wire."),
    ("kenn", "Kennel", (1, 1), "soviet", "the roof", "A Kennel: small reinforced dog kennel with a fenced run."),
    ("syrd", "Naval Yard", (3, 3), "allied", "dock edge markings and crane", "A Naval Yard: floating shipyard dock with gantry cranes, built over water (draw the water area inside the dock in dark blue)."),
    ("spen", "Sub Pen", (3, 3), "soviet", "the pen roof stripes", "A Sub Pen: armoured submarine pen with a covered bay opening onto water (draw water inside the pen in dark blue)."),
    ("atek", "Allied Tech Center", (2, 3), "allied", "roof panels", "An Allied Tech Center: futuristic research laboratory with glass domes, satellite uplink and server towers."),
    ("stek", "Soviet Tech Center", (3, 3), "soviet", "roof panels", "A Soviet Tech Center: massive secret research institute with reactor towers, Tesla antennas and thick armoured walls."),
    ("pdox", "Chronosphere", (2, 2), "allied", "the base ring", "A Chronosphere: superweapon with a glowing blue time-distortion sphere held by curved metal arms above a high-tech platform."),
    ("iron", "Iron Curtain", (2, 2), "soviet", "the base ring", "An Iron Curtain: superweapon with a huge red-glowing energy emitter dish on a massive armoured pylon."),
    ("mslo", "Missile Silo", (2, 1), "neutral", "the hatch rim", "A Strategic Launch Facility for a fictional sci-fi strategy game: a low armoured concrete bunker with two large sliding hatch doors set into its flat roof, slightly open, a glowing sci-fi rocket nose cone (sleek, white, futuristic) peeking out, warning lights and antenna masts around it."),
    ("gap", "Gap Generator", (1, 1), "allied", "the base", "A Gap Generator: tall slim tower with a rotating cloaking-field emitter at the top."),
    ("pbox", "Pillbox", (1, 1), "allied", "the roof", "A Pillbox: small round concrete bunker with a machine-gun slit."),
    ("hbox", "Camo Pillbox", (1, 1), "allied", "a small roof hatch", "A Camouflaged Pillbox: low bunker covered in camouflage netting and foliage (use brown and khaki, not green)."),
    ("gun", "Turret", (1, 1), "allied", "turret top plate", "A Turret: armoured gun emplacement with a rotating cannon turret on a concrete base, cannon pointing toward the bottom-right."),
    ("agun", "AA Gun", (1, 1), "allied", "the gun base", "An AA Gun: anti-aircraft emplacement with twin rapid-fire cannons angled up toward the sky."),
    ("ftur", "Flame Tower", (1, 1), "soviet", "the tower band", "A Flame Tower: squat armoured tower with a flamethrower nozzle and fuel tanks."),
    ("tsla", "Tesla Coil", (1, 1), "soviet", "the base ring", "A Tesla Coil: tall metal coil tower with crackling blue electric arcs at the top."),
    ("sam", "SAM Site", (2, 1), "soviet", "launcher rails", "A SAM Site: surface-to-air missile launcher with four missiles on a rotating rail, in a sandbagged pit."),
]

# id, name, kind, style, team areas, description
VEHICLES = [
    ("1tnk", "Light Tank", "tank", "allied", "side skirt stripes and turret band", "A fast light tank with a small turret and slim 90mm gun."),
    ("2tnk", "Medium Tank", "tank", "allied", "side skirt stripes and turret band", "A modern main battle tank (Leopard 2 / Abrams class) with an angular turret and 120mm gun."),
    ("3tnk", "Heavy Tank", "tank", "soviet", "side skirt stripes and turret band", "A heavy Soviet tank with a large rounded turret and twin 105mm cannons."),
    ("4tnk", "Mammoth Tank", "tank", "soviet", "side skirt stripes and turret band", "A huge Mammoth Tank: four tracks, twin heavy cannons and twin missile pods on the turret."),
    ("arty", "Artillery", "vehicle", "allied", "barrel band and hull stripe", "A self-propelled artillery vehicle with a long-range howitzer."),
    ("v2rl", "V2 Rocket Launcher", "vehicle", "soviet", "rocket fins and cab stripe", "A truck-mounted ballistic rocket launcher carrying one large rocket on an erector."),
    ("harv", "Ore Truck", "vehicle", "neutral", "cab roof and bin stripe", "A large armoured ore harvester truck with a front scoop and a big ore bin."),
    ("mcv", "Mobile Construction Vehicle", "vehicle", "neutral", "roof panels", "A Mobile Construction Vehicle: big multi-axle armoured truck carrying a folded construction yard and crane."),
    ("jeep", "Ranger", "vehicle", "allied", "hood stripe", "A fast armoured 4x4 scout vehicle with a roof-mounted machine gun."),
    ("apc", "Armored Personnel Carrier", "vehicle", "soviet", "hull side stripe", "A tracked armoured personnel carrier with a small machine-gun turret and rear troop door."),
    ("mnly", "Minelayer", "vehicle", "neutral", "hull stripe", "A tracked minelaying vehicle with a mine-dispensing chute at the back."),
    ("truk", "Supply Truck", "vehicle", "neutral", "cargo cover stripe", "A military supply truck with a covered cargo bed full of crates."),
    ("mgg", "Mobile Gap Generator", "vehicle", "allied", "hull stripe", "A tracked vehicle carrying a tall rotating cloaking-field emitter."),
    ("mrj", "Mobile Radar Jammer", "vehicle", "allied", "hull stripe", "A tracked electronic-warfare vehicle with a large jamming antenna array."),
    ("ttnk", "Tesla Tank", "tank", "soviet", "hull stripe", "A tank with a Tesla coil weapon instead of a cannon, blue electric glow."),
    ("ftrk", "Mobile Flak", "vehicle", "soviet", "cab stripe", "A truck with a rapid-fire anti-aircraft flak cannon on the back."),
    ("dtrk", "Demolition Truck", "vehicle", "soviet", "cab stripe", "A heavy armoured truck carrying a large sealed sci-fi energy core container with hazard-stripe warning markings and blinking lights."),
    ("ctnk", "Chrono Tank", "tank", "allied", "hull stripe", "A futuristic hover-style tank with missile pods and blue chrono-shift emitters."),
    ("qtnk", "MAD Tank", "tank", "soviet", "hull stripe", "A tank carrying a big seismic shockwave generator instead of a turret."),
    ("stnk", "Phase Transport", "vehicle", "allied", "hull stripe", "A stealth armoured transport with angular faceted panels and a missile launcher."),
]

AIRCRAFT = [
    ("mig", "MiG Attack Plane", "jet aircraft", "soviet", "tail fin and wing tips", "A Soviet MiG-style ground-attack jet with missiles under the wings, top view emphasised."),
    ("yak", "Yak Attack Plane", "propeller aircraft", "soviet", "tail fin and wing tips", "A Yak-style propeller ground-attack plane with wing machine guns."),
    ("tran", "Chinook", "transport helicopter", "neutral", "tail band", "A twin-rotor Chinook-style transport helicopter."),
    ("heli", "Longbow", "attack helicopter", "allied", "tail band", "An Apache Longbow-style attack helicopter with Hellfire missiles."),
    ("mh60", "Black Hawk", "helicopter", "allied", "tail band", "A Black Hawk-style utility helicopter with door guns."),
]

SHIPS = [
    ("ss", "Submarine", "submarine", "soviet", "conning tower band", "A Soviet attack submarine, surfaced, long dark hull."),
    ("msub", "Missile Submarine", "submarine", "soviet", "conning tower band", "A large Soviet missile submarine with vertical launch hatches on the deck."),
    ("dd", "Destroyer", "warship", "allied", "funnel band and deck stripe", "A modern destroyer warship with a forward gun turret and anti-sub launchers."),
    ("ca", "Cruiser", "warship", "allied", "funnel band and deck stripe", "A large cruiser warship with two heavy gun turrets."),
    ("lst", "Transport", "landing craft", "neutral", "deck stripe", "An amphibious landing ship with a front ramp."),
    ("pt", "Gunboat", "patrol boat", "allied", "deck stripe", "A fast patrol gunboat with a deck cannon."),
]

INFANTRY_LIST = [
    ("e1", "Rifle Infantry", "neutral", "shoulder patches and helmet band", "A modern rifleman with assault rifle, helmet and body armour."),
    ("e2", "Grenadier", "soviet", "shoulder patches and helmet band", "A Soviet grenadier with a bag of hand grenades and a heavy coat."),
    ("e3", "Rocket Soldier", "neutral", "shoulder patches and helmet band", "A soldier carrying a shoulder-fired rocket launcher."),
    ("e4", "Flame Infantry", "soviet", "shoulder patches and tank straps", "A flamethrower trooper with fuel tanks on the back and a fire-resistant suit."),
    ("e6", "Engineer", "neutral", "vest panels and helmet band", "A combat engineer with a tool bag, hard hat and utility vest."),
    ("e7", "Tanya", "allied", "armband", "Tanya, an elite female commando with dual pistols, tactical gear, confident pose."),
    ("medi", "Medic", "allied", "armband", "A field medic with a medical backpack (red cross on white)."),
    ("mech", "Mechanic", "allied", "armband", "A field mechanic with a wrench and tool belt."),
    ("thf", "Thief", "soviet", "armband", "A stealthy thief in dark clothing with a loot bag."),
    ("shok", "Shock Trooper", "soviet", "shoulder pads", "A Soviet shock trooper in heavy armour with a backpack Tesla gun, blue electric glow."),
    ("spy", "Spy", "allied", "tie", "A spy in a dark suit and trench coat."),
]

DOG = ("dog", "Attack Dog", "A muscular military attack dog (German shepherd) in a tactical harness, standing side view.")

ENV = [
    ("tree-pine", "Pine trees (set of 4)", "A sheet of four different single pine trees, evenly spaced in a 2x2 grid, each tree isolated."),
    ("tree-oak", "Broadleaf trees (set of 4)", "A sheet of four different single broadleaf (oak / maple) trees, evenly spaced in a 2x2 grid, each tree isolated."),
    ("tree-dead", "Dead trees (set of 4)", "A sheet of four different dead, leafless trees, evenly spaced in a 2x2 grid."),
    ("ore", "Gold ore (4 sizes)", "A sheet of four patches of glittering gold ore crystals on the ground, from a small sparse patch to a large dense pile, evenly spaced in a 2x2 grid."),
    ("gems", "Gems (4 sizes)", "A sheet of four patches of sparkling multicoloured gem crystals, from a small sparse patch to a large dense cluster, evenly spaced in a 2x2 grid."),
    ("rocks", "Boulders (set of 4)", "A sheet of four different large boulders / rock outcrops, evenly spaced in a 2x2 grid."),
]


def section(title, intro=""):
    return f"\n## {title}\n\n{intro}\n" if intro else f"\n## {title}\n"


def entry(i, name, file, prompt, extra=""):
    s = f"### {i}. {name}\nSave as: `{file}`\n\n```\n{prompt}\n```\n"
    if extra:
        s += f"\n{extra}\n"
    return s


def main():
    out = [
        "# RedAlert Project X - AI art prompts (ChatGPT or Gemini)",
        "",
        "Prompts for every building, unit and environment object. Paste one prompt per image.",
        "",
        "**How to use**",
        "",
        "1. Start a new ChatGPT (or Gemini) chat for each object, paste the prompt and generate. ChatGPT follows the two-version building prompt best.",
        "2. If it looks right, download it and rename it to the **Save as** name. Put buildings in `~/Downloads/project_x/buildings/`, units in `~/Downloads/project_x/units/` and environment art in `~/Downloads/project_x/environment/`.",
        "3. Each building prompt makes **one wide image with both versions**: intact on the left, battle-damaged on the right. Reject it if the two copies differ in angle or size, touch each other, or there is a line between them.",
        "4. Reject an image if it changes the camera angle, adds ground or grass, has a non-magenta/white background, or uses green outside the team-colour areas. Just regenerate.",
        "5. Keep everything in one consistent style: attach the approved Construction Yard image (`artsrc/buildings/src/fact-chatgpt.png`, or `Intact and Ruined Industrial Base.png` in Downloads) to each new chat and add: *\"Match the style, camera angle, lighting and level of detail of the attached image, but draw the building described below.\"*",
        "6. File names: name each download after its **Save as** name (for example `weap.png`), or tell me which building each file is.",
        "",
        "**What happens next (my side)**",
        "",
        "- **Buildings and environment** are used directly: I remove the magenta background, scale them to the footprint, add player colours (the green areas) and make the build-up animation and sidebar icons.",
        "- **Units, aircraft, ships and infantry** turn in 32 directions, so one picture is not enough. Feed each image into a free image-to-3D tool (for example Tripo AI, Meshy or Hunyuan3D) and download the result as `.glb` with the same name. Infantry: also upload the model to Mixamo (free) for a skeleton and walk / shoot / die animations. My Blender pipeline renders every direction and animation from the 3D files.",
        "",
        "Team colour: the pure green (#00FF00) areas are replaced with each player's colour in game, so keep green only where the prompt says.",
    ]

    n = 1
    out.append(section("Buildings", "Wide 2:1 images, intact (left) + damaged (right). Footprints are in map cells (width x depth)."))
    for bid, name, (w, h), style, areas, desc in BUILDINGS:
        prompt = BUILDING.format(desc=desc, w=w, h=h, style=STYLE[style], team=TEAM.format(areas=areas),
                                 extra=DAMAGE_EXTRA.get(bid, ""))
        out.append(entry(n, f"{name} ({w}x{h})", f"{bid}.png", prompt))
        n += 1

    out.append(section("Vehicles", "Model reference images for image-to-3D. Save the 3D result as `<name>.glb`."))
    for vid, name, kind, style, areas, desc in VEHICLES:
        prompt = UNIT.format(kind=kind, desc=desc, style=STYLE[style], team=TEAM.format(areas=areas))
        out.append(entry(n, name, f"{vid}.png  ->  {vid}.glb", prompt))
        n += 1

    out.append(section("Aircraft"))
    for aid, name, kind, style, areas, desc in AIRCRAFT:
        prompt = UNIT.format(kind=kind, desc=desc, style=STYLE[style], team=TEAM.format(areas=areas))
        out.append(entry(n, name, f"{aid}.png  ->  {aid}.glb", prompt))
        n += 1

    out.append(section("Ships", "The game shows ships on water from above; the reference image only needs the ship itself."))
    for sid, name, kind, style, areas, desc in SHIPS:
        prompt = UNIT.format(kind=kind, desc=desc, style=STYLE[style], team=TEAM.format(areas=areas))
        out.append(entry(n, name, f"{sid}.png  ->  {sid}.glb", prompt))
        n += 1

    out.append(section("Infantry", "Character reference images (A-pose) for image-to-3D and Mixamo rigging."))
    for iid, name, style, areas, desc in INFANTRY_LIST:
        prompt = INFANTRY.format(desc=desc, style=STYLE[style], team=TEAM.format(areas=areas))
        out.append(entry(n, name, f"{iid}.png  ->  {iid}.glb", prompt))
        n += 1
    did, name, desc = DOG
    dog_prompt = (f"3D model reference image of a single animal for a real-time strategy game. {desc} "
                  "Whole animal visible, orthographic, neutral even studio lighting. Isolated on a flat plain white background, "
                  "no ground shadow, no text, no watermark. Square image.")
    out.append(entry(n, name, f"{did}.png  ->  {did}.glb", dog_prompt))
    n += 1

    out.append(section("Environment", "Sheets with four variants each; I cut them apart."))
    for eid, name, desc in ENV:
        out.append(entry(n, name, f"{eid}.png", ENVIRONMENT.format(desc=desc)))
        n += 1

    out.append(section("Not included (on purpose)",
                       "- **Fake buildings** reuse the real building art.\n"
                       "- **Walls and fences** (sandbags, wire, concrete) join up in 16 shapes; I'll build those from textures.\n"
                       "- **Civilian buildings, campaign-only units (ants, zombies)** and **sidebar icons**: icons are rendered from the art above; the rest can come later."))

    open(OUT, "w").write("\n".join(out) + "\n")
    print(f"wrote {OUT} ({n - 1} prompts)")


if __name__ == "__main__":
    main()
