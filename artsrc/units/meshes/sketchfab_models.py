"""
Settings for the downloaded Sketchfab models (artsrc/units/meshes/glb/sketchfab/), shared by
import_sketchfab.py (Blender) and make_sketchfab.py (the driver). Credits for every model: mods/rapx/CREDITS.

Per unit id (the sprite it replaces):
  name     shown on the progress page (artsrc/units/soldiers/progress_server.py)
  src      glTF file under glb/sketchfab/
  kind     tank (hull 0-31 + turret 32-63), vehicle (body 0-31), rocket (v2rl: body with rocket 0-31, empty
           launcher 32-63), air (no ground shadow, the engine draws it), heli (air + separate rotor sheets),
           ship (body 0-31 cut at the waterline)
  out      sprite sheet name in mods/rapx/bits/hd/units/ (default: unit id)
  yaw      degrees counter-clockwise that turn the model's nose to +Y
  length   length in Blender units of the whole model (or of `span`, a model-unit Y range after the yaw);
           the same lengths the AI models used (meshes/make.sh), so the units keep their size in game
  frame    frame size before the 2x (ground) or 2.6x (air) pixel factor
  drop     parts (object names) left out; drop_materials: parts with these materials left out; drop_contains:
           parts whose name contains one of these
  scrub_white  repaint near-white texture markings (another nation's insignia) in the body colour
  paint    national paint (display RGB 0-1): its hue/saturation over the model's shading (paint_strength 0-1,
           default 0.85), then paint_value multiplies the brightness (IDEA-17 shared launcher chassis)
  attach   {"src", "at" (x, y, z model units after the yaw), "height", "plate" (radius, thickness) optional}: a
           second model mounted on this one, optionally on a steel turret plate
           (tanks: with "replace_turret" it is the turret; "muzzle_top" puts the muzzle at its top)
  team     where the team colour goes: "materials" (names), "box" (x0, x1, y0, y1, z0, z1 as 0-1 fractions of
           the model's bounds after the yaw; "boxes": a list of them; "box_materials" limits it to those
           materials), "greens" (the model's own green paint)
  darken   multiplies the model's paint (0-1), e.g. a white navy finish made gunmetal like the concept
  tank     "turret" parts, "cut" (z, model units after the yaw: faces of the other parts above it within
           "ring" (rx, ry) around "pivot" (x, y) go with the turret, plus the gun in front), "muzzle" part
  rocket   parts that are the rocket (hidden on the empty launcher frames); rocket_above {part: z} adds the
           loose pieces of a shared part whose centre is above z (model units)
  spin     tank kind: the turret is a spinner (radar dish): rendered as one turn in this many frames (default 32
           = turret facings)
  rotors   one list of parts per rotor (each gets its own hub offset; all rotors share one sheet)
  keep_near ((x, y), r): keep only the parts centred within r of (x, y), model units after the yaw
  snap     "length" / "wing": turn the plan view's long axis (fuselage, or the wings when they are longer)
           exactly onto the nose direction, for models posed at an angle
  fix_normals  recalculate face normals outwards and drop custom normals (SketchUp exports with flipped faces)
  waterline  ship kind: z (model units) of the waterline; faces below it are cut off, so the hull sits on the
           water (the render's ground)
  blades   rotor blade count (sets the slow-rotor frames to one blade period; default 4)
"""

JET_BOX = (0.0, 1.0, 0.0, 0.3, 0.55, 1.0)  # tail fins: rear 30%, top 45%
HELI_BOX = (0.0, 1.0, 0.0, 0.35, 0.0, 1.0)  # tail boom: rear 35%
FLAT_BOX = (0.0, 1.0, 0.0, 0.12, 0.0, 1.0)  # flying wings (no tail): the trailing edge only

MODELS = {
    # Heavy Tank: "T-72B3 Main Battle Tank" by Muhamad Mirza Arrafi, CC-BY-4.0. Has its own recolour settings
    # (texture pass in import_sketchfab.py: team / paint / markings) from before the shader team colour.
    "3tnk": {
        "src": "t72b3/scene.gltf", "kind": "tank", "frame": 192,
        "span": (-4.4, 2.87), "length": 8.6,
        "drop": ["Object_15", "Object_2"],  # anti-drone slat roof over the turret; white cross decal
        "tank": {"turret": ["Object_5", "Object_8", "Object_10", "Object_6", "Object_7"],
                 "mixed": {"Object_11": 0.84}, "ring": (1.95, 1.95), "pivot": (0.0, -0.9), "muzzle": "Object_5"},
        "legacy_paint": {"team": ["bronya.1", "misc_a.5"],
                         "paint": ["chassis.0", "chassis.2", "misc_a.3", "misc_b.0", "wheel_big_0.0"],
                         "markings": ["bronya.1"]},
    },
    # Mammoth Tank: "Red Alert 2 - Soviet Apocalypse Tank V2" by Ska-Ara, CC-BY-4.0
    "4tnk": {
        "src": "inbox/red_alert_2_-_soviet_apocalypse_tank_v2/scene.gltf", "kind": "tank", "frame": 224,
        "yaw": -90, "span": (-8.35, 1.88), "length": 9.6,
        "tank": {"turret": [], "cut": 1.2, "ring": (2.0, 2.0), "pivot": (0.0, -2.6)},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.55, 1.0)},  # turret roof
    },
    # V2 Rocket Launcher: "Red Alert 2 - Soviet V3 rocket launcher" by Ska-Ara, CC-BY-4.0
    "v2rl": {
        "src": "inbox/red_alert_2_-__soviet_v3_rocket_launcher/scene.gltf", "kind": "rocket", "frame": 224,
        "yaw": 180, "length": 9.75,  # the rocket points forward over the cab, as in Red Alert 2
        "rocket": [], "rocket_above": {"defaultMaterial": 1.6},  # the rocket shares a part with the wheels
        "team": {"box": (0.0, 1.0, 0.68, 1.0, 0.0, 0.55)},  # the truck cab
    },
    # Light Tank: "M551 Sheridan Light Tank" by Muhamad Mirza Arrafi, CC-BY-4.0 (antennas left out)
    "1tnk": {
        "src": "inbox2/1tnk__m551_sheridan_light_tank/scene.gltf", "kind": "tank", "frame": 192,
        "yaw": 180, "length": 7.5,
        "drop": ["antenna01_Gear_566_0", "antenna011_Gear_566_0"],
        "tank": {"turret": ["g_cannonbase_m551_m81_Cannon_587_0", "g_cannonbase_m551_m81_Glass_588_0",
                            "g_cannon_m81_Cannon_587_0", "g_turret_m551_Turret_641_0", "g_turret_m551_Glass_588_0",
                            "g_turret_m551_Gear_642_0"],
                 "ring": (1.4, 1.6), "pivot": (-0.07, 0.01), "muzzle": "g_cannon_m81_Cannon_587_0"},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.8, 1.0)},  # turret roof
    },
    # Medium Tank: "M1A1 Abrams Main Battle Tank" by Muhamad Mirza Arrafi, CC-BY-4.0. The gun is merged into
    # the hull parts: everything above the deck inside the turret ring (plus the gun) is cut off as the turret.
    "2tnk": {
        "src": "inbox2/2tnk__m1a1_abrams_main_battle_tank/scene.gltf", "kind": "tank", "frame": 192,
        "yaw": 180, "length": 8.6,
        "tank": {"turret": ["Object_14", "Object_15", "Object_5", "Object_13", "Object_2", "Object_16", "Object_3",
                            "Object_17", "Object_6"],
                 "cut": 1.15, "ring": (1.8, 2.6), "pivot": (0.03, -0.68)},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.73, 1.0)},  # turret roof
    },
    # Tesla Tank (TTNK): "T4-B Heavy Tank" by henskelion, CC-BY-4.0 (the earlier T-62 + RA2 coil build is in
    # old-ai/ttnk). Turret: every part above the hull deck, side cannons included; the Rebel emblem on the front is
    # painted out (scrub_red); Tesla bolts fire from both side cannons (muzzle = one barrel, mirrored in rules).
    "ttnk": {
        "src": "inbox2/ttnk__t4-b_heavy_tank/scene.gltf", "kind": "tank", "frame": 192,
        "yaw": 180, "length": 8.4, "scrub_red": True,
        "tank": {"turret": ['pCylinder41_T4_B_blinn_0', 'pCylinder40_T4_B_blinn_0', 'pCylinder39_T4_B_blinn_0', 'pCylinder10_T4_B_blinn_0', 'pCube3_T4_B_blinn_0', 'pCube25_T4_B_blinn_0', 'pCylinder57_T4_B_blinn_0', 'pCube28_T4_B_blinn_0', 'pCube35_T4_B_blinn_0', 'pCylinder57_T4_B_blinn_0.001', 'pCube7_T4_B_blinn_0', 'pCube27_T4_B_blinn_0', 'pCylinder57_T4_B_blinn_0.002', 'pCylinder60_T4_B_blinn_0', 'pCylinder62_T4_B_blinn_0', 'pCylinder63_T4_B_blinn_0', 'pCube37_T4_B_blinn_0', 'pCube46_T4_B_blinn_0', 'pCube47_T4_B_blinn_0', 'pCube43_T4_B_blinn_0', 'pCube44_T4_B_blinn_0', 'pCube45_T4_B_blinn_0', 'pCylinder11_T4_B_blinn_0', 'pCube4_T4_B_blinn_0', 'pCube6_T4_B_blinn_0', 'pCylinder19_T4_B_blinn_0', 'polySurface2_T4_B_blinn_0', 'pCylinder45_T4_B_blinn_0', 'pCylinder51_T4_B_blinn_0', 'pCylinder61_T4_B_blinn_0', 'pCube26_T4_B_blinn_0', 'pCube36_T4_B_blinn_0', 'pCylinder11_T4_B_blinn_0.001', 'pCube4_T4_B_blinn_0.001', 'pCube6_T4_B_blinn_0.001', 'pCylinder19_T4_B_blinn_0.001', 'polySurface2_T4_B_blinn_0.001', 'pCylinder45_T4_B_blinn_0.001', 'pCylinder51_T4_B_blinn_0.001', 'pCylinder61_T4_B_blinn_0.001'],
                 "ring": (8.5, 9.5), "pivot": (0.0, -6.2), "muzzle": "pCylinder61_T4_B_blinn_0"},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.85, 1.0)},  # turret roof
    },
    # MAD Tank: "KV-2 heavy tank 1940" by comrade1280, CC-BY-4.0 (display floor left out). No turning turret in
    # game (the shock-wave device sits in the box turret), so it renders as one body.
    "qtnk": {
        "src": "inbox2/qtnk__kv_2_heavy_tank_1940/scene.gltf", "kind": "vehicle", "frame": 192,
        "yaw": 180, "length": 8.6, "drop_materials": ["floor"],
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.93, 1.0)},  # turret roof
    },
    # Construction Vehicle, Union (mcv): "HEMTT (USA)" by 42manako, CC-BY-NC-4.0 (non-commercial; 2026-11-03,
    # replaced the Oshkosh M1070 HET, old sprite in old-sketchfab/mcv-oshkosh.png). Team colour: the cab roof.
    "mcv": {
        "name": "Construction Vehicle (Union)", "src": "inbox3/mcv.union__hemtt_usa/scene.gltf",
        "kind": "vehicle", "frame": 224, "yaw": 90, "length": 10.7,
        "team": {"box": (0.0, 1.0, 0.72, 1.0, 0.8, 1.0)},
    },
    # Construction Vehicle, Vanguard (image mcv.vanguard via RenderSprites FactionImages): "M978 HEMTT" by 42manako,
    # CC-BY-4.0 (2026-11-03, replaced the Ural KS3574 crane, old sprite in old-sketchfab/mcv-vanguard-ural.png).
    # Team colour: the cab roof.
    "mcv.vanguard": {
        "name": "Construction Vehicle (Vanguard)", "src": "inbox3/mcv.vanguard__m978_hemtt/scene.gltf",
        "kind": "vehicle", "out": "mcv-vanguard", "frame": 224, "yaw": 180, "length": 10.7,
        "team": {"box": (0.0, 1.0, 0.72, 1.0, 0.8, 1.0)},
    },
    # Mobile Gap Generator: "1S12 Long Track Acquisition Radar" by gogiart, CC-BY-4.0. The parts are merged by
    # material: everything above the cab roof (the big antenna on its turntable) is cut off as the spinner, rendered
    # as a full 32-frame turn (spin) for the WithIdleOverlay "spinner" sequence.
    "mgg": {
        "src": "inbox2/mgg__1s12_long_track/scene.gltf", "kind": "tank", "frame": 224,
        "yaw": 90, "length": 7.6, "spin": 32,
        "tank": {"turret": [], "cut": 6.0, "ring": (9.8, 9.8), "pivot": (0.0, 0.0), "muzzle_top": True},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.41, 0.47)},  # cab and equipment roof
    },
    # Previews only (Fab downloads, licence to confirm): IS-3M (needs its hull colour texture), mecha
    "preview.is3m": {"src": "inbox2/is3m_kyev_set1_gltf/scene.gltf", "kind": "vehicle", "frame": 192, "length": 8.6},
    "preview.mecha": {"src": "inbox2/mecha_gltf/scene.gltf", "kind": "vehicle", "frame": 192, "length": 4.0},
    # Vanguard Medium Tank (MTNK): "Soviet medium tank T-34-85" (Fab download), parts named Turret.* / Gun.*
    "mtnk": {
        "name": "Medium Tank (Vanguard)", "src": "inbox2/soviet_medium_tank_t_34_85_s_53_gltf/scene.gltf",
        "kind": "tank", "frame": 192, "yaw": 180, "length": 7.8,
        "tank": {"turret": ["Gun.004_low_Antracite_0", "Gun.044_low_Antracite_0", "Turret.001_low_Antracite_0", "Turret.007_low_Antracite_0", "Turret.008_low_Antracite_0", "Turret.011_low_Antracite_0", "Turret.016_low_Antracite_0", "Turret.039_low_Antracite_0", "Turret.040_low_Antracite_0", "Turret.041_low_Antracite_0", "Turret.048_low_Antracite_0", "Turret.052_low_Antracite_0", "Turret.056_low_Antracite_0", "Turret.057_low_Antracite_0", "Turret.060_low_Antracite_0", "Turret.132_low_Antracite_0", "Turret.136_low_Antracite_0", "Turret.137_low_Antracite_0"],
                 "ring": (0.65, 0.9), "pivot": (0.025, -0.185), "muzzle": "Gun.044_low_Antracite_0"},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.8, 1.0)},  # turret roof
    },
    # Ranger (JEEP): "Tiger Russian Military Vehicle" by Gerhald, CC-BY-4.0. No roof gun on the model: the Ranger
    # keeps its turret in rules (a hatch gunner) without a turret sprite.
    "jeep": {
        "src": "inbox3/tiger_russian_military_vehicle/scene.gltf", "kind": "vehicle", "frame": 160,
        "yaw": 180, "length": 6.25,
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.62, 0.75)},  # roof
    },
    # Minelayer (MNLY): "M113" by arc4de, CC-BY-4.0
    "mnly": {
        "src": "inbox2/mnly__m113/scene.gltf", "kind": "vehicle", "frame": 192, "yaw": 0, "length": 8.1,
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.9, 1.0)},  # roof
    },
    # Supply Truck (TRUK): "Ural 4320" by davidbroutian, CC-BY-4.0
    "truk": {
        "src": "inbox2/truk__ural_4320/scene.gltf", "kind": "vehicle", "frame": 192, "yaw": 180, "length": 8.1,
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.85, 1.0)},  # cargo cover and cab roof
    },
    # Flak Truck (FTRK): "96K6 Pantsir-S1" by ALI1388, CC-BY-4.0. The combat module (guns + missiles) on the
    # rear is cut off above the truck bed as the turret.
    "ftrk": {
        "src": "inbox2/ftrk.pantsir__96k6_pantsir_s1/scene.gltf", "kind": "tank", "frame": 224,
        "yaw": 180, "length": 8.6,
        "tank": {"turret": [], "cut": 2600, "ring": (1500, 2400), "pivot": (-1000, -4800)},
        "team": {"box": (0.0, 1.0, 0.0, 0.55, 0.62, 0.75)},  # top of the combat module
    },
    # Artillery (ARTY): "M109A6 Paladin Self-Propelled Howitzer" by Muhamad Mirza Arrafi, CC-BY-4.0. The classic
    # artillery has no turning turret: one body, gun forward (antennas left out)
    "arty": {
        "src": "inbox2/arty__m109a6_paladin_self_propelled_howitzer/scene.gltf", "kind": "vehicle", "frame": 224,
        "yaw": 180, "length": 8.6,
        "drop": ["antenna_short__M109A6_PaladinGear_790_0", "antenna_short1__M109A6_PaladinGear_790_0"],
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.72, 1.0)},  # turret roof
    },
    # Demolition Truck (DTRK): "Gaz 66" by tiunov.se, CC-BY-4.0
    "dtrk": {
        "src": "inbox2/dtrk__gaz_66/scene.gltf", "kind": "vehicle", "frame": 192, "yaw": 180, "length": 8.1,
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.85, 1.0)},  # cargo bed cover and cab roof
    },
    # Chrono Tank (CTNK): '"Cobra" Futuristic tank concept' by iptestcs, CC-BY-4.0 (display base left out)
    "ctnk": {
        "src": "inbox2/ctnk__cobra__futuristic_tank_concept/scene.gltf", "kind": "vehicle", "frame": 192,
        "yaw": 180, "length": 8.25,
        "drop": ["Box176_20 - Default_0", "Box176_23 - Default_0", "Box176_24 - Default_0"],
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.8, 1.0)},
    },
    # Phase Transport (STNK): "Stealth tank" by artmanbox, CC-BY-4.0
    "stnk": {
        "src": "inbox2/stnk__stealth_tank/scene.gltf", "kind": "vehicle", "frame": 192, "yaw": 0, "length": 8.1,
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.8, 1.0)},
    },
    # Prism Tank (PTNK): "Cyber Tank | Futuristic Cyberpunk" by kraytay, CC-BY-4.0
    "ptnk": {
        "src": "inbox2/ptnk.cyber__cyber_tank__futuristic_cyberpunk/scene.gltf", "kind": "tank", "frame": 224,
        "yaw": 180, "length": 8.8,
        # The turret block above the deck (and its gun) turns; pivot measured on the model (after the yaw)
        "tank": {"turret": [], "cut": 1.15, "ring": (1.3, 1.2), "pivot": (0.08, -1.4)},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.85, 1.0)},
    },
    # Radar Jammer (MRJ): "Renault TRM Radar Truck" by Muhamad Mirza Arrafi, CC-BY-4.0
    "mrj": {
        "src": "inbox2/mrj__renault_trm_radar_truck/scene.gltf", "kind": "tank", "frame": 224, "yaw": 180,
        "length": 8.1, "spin": 32,
        # The radar dish on its mast spins (32-frame turn for the "spinner" overlay); pivot = the mast
        "tank": {"turret": [], "cut": 450, "ring": (380, 380), "pivot": (9, -138), "muzzle_top": True},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.4, 0.46)},
    },
    # XR-85 Tank Droid (XR85, France only): "XR-85 Tank Droid" by henskelion, CC-BY-4.0. The top turret with the
    # long main gun turns; the side, front and rear guns stay on the hull.
    "xr85": {
        "name": "XR-85 Tank Droid", "src": "inbox2/xr85__xr-85_tank_droid/scene.gltf", "kind": "tank", "frame": 224,
        "yaw": 180, "length": 9.0,
        "tank": {"turret": ["Turret_Turret_MAT_0", "Gun_Turret_MAT_0", "Barrel_Turret_MAT_0"],
                 "ring": (1.5, 1.7), "pivot": (-0.53, -0.9), "muzzle": "Barrel_Turret_MAT_0"},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.88, 1.0)},  # turret roof
    },
    # Spider Tank (SPDR, Vanguard): "Spider Tank" by Adoni, CC-BY-4.0. Six-legged; the turret with the long gun and
    # the twin anti-aircraft guns turns. Legs stay in their standing pose.
    "spdr": {
        "name": "Spider Tank", "src": "inbox2/spider_tank/scene.gltf", "kind": "tank", "frame": 256,
        "yaw": 180, "length": 10.0,
        "tank": {"turret": ['AA_gun_center_AA_Gun_mat_0', 'AA_gun_antennae_AA_Gun_mat_0', 'AA_gun_swivel_AA_Gun_mat_0', 'AA_gun_swivel_mount_main_AA_Gun_ma', 'AA_gun_swivel_mount_AA_Gun_mat_0', 'AA_gun_pipes_left_AA_Gun_mat_0', 'AA_gun_left_AA_Gun_mat_0', 'AA_gun_left_ammo_box_AA_Gun_mat_0', 'AA_gun_left_barrel_ridges_AA_Gun_m', 'AA_gun_buffer_left_AA_Gun_mat_0', 'AA_gun_chamber_left_AA_Gun_mat_0', 'AA_gun_indicator_left_AA_Gun_mat_0', 'AA_gun_pipes_right_AA_Gun_mat_0', 'AA_gun_right_AA_Gun_mat_0', 'AA_gun_right_ammo_box_AA_Gun_mat_0', 'AA_gun_right_barrel_ridges_AA_Gun_', 'AA_gun_buffer_right_AA_Gun_mat_0', 'AA_gun_chamber_right_AA_Gun_mat_0', 'AA_gun_indicator_right_AA_Gun_mat_', 'Turret_cages_Turret_mat_0', 'Turret_handles_Turret_mat_0', 'Turret_taillights_Turret_mat_0', 'Turret_viewfinder_left_mount_Turre', 'Turret_viewfinder_left_Turret_mat_', 'Turret_viewfinder_right_mount_Turr', 'Turret_viewfinder_right_Turret_mat', 'Turret_viewfinder_right_latch_Turr', 'Turret_viewfinder_right_tiedown_Tu', 'Turret_viewfinder_right_handle_Tur', 'Turret_viewfinder_left_latch_Turre', 'Turret_viewfinder_left_handle_Turr', 'Turret_viewfinder_left_tiedown_Tur', 'Turret_Turret_mat_0', 'Turret_accessories_Turret_mat_0', 'Turret_radiator_Turret_mat_0', 'Turret_barrel_Barrel_mat_0'],
                 "ring": (2.0, 3.3), "pivot": (0.0, -0.4), "muzzle": "Turret_barrel_Barrel_mat_0"},
        "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.82, 1.0)},  # turret roof
    },
    # APC: "ARX Medic" by snafuj, CC-BY-4.0
    "apc": {
        "src": "inbox/arx_medic/scene.gltf", "kind": "vehicle", "frame": 192,
        "yaw": 180, "length": 7.75,
        "team": {"box": (0.0, 1.0, 0.0, 0.45, 0.55, 1.0)},  # roof of the rear compartment
    },

    # Spy Car 1 (rules/spycar.yaml SCAR): "2009 Aston Martin DBS" by Galaxy Car Showroom, CC-BY-4.0 (game-engine
    # style part names - replace before any commercial release). Badges left out; team colour is a racing stripe
    # down the middle of the paint (bonnet, roof, boot).
    "scar": {
        "name": "Spy Car 1", "src": "inbox/2009_aston_martin_dbs/scene.gltf", "kind": "vehicle",
        "frame": 160, "yaw": 0, "length": 6.5,
        "drop": ["Object_4", "Object_82", "Object_84", "Object_86"],
        "team": {"box": (0.42, 0.58, 0.0, 1.0, 0.5, 1.0), "box_materials": ["Paint"]},
    },
    # Spy Car 2 (rules/spycar.yaml SCR2): "1964 Aston Martin DB5" by BrodyFelch, CC-BY-4.0. The bonnet badge is
    # painted out of the extracted texture (glb/sketchfab/inbox/1964_aston_martin_db5/textures/Base_baseColor.png);
    # the team colour is a racing stripe down the middle of the body (bonnet, roof, boot).
    "scr2": {
        "name": "Spy Car 2", "src": "inbox/1964_aston_martin_db5/scene.gltf", "kind": "vehicle",
        "frame": 160, "yaw": 180, "length": 6.3,
        "team": {"box": (0.42, 0.58, 0.0, 1.0, 0.5, 1.0), "box_materials": ["Base"]},
    },

    # Flying Gap Generator (rules/gapjet.yaml JET.GAPGEN): "Grumman E-2D Advanced Hawkeye" by Muhamad Mirza
    # Arrafi, CC-BY-4.0. Team colour: the top of the rotodome.
    "jet.gapgen": {
        "name": "Shroud Hawk (E-2D)", "src": "inbox2/jet.gap__e2d_hawkeye/scene.gltf", "kind": "air",
        "out": "ae-2-shroud-hawk", "frame": 192, "yaw": 180, "length": 8.2,
        "team": {"box": (0.38, 0.62, 0.24, 0.52, 0.88, 1.0)},
    },

    # --- Jets (sprite names from artsrc/jets/make_jets.py: the HD sheet is swapped in place) ---------------
    # "A-10C Thunderbolt II" by VTX, CC-BY-NC-SA-4.0
    "jet.a10": {"src": "inbox/a-10c_thunderbolt_ii/scene.gltf", "kind": "air", "out": "aa-10-thunderhog",
                "frame": 160, "yaw": 180, "length": 7.1, "team": {"box": JET_BOX}},
    # "F-14A Tomcat Early" by VTX, CC-BY-NC-SA-4.0
    "jet.f14": {"src": "inbox/f-14a_tomcat_early/scene.gltf", "kind": "air", "out": "af-14-bobcat",
                "frame": 160, "yaw": 180, "length": 7.8, "team": {"box": JET_BOX}},
    # "Sukhoi Su-35 - Fighter Jet - Free" by bohmerang, CC-BY-NC-SA-4.0
    "jet.su35": {"src": "inbox/sukhoi_su-35_-_fighter_jet_-_free/scene.gltf", "kind": "air",
                 "out": "sk-35-flankard-e", "frame": 160, "yaw": 90, "length": 8.5,
                 "team": {"box": (0.0, 1.0, 0.0, 0.3, 0.55, 1.0)}},  # tail fins
    # "KF-21A Boramae Fighter Jet" by Muhamad Mirza Arrafi, CC-BY-4.0
    "jet.f22": {"src": "inbox/kf-21a_boramae_fighter_jet/scene.gltf", "kind": "air", "out": "af-22-raptorex",
                "frame": 160, "yaw": 180, "length": 7.7, "team": {"box": JET_BOX}},
    # "Northrop Grumman X-47B" by yakudami, CC-BY-4.0. White navy finish made gunmetal like the concept, team
    # colour on the spine and wingtips; the file's second copy (wings folded) is dropped.
    "jet.x47": {"src": "inbox2/jet.x47__northrop_grumman_x_47b/scene.gltf", "kind": "air", "out": "ax-47-stingray",
                "frame": 160, "yaw": 180, "length": 5.8, "drop": ["Cube.001_Material.001_0"], "darken": 0.06,
                "team": {"boxes": [(0.485, 0.515, 0.1, 0.95, 0.4, 1.0),  # spine
                                   (0.0, 0.055, 0.0, 0.6, 0.0, 1.0), (0.945, 1.0, 0.0, 0.6, 0.0, 1.0)]}},  # tips
    # "FPV Drone" by PinaPipe, CC-BY-4.0
    "jet.swarm": {"src": "inbox/fpv_drone/scene.gltf", "kind": "air", "out": "swarm-drone",
                  "frame": 160, "yaw": 45, "length": 3.5, "team": {"materials": ["Frame"]}},
    # Zeppelin: "Red Alert Kirov Airship" by boxgizmo, Sketchfab Standard licence
    "jet.zeppelin": {"src": "inbox/red_alert_kirov_airship/scene.gltf", "kind": "air", "out": "zeppelin",
                     "frame": 288, "yaw": 180, "length": 20,
                     "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.68, 0.75)}},  # a band round the envelope
    # MiG attack plane (classic MIG): "MiG-35 - Fighter Jet - Free" by bohmerang, CC-BY-NC-SA-4.0
    "mig": {"src": "inbox/mig-35_-_fighter_jet_-_free/scene.gltf", "kind": "air", "frame": 160, "yaw": 90,
            "length": 7.2, "team": {"box": JET_BOX}},
    # Badger paradrop plane / bomber (classic BADR): "c-17a globemaster" by Kevin Love (Tyler_Kevin), CC-BY-4.0
    "badr": {"src": "inbox/c-17a_globemaster/scene.gltf", "kind": "air", "frame": 224, "yaw": 0,
             "length": 13.6, "team": {"box": JET_BOX}},

    # --- Helicopters: body sheet (32 facings) + rotor sheet (4 blurred + 8 slow frames) -------------------
    # Chinook: "Boeing CH-47 Chinook Military Transport Aircraft" by Muhamad Mirza Arrafi, CC-BY-4.0
    "tran": {"src": "inbox/boeing_ch-47_chinook_military_transport_aircraft/scene.gltf", "kind": "heli",
             "frame": 192, "yaw": 180, "length": 8.6,
             "rotors": [["Object_6", "Object_9"], ["Object_7", "Object_8"]], "blades": 3, "team": {"box": HELI_BOX}},
    # Longbow: "Aérospatiale SA342 Gazelle" by VTX, CC-BY-NC-SA-4.0
    "heli": {"src": "inbox/aerospatiale_sa342_gazelle/scene.gltf", "kind": "heli", "frame": 192, "yaw": 180,
             "length": 7.0, "rotors": [["Object_136"]], "blades": 3, "team": {"box": HELI_BOX}},
    # Hind: "CAIC Z-10ME" by VTX, CC-BY-NC-SA-4.0
    "hind": {"src": "inbox/caic_z-10me/scene.gltf", "kind": "heli", "frame": 192, "yaw": 180, "length": 7.6,
             "rotors": [["Object_8"]], "blades": 5, "team": {"box": HELI_BOX}},
    # Black Hawk: "Sikorsky CH-53E Sea Stallion" by Muhamad Mirza Arrafi, CC-BY-4.0
    "mh60": {"src": "inbox/sikorsky_ch-53e_sea_stallion/scene.gltf", "kind": "heli", "frame": 192, "yaw": 0,
             "length": 8.4, "rotors": [["Object_11"]], "blades": 7, "team": {"box": HELI_BOX}},

    # --- Phase 1 (assets/inbox/new_3d_models_2, credits in that folder's credits.md) -------------------
    "jet.f104": {"name": "Starflash (F-104)", "src": "inbox2/jet.f104__f_104_starfighter/scene.gltf", "kind": "air", "out": "af-104-starflash", "frame": 160, "yaw": 180, "length": 7.2, "team": {"box": JET_BOX}},
    "jet.f4": {"name": "Spectre II (F-4)", "src": "inbox2/jet.f4__mcdonnell_douglas_f_4_phantom_ii/scene.gltf", "kind": "air", "out": "af-4-spectre-ii", "frame": 160, "yaw": 90, "length": 7.8, "team": {"box": JET_BOX}},
    "jet.f16": {"name": "Fighting Kestrel (F-16)", "src": "inbox2/jet.f16__general_dynamics_f_16d_block_60/scene.gltf", "kind": "air", "out": "af-16-fighting-kestrel", "frame": 192, "yaw": 0, "length": 7.0, "team": {"box": JET_BOX}},
    "jet.f117": {"name": "Nightjar (F-117)", "src": "inbox2/jet.f117__lockheed_f_117a_nighthawk_stealth_bomber/scene.gltf", "kind": "air", "out": "af-117-nightjar", "frame": 160, "yaw": 180, "length": 8.0, "team": {"box": JET_BOX}},
    "jet.sr71": {"name": "Blackwing (SR-71)", "src": "inbox2/jet.sr71__lockheed_sr_71__blackbird/scene.gltf", "kind": "air", "out": "sr-7-blackwing", "frame": 160, "yaw": 90, "length": 10.7, "team": {"box": JET_BOX}},
    "jet.b52": {"name": "Stratoforce (B-52)", "src": "inbox2/jet.b52__boeing_b_52d_stratofortress___duxford/scene.gltf", "kind": "air", "out": "ab-52-stratoforce", "frame": 224, "yaw": 180, "length": 13.6, "team": {"box": JET_BOX}},
    "jet.b2": {"name": "Wraith (B-2)", "src": "inbox2/jet.b2__b_2_spirit/scene.gltf", "kind": "air", "out": "ab-2-wraith", "frame": 256, "yaw": 0, "length": 6.5, "team": {"box": FLAT_BOX}},
    "jet.yf23": {"name": "Black Recluse (YF-23)", "src": "inbox2/jet.yf23__rigged_northrop_yf_23/scene.gltf", "kind": "air", "out": "ayf-23-black-recluse", "frame": 160, "yaw": 90, "length": 8.1, "team": {"box": JET_BOX},
                 "drop": ["Icosphere", "Object_13", "Object_33", "Object_37", "Object_43"]},  # helper sphere, flat inner panel, landing gear,
    "jet.harrier": {"name": "Harrow (Harrier)", "src": "inbox2/jet.harrier__av_8b_harrier_ii/scene.gltf", "kind": "air", "out": "harrow", "frame": 160, "yaw": 180, "length": 6.5, "team": {"box": JET_BOX}},
    "jet.m2000": {"name": "Mirago 2000 (Mirage 2000)", "src": "inbox2/jet.m2000__mirage_2000_5f/scene.gltf", "kind": "air", "out": "mirago-2000", "frame": 160, "yaw": 180, "length": 6.6, "team": {"box": JET_BOX}},
    "jet.rafale": {"name": "Rafal F4 (Rafale)", "src": "inbox2/jet.rafale__dassault_rafale/scene.gltf", "kind": "air", "out": "rafal-f4", "frame": 160, "yaw": -90, "length": 6.8, "team": {"box": JET_BOX}},
    "jet.typhoon": {"name": "Typhon (Typhoon)", "src": "inbox2/jet.typhoon__eurofighter_typhoon_da2___zh588/scene.gltf", "kind": "air", "out": "typhon", "frame": 160, "yaw": 180, "length": 7.0, "team": {"box": JET_BOX}},
    "jet.vulcan": {"name": "Volcan (Vulcan)", "src": "inbox2/jet.vulcan__avro_vulcan_b_2___xh558/scene.gltf", "kind": "air", "out": "volcan", "frame": 160, "yaw": 180, "length": 10.1, "team": {"box": JET_BOX}},
    "jet.seavixen": {"name": "Sea Vixa (Sea Vixen)", "src": "inbox2/jet.seavixen__de_havilland_dh_110_sea_vixen_faw_2/scene.gltf", "kind": "air", "out": "sea-vixa", "frame": 160, "yaw": 180, "length": 7.2, "team": {"box": JET_BOX}},
    "jet.mig3": {"name": "Mik-3 Strela (MiG-3)", "src": "inbox2/jet.mig3__mig3/scene.gltf", "kind": "air", "out": "mik-3-strela", "frame": 160, "yaw": -121, "length": 4.7, "team": {"box": JET_BOX}},
    "jet.mig21": {"name": "Mik-21 Fishbone (MiG-21)", "src": "inbox2/jet.mig21__mig_21_fishbed___cold_war_era_fighter___free/scene.gltf", "kind": "air", "out": "mik-21-fishbone", "frame": 160, "yaw": -90, "length": 6.6, "team": {"box": JET_BOX}, "keep_near": ((46.0, 31.4), 10.0)},
    "jet.mig23": {"name": "Mik-23 Flintlock (MiG-23)", "src": "inbox2/jet.mig23__mig_23_mld/scene.gltf", "kind": "air", "out": "mik-23-flintlock", "frame": 160, "yaw": 180, "length": 7.2, "team": {"box": JET_BOX}},
    "jet.mig25": {"name": "Mik-25 Foxbane (MiG-25)", "src": "inbox2/jet.mig25__mig25/scene.gltf", "kind": "air", "out": "mik-25-foxbane", "frame": 160, "yaw": -135, "length": 7.9, "team": {"box": JET_BOX}, "snap": 'length'},
    "jet.su25": {"name": "Sk-25 Rook (Su-25)", "src": "inbox2/jet.su25__pbr__sukhoi_su_25/scene.gltf", "kind": "air", "out": "sk-25-rook", "frame": 160, "yaw": 0, "length": 6.9, "team": {"box": JET_BOX}},
    "jet.su27": {"name": "Sk-27 Flankard (Su-27)", "src": "inbox2/jet.su27__sukhoi_su_27p_flanker_b/scene.gltf", "kind": "air", "out": "sk-27-flankard", "frame": 160, "yaw": 0, "length": 8.5, "team": {"box": JET_BOX}},
    "jet.su47": {"name": "Sk-47 Berkov (Su-47)", "src": "inbox2/jet.su47__su_47_berkut/scene.gltf", "kind": "air", "out": "sk-47-berkov", "frame": 160, "yaw": 180, "length": 8.6, "team": {"box": JET_BOX}},
    "jet.tu160": {"name": "Tv-160 Swanwing (Tu-160)", "src": "inbox2/jet.tu160__tupolev_tu_160_blackjack_strategic_bomber/scene.gltf", "kind": "air", "out": "tv-160-swanwing", "frame": 288, "yaw": 180, "length": 14, "team": {"box": JET_BOX}},
    "jet.l39": {"name": "L-39U Albatross (L-39)", "src": "inbox2/jet.l39__l_39_albatros/scene.gltf", "kind": "air", "out": "l-39u-albatross", "frame": 160, "yaw": 180, "length": 5.9, "team": {"box": JET_BOX}},
    # An-225 slot: "C-17A Globemaster III" by VTX, CC-BY-NC-SA-4.0 (the textureless An-225 model looked flat white)
    "jet.an225": {"name": "An-225 Dreamer (C-17A Globemaster III)", "src": "inbox/c-17a_globemaster_iii/scene.gltf", "kind": "air", "out": "an-225-dreamer", "frame": 288, "yaw": 0, "length": 18.9, "team": {"box": JET_BOX}},
    "jet.j20": {"name": "JX-20 Jade Dragon (J-20)", "src": "inbox2/jet.j20__chinese_chengdu_j_20/scene.gltf", "kind": "air", "out": "jx-20-jade-dragon", "frame": 160, "yaw": 0, "length": 8.1, "team": {"box": JET_BOX}},
    "jet.saeqeh": {"name": "Saeqa (F-5E / Saeqeh)", "src": "inbox2/jet.saeqeh__northrop_f_5e_tiger_ii/scene.gltf", "kind": "air", "out": "saeqa", "frame": 160, "yaw": 180, "length": 6.7, "team": {"box": JET_BOX}},
    "jet.grom": {"name": "Grom-K drone", "src": "inbox2/jet.grom__stealth_drone_concept/scene.gltf", "kind": "air", "out": "grom-k", "frame": 160, "yaw": 90, "length": 6.4, "team": {"box": FLAT_BOX}},
    "jet.v22": {"name": "Kestrel tiltrotor (V-22)", "src": "inbox2/jet.v22__bell_boeing_v_22_osprey_military_helicopter/scene.gltf", "kind": "air", "out": "kestrel-tiltrotor", "frame": 160, "yaw": 0, "length": 7.4, "team": {"box": JET_BOX}},
    "yak": {"name": "Yak Attack Plane (Yak-9)", "src": "inbox2/yak__yak9/scene.gltf", "kind": "air", "frame": 160, "yaw": -139, "length": 4.8, "team": {"box": JET_BOX}},
    "u2": {"name": "Spy Plane (U-2)", "src": "inbox2/u2__lockheed_u_2c_spy_plane___duxford/scene.gltf", "kind": "air", "frame": 192, "yaw": 180, "length": 7.0, "team": {"box": JET_BOX}},

    # --- Ships (kind ship: hull 0-31, cut at the waterline; the guns are part of the hull for now) ---
    # Cruiser: none yet. The CLAA "Uranus" (inbox3, lxyun_2) and the inbox2 "BB-61 Iowa (New Year Mode)" ship-girl are
    # out: Uranus's materials (am433_...) match a warship game's asset names, so it is probably ripped. Its entry is
    # kept as "ca.uranus" (not in game) for comparison.
    "ca.uranus": {"name": "Cruiser (CLAA Uranus)", "src": "inbox3/british_navy_claa_tier__uranus/scene.gltf", "kind": "ship", "out": "ca-uranus",
           "frame": 320, "yaw": 180, "length": 18.0, "waterline": -8.4,
           "team": {"box": (0.25, 0.75, 0.3, 0.7, 0.55, 1.0)}},  # bridge and funnels,
    # Cruiser: "USS Cleveland (CL-55)" by bsterling, CC-BY-4.0 (WWII gun cruiser, like the classic artillery cruiser)
    "ca": {"name": "Cruiser (Cleveland)", "src": "cruisers/ca.cleveland/scene.gltf", "kind": "ship",
           "frame": 320, "yaw": 90, "length": 18.0, "waterline": 0.0,
           "team": {"box": (0.25, 0.75, 0.3, 0.7, 0.45, 1.0)}},  # bridge and funnels
    # Spare: "Ticonderoga Missile Cruiser" by waelXcm, CC-BY-4.0 (not in game)
    "ca.ticonderoga": {"name": "Missile Cruiser (Ticonderoga)", "src": "cruisers/ca.ticonderoga/scene.gltf",
                       "kind": "ship", "out": "ca-ticonderoga", "frame": 320, "yaw": 180, "length": 17.0,
                       "waterline": 0.010, "team": {"box": (0.2, 0.8, 0.25, 0.75, 0.45, 1.0)}},
    # Carriers, the US era ladder (docs/DESIGN-IDEAS.md IDEA-08 2a). Team colour on the island (starboard, tall).
    # Tier 1 Fleet Carrier: "Essex-Class Aircraft Carrier" by Spark_Customs, CC-BY-4.0 (post-war refit, waterline model)
    "cv1": {"name": "Fleet Carrier (Essex)", "src": "carriers/cv.essex2/scene.gltf", "kind": "ship",
            "frame": 288, "yaw": 90, "length": 22.0, "waterline": -0.38,
            "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # Tier 2 Battle Carrier: "USS Enterprise CVN-65 Aircraft Carrier" by MirzaArrafiERV_45, CC-BY-4.0
    "cv2": {"name": "Battle Carrier (Enterprise CVN-65)", "src": "carriers/cv.enterprise/scene.gltf", "kind": "ship",
            "frame": 320, "yaw": 90, "length": 25.0, "waterline": 19.0,
            "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.35, 1.0)}},
    # Tier 3 Supercarrier: "USS NIMITZ CVN-68 AIRCRAFT CARRIER" by MirzaArrafiERV_45, CC-BY-4.0
    "cv3": {"name": "Supercarrier (Nimitz)", "src": "carriers/cv.nimitz__uss_nimitz_cvn_68_aircraft_carrier/scene.gltf",
            "kind": "ship", "frame": 352, "yaw": 90, "length": 28.0, "waterline": 20.0,
            "drop_materials": ["0137_Black"],  # SketchUp back faces: a black copy of the deck z-fights with it
            "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # Tier 4 Future Carrier: "Gerald R Ford aircraft Carrier" by waelXcm, CC-BY-4.0
    "cv4": {"name": "Future Carrier (Gerald R. Ford)", "src": "carriers/cv.ford2__gerald_r_ford_aircraft_carrier/scene.gltf",
            "kind": "ship", "frame": 384, "yaw": 180, "length": 29.0, "waterline": 0.52,
            "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # National carriers (rules/carriers.yaml; one per nation with carriers in real life), CC-BY-4.0:
    # "HMS Queen Elizabeth R08 Aircraft Carrier" by MirzaArrafiERV_45
    "cvgb": {"name": "England: HMS Queen Elizabeth", "src": "nations/cv.england.qe/scene.gltf", "kind": "ship", "frame": 352,
             "yaw": 0, "length": 27.0, "waterline": 3.0, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "Charles De Gaulle Aircraft Carrier" by MirzaArrafiERV_45
    "cvfr": {"name": "France: Charles de Gaulle", "src": "nations/cv.france.cdg/scene.gltf", "kind": "ship", "frame": 320,
             "yaw": 180, "length": 26.0, "waterline": 2100.0, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "JS Kaga DDH/CVM - 184" by hrd4588
    "cvjp": {"name": "Japan: JS Kaga (F-35 conversion)", "src": "nations/cv.japan.kaga/scene.gltf", "kind": "ship", "frame": 320,
             "yaw": 180, "length": 24.0, "waterline": 8.0, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "JS Izumo DDH/CVM -183" by hrd4588
    "cvit": {"name": "Italy: light carrier (JS Izumo model, near match for Cavour)", "src": "nations/cv.japan.izumo/scene.gltf", "kind": "ship", "frame": 320,
             "yaw": 180, "length": 23.0, "waterline": 42.0, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "MISTRAL CLASS LHD" by MirzaArrafiERV_45
    "cveg": {"name": "Egypt: Mistral helicopter carrier", "src": "nations/cv.egypt.mistral/scene.gltf", "kind": "ship", "frame": 288,
             "yaw": 180, "length": 21.0, "waterline": 0.25, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.58, 1.0)}},
    # "KIEV CLASS AIRCRAFT CARRIER" by MirzaArrafiERV_45
    "cvsu": {"name": "Soviet: Kiev class", "src": "nations/cv.soviet.kiev/scene.gltf", "kind": "ship", "frame": 320,
             "yaw": 180, "length": 25.0, "waterline": 0.0, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "Admiral Kuznetsov Aircraft Carrier (Prop)" by mansoorsajidp
    "cvru": {"name": "Russia: Admiral Kuznetsov", "src": "nations/cv.russia.kuznetsov/scene.gltf", "kind": "ship", "frame": 352,
             "yaw": 180, "length": 27.0, "waterline": 0.04, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "ins vikrant aircraft carrier" by Chenzoss
    "cvin": {"name": "India: INS Vikrant", "src": "nations/cv.india.vikrant/scene.gltf", "kind": "ship", "frame": 320,
             "yaw": 180, "length": 26.0, "waterline": -0.2, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "Chinese Aircraft Carrier" by businessyuen
    "cvcn": {"name": "China: Fujian-style carrier", "src": "nations/cv.china.generic/scene.gltf", "kind": "ship", "frame": 352,
             "yaw": 180, "length": 28.0, "waterline": 1.2, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "TCG Anadolu" by ammar_ssr
    "cvtr": {"name": "Turkey: TCG Anadolu drone carrier", "src": "nations/cv.turkey.anadolu/scene.gltf", "kind": "ship", "frame": 288,
             "yaw": -90, "length": 22.0, "waterline": 150.0, "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.4, 1.0)}},
    # "USS WASP LHD-1" by MirzaArrafiERV_45 (flat deck, stand-in for the Shahid Bagheri; darkened from navy white so it
    # does not look like Italy's carrier). Tried first: lavawave's container ship (red cell guides read as a raft) and
    # MirzaArrafi's USS Tarawa (renders almost black with loose sticks)
    "cvir": {"name": "Iran: drone carrier (USS Wasp model, stand-in for Shahid Bagheri)", "src": "nations/cv.lhd.wasp/scene.gltf",
             "kind": "ship", "frame": 288, "yaw": 180, "length": 22.0, "waterline": 0.27, "darken": 0.45,
             "team": {"box": (0.55, 1.0, 0.0, 1.0, 0.55, 1.0)}},
    # Destroyer: "1:1 Low poly US NAVY DDG-51 USS Arleigh Burke" by Yi Tsung Lee, CC-BY-4.0
    "dd": {"name": "Destroyer (Arleigh Burke)", "src": "inbox2/dd__1_1_low_poly_us_navy_ddg_51_uss_arleigh_burke/scene.gltf",
           "kind": "ship", "frame": 224, "yaw": 180, "length": 13.5, "waterline": 0.3,
           "team": {"box": (0.25, 0.75, 0.35, 0.75, 0.45, 1.0)}},  # deckhouses,
    # Gunboat: "Type 22 Houbei-class missile boat" by 42manako, CC-BY-4.0
    "pt": {"name": "Gunboat (Houbei)", "src": "inbox2/pt__type_22_houbei_class_missile_boat/scene.gltf", "kind": "ship",
           "frame": 192, "yaw": 0, "length": 9.0, "waterline": 30.0,
           "team": {"box": (0.0, 1.0, 0.2, 0.6, 0.55, 1.0)}},  # cabin roof,
    # Transport: "LCAC Hovercraft croqui" by LM3D, CC-BY-4.0 (rides on its skirt: only the bottom plate goes)
    "lst": {"name": "Transport (LCAC)", "src": "inbox2/lst__lcac_hovercraft_croqui/scene.gltf", "kind": "ship",
            "frame": 224, "yaw": 90, "length": 12.0, "waterline": -1000.0,
            "darken": 0.1, "team": {"boxes": [(0.0, 0.2, 0.15, 0.85, 0.45, 1.0), (0.8, 1.0, 0.15, 0.85, 0.45, 1.0)]}},  # untextured white: naval grey; side cabins,
    # Submarine: "Kilo Class Submarine" by ArtBlender, CC-BY-4.0 (surfaced; IDEA-30 phase 3)
    "ss": {"name": "Submarine (Kilo)", "src": "phase34/kilo-sub/scene.gltf", "kind": "ship", "frame": 160,
           "yaw": 270, "length": 11.0, "waterline": 0.0, "team": {"box": (0.0, 1.0, 0.28, 0.48, 0.55, 1.0)}},  # the sail
    # Missile Submarine: "Ohio Class Submarine SSBN" by waelXcm, CC-BY-4.0 (surfaced; the raised Trident left out)
    "msub": {"name": "Missile Submarine (Ohio)", "src": "inbox2/msub__ohio_class_submarine_ssbn/scene.gltf",
             "kind": "ship", "frame": 256, "yaw": 180, "length": 14.5, "waterline": 0.013,
             "drop": ["trident_missile_others_0"], "team": {"box": (0.0, 1.0, 0.68, 0.86, 0.55, 1.0)}},  # the sail,
}


# --- IDEA-17 national rocket launchers: 6 shared chassis, one sprite per nation in its own paint ----------------
# Models: tools/download_sketchfab.py --launchers (unzipped into glb/sketchfab/launchers/). Team colour on the
# top of the launcher pods. No green paint: the game turns green into the team colour.
LAUNCHER_CHASSIS = {
    # HIMAX: "Ukrainian M142 HIMARS" by 42manako, CC-BY-4.0 (the "_dam" parts are its damaged variants)
    "rl.light": {"src": "launchers/rl.light__ukrainian_m142_himars/scene.gltf", "kind": "vehicle", "frame": 192,
                 "length": 7.6, "drop_contains": ["_dam"], "scrub_white": True,  # Ukrainian crosses
                 "team": {"box": (0.0, 1.0, 0.0, 0.55, 0.8, 1.0)}},
    # Tracked MLRS: "Free M270" by DaHoon, CC-BY-4.0 (a loose rocket and a spare pod beside it are left out)
    "rl.tracked": {"src": "launchers/rl.tracked__free_m270/scene.gltf", "kind": "vehicle", "frame": 192,
                   "length": 7.6, "keep_near": ((0, 1), 11), "fix_normals": True,
                   "team": {"box": (0.0, 1.0, 0.0, 0.6, 0.85, 1.0)}},
    # Heavy 8x8: "BM-27 Uragan" by javanilga, CC-BY-4.0
    "rl.heavy": {"src": "launchers/rl.heavy__bm_27_uragan/scene.gltf", "kind": "vehicle", "frame": 224,
                 "length": 9.4, "team": {"box": (0.0, 1.0, 0.0, 0.5, 0.82, 1.0)}},
    # Medium 6x6 tube rack: "BM-21 Grad" by Basic Hsu, CC-BY-4.0
    "rl.medium": {"src": "launchers/rl.medium__bm_21_grad/scene.gltf", "kind": "vehicle", "frame": 192, "yaw": 180,
                  "length": 8.0, "fix_normals": True, "team": {"box": (0.0, 1.0, 0.0, 0.45, 0.8, 1.0)}},
    # TOZ-1 Sunflare: "TOS-1 BURATINO (LOW POLY)" by LM3D, CC-BY-4.0 (its dirt ground disc is left out)
    "rl.tank": {"src": "launchers/rl.tank__tos_1_buratino__low_poly/scene.gltf", "kind": "vehicle", "frame": 224,
                "length": 8.8, "drop": ["Object_2"], "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.85, 1.0)}},
    # Type-12 Sea Arrow: "3K60 Bal-E" coastal missile launcher by 42manako, CC-BY-4.0
    "rl.canister": {"src": "launchers/rl.canister__3k60_bal_e/scene.gltf", "kind": "vehicle", "frame": 224,
                    "yaw": 180, "length": 10.5, "team": {"box": (0.0, 1.0, 0.0, 0.45, 0.62, 0.75)}},
}

# Launcher actor -> (chassis, national paint in display RGB, or None for the model's own paint)
LAUNCHER_PAINT = {
    "himax": ("rl.light", (0.66, 0.58, 0.42)),       # USA: desert tan
    "hailstorm": ("rl.tracked", (0.38, 0.37, 0.25)),  # England: olive drab
    "lrx": ("rl.tracked", (0.44, 0.43, 0.35)),        # France: grey-olive
    "marz": ("rl.tracked", (0.31, 0.32, 0.31)),       # Germany: NATO dark grey
    "saetta": ("rl.tracked", (0.55, 0.49, 0.36)),     # Italy: khaki
    "kasirga": ("rl.heavy", (0.62, 0.55, 0.40)),      # Turkey: sand
    "fatah": ("rl.heavy", (0.52, 0.46, 0.32)),        # Pakistan: khaki
    "chunmu": ("rl.heavy", (0.34, 0.34, 0.23)),       # South Korea: dark olive
    "vilkra": ("rl.heavy", (0.33, 0.34, 0.29)),       # Ukraine: grey-olive
    "phx16": ("rl.heavy", (0.50, 0.47, 0.38)),        # China: light tan
    "grad": ("rl.medium", (0.39, 0.38, 0.25)),        # Cuba: olive
    "pinak": ("rl.medium", (0.42, 0.40, 0.26)),       # India: olive drab
    "saqr36": ("rl.medium", (0.70, 0.60, 0.42)),      # Egypt: sand
    "fajir5": ("rl.medium", (0.60, 0.50, 0.36)),      # Iran: desert brown
    "toz1": ("rl.tank", None),                        # Russia: the model's own camouflage
    "type12": ("rl.canister", (0.37, 0.36, 0.25)),    # Japan: JGSDF olive
}

for _actor, (_chassis, _paint) in LAUNCHER_PAINT.items():
    _extra = {}
    if _paint:
        _extra = {"paint": _paint, "paint_strength": 1.0}  # brightness: measured by import_sketchfab.py
    MODELS[_actor] = dict(LAUNCHER_CHASSIS[_chassis], name=_actor.upper(), out="rl-" + _actor, **_extra)


# --- IDEA-26 B2 air-defence tiers 2-4: an Allied and a Soviet look per tier (tools/download_sketchfab.py --airdef) --
# Rendered like vehicles (32 facings); the building shows one facing (sequences/air-defence.yaml). Team colour on the
# missile canisters.
MODELS.update({
    # Medium SAM (Allies): "US NASAMS 3 (TEL) (War Thunder) Line of Contact" by KojfDiscord, CC-BY-4.0
    "ad.msam.allies": {"name": "Medium SAM (NASAMS)", "src": "airdef/msam.allies__us_nasams_3__tel___war_thun/scene.gltf",
                       "kind": "vehicle", "frame": 224, "yaw": 180, "length": 9.0, "out": "ad-msam-allies",
                       "team": {"box": (0.0, 1.0, 0.0, 0.5, 0.7, 1.0)}},
    # Medium SAM (Soviets): "BUK Missile System" by azlan, CC-BY-4.0
    "ad.msam.soviet": {"name": "Medium SAM (Buk)", "src": "airdef/msam.soviet__buk_missile_system/scene.gltf",
                       "kind": "vehicle", "frame": 224, "yaw": 180, "length": 9.0, "out": "ad-msam-soviet",
                       "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.82, 1.0)}},
    # Long-range SAM (Allies): "MIM-104 Patriot Surface-To-Air Missile (SAM)" by MirzaArrafiERV_45, CC-BY-4.0
    "ad.lsam.allies": {"name": "Long-range SAM (Patriot)", "src": "airdef/lsam.allies__mim_104_patriot_surface_to_/scene.gltf",
                       "kind": "vehicle", "frame": 256, "yaw": 90, "length": 10.0, "out": "ad-lsam-allies",
                       "team": {"box": (0.0, 1.0, 0.0, 1.0, 0.8, 1.0)}},
    # Long-range SAM (Soviets): "s-400" by sami1230, CC-BY-4.0 (untextured: Soviet olive paint)
    "ad.lsam.soviet": {"name": "Long-range SAM (S-400)", "src": "airdef/lsam.soviet__s_400/scene.gltf",
                       "kind": "vehicle", "frame": 256, "yaw": 180, "length": 11.0, "out": "ad-lsam-soviet",
                       "paint": (0.40, 0.40, 0.28), "paint_strength": 1.0,
                       "team": {"box": (0.0, 1.0, 0.0, 0.5, 0.75, 1.0)}},
    # Missile Shield (Allies): "Terminal High Altitude Area Defense (THAAD)" by Chenzoss, CC-BY-4.0
    "ad.bmd.allies": {"name": "Missile Shield (THAAD)", "src": "airdef/bmd.allies__terminal_high_altitude_area_/scene.gltf",
                      "kind": "vehicle", "frame": 256, "yaw": 180, "length": 11.0, "out": "ad-bmd-allies",
                      "team": {"box": (0.0, 1.0, 0.0, 0.45, 0.7, 1.0)}},
    # Missile Shield (Soviets): "Chinese HQ-9" by 42manako, CC-BY-4.0 (an S-500 stand-in; red star scrubbed)
    "ad.bmd.soviet": {"name": "Missile Shield (HQ-9)", "src": "airdef/bmd.soviet__chinese_hq_9/scene.gltf",
                      "kind": "vehicle", "frame": 256, "yaw": 180, "length": 11.0, "out": "ad-bmd-soviet",
                      "scrub_red": True, "team": {"box": (0.0, 1.0, 0.0, 0.5, 0.75, 1.0)}},
})

