"""
The full jet roster (123 jets, 51 variants) before it was cut to one aircraft per silhouette type.
Kept for reference: copy a line back into JETS in make_jet_prompts.py to bring an aircraft back.
Format as in make_jet_prompts.py.
"""

# (game name, real inspiration, nation, tier, role, extra shape notes)
# tier: 0-5 or "X". Order: shared Soviet, shared Allied, then nation by nation.
JETS = [
    # --- Shared Soviet roster ---
    ("MiK-19 Farmhand", "MiG-19", "soviet", 2, "air", "sharply swept wings, twin engines side by side"),
    ("MiK-21 Fishbone", "MiG-21", "soviet", 2, "air", "tailed delta wing, round nose intake with a shock cone"),
    ("Sk-15 Flagstaff", "Sukhoi Su-15", "soviet", 2, "int", "twin engines with side intakes, cranked delta wing, pointed radar nose"),
    ("Sk-7 Fitch", "Sukhoi Su-7", "soviet", 2, "attack", "sharply swept wings, long fuselage, nose intake"),
    ("Tv-22 Blindar", "Tupolev Tu-22", "soviet", 2, "bomber", "supersonic bomber with two engines on top of the tail"),
    ("MiK-29 Fulcra", "MiG-29", "soviet", 3, "air", "twin tails, twin engines with intakes under the wing roots, blended body"),
    ("Sk-27 Flankard", "Sukhoi Su-27", "soviet", 3, "air", "large twin-engine fighter, engines widely spaced under a flat lifting body, twin tails outboard of the engines, long tail sting between the nozzles, big curved wing-root extensions, bubble canopy, no canards"),
    ("MiK-25 Foxbane", "MiG-25", "soviet", 3, "int", "huge box intakes, twin tails, thin wings, built for Mach 3"),
    ("MiK-31 Foxhunter", "MiG-31", "russia", 3, "int", "two-seat long-range interceptor like a larger MiG-25"),
    ("MiK-23 Flintlock", "MiG-23", "soviet", 3, "multi", "variable-sweep wings shown half swept, side intakes"),
    ("MiK-27 Flailer", "MiG-27", "soviet", 3, "attack", "variable-sweep wings shown half swept, flat 'duck' nose"),
    ("Sk-25 Rook", "Sukhoi Su-25", "soviet", 3, "attack", "armoured close-support jet, straight wings, engines in nacelles beside the fuselage"),
    ("Sk-17 Fitterwing", "Sukhoi Su-17 / Su-22", "soviet", 3, "attack", "variable-sweep outer wings shown half swept, nose intake"),
    ("Sk-24 Fencor", "Sukhoi Su-24", "soviet", 3, "strike", "two crew side by side, variable-sweep wings shown half swept"),
    ("Sk-33 Seaflank", "Sukhoi Su-33", "soviet", 3, "carrier", "single-seat Su-27 airframe with small canards beside the cockpit, folding wings shown spread, a short tail sting and an arrestor hook"),
    ("Yk-38 Forja", "Yakovlev Yak-38", "soviet", 3, "vtol", "small VTOL jet with lift-jet doors behind the cockpit"),
    ("Sk-35 Flankard-E", "Sukhoi Su-35", "soviet", 4, "air", "single-seat Su-27 airframe with no canards, large round thrust-vectoring nozzles and a darker radar nose"),
    ("Sk-30 Flankard-C", "Sukhoi Su-30", "soviet", 4, "multi", "Su-27 airframe with a long two-seat tandem canopy and small canards on the wing-root extensions beside the cockpit"),
    ("MiK-35 Fulcra-F", "MiG-35", "soviet", 4, "multi", "MiG-29 airframe with a bigger humped spine behind the cockpit and a refuelling probe"),
    ("Sk-34 Fullbore", "Sukhoi Su-34", "soviet", 4, "strike", "Su-27 shape with a wide flat 'platypus' nose for two crew side by side"),
    ("Yk-130 Mittenhawk", "Yakovlev Yak-130", "soviet", 4, "light", "small twin-engine jet with leading-edge extensions"),
    ("MiK-29K Seafulcra", "MiG-29K", "soviet", 4, "carrier", "naval MiG-29 with a bigger spine, folding wings shown spread and an arrestor hook"),
    ("Sk-57 Felonix", "Sukhoi Su-57", "russia", 5, "stealth", "large stealth fighter with all-moving twin tails and widely spaced engines"),
    ("MiK-1.44 Flatpack", "Mikoyan MiG 1.44", "soviet", "X", "air", "delta wing with large canards, twin tails, big chin intake"),
    ("Sk-47 Berkov", "Sukhoi Su-47 Berkut", "soviet", "X", "air", "forward-swept wings, canards, twin tails"),
    ("Sk-37 Terminus", "Sukhoi Su-37", "soviet", "X", "air", "single-seat Su-27 airframe with both small canards beside the cockpit and thrust-vectoring nozzles, square-tipped tail fins"),
    ("Yk-141 Freestyler", "Yakovlev Yak-141", "soviet", "X", "vtol", "supersonic VTOL jet with twin tail booms and a swivelling rear nozzle"),

    # --- Shared Allied roster ---
    ("AF-5 Tigerette", "Northrop F-5", "allied", 2, "air", "small twin-engine light fighter with a pointed nose"),
    ("AF-4 Spectre II", "F-4 Phantom II", "allied", 2, "int", "two-seat twin-engine fighter, upturned wingtips, drooping tailplanes"),
    ("AF-104 Starflash", "F-104 Starfighter", "allied", 2, "int", "very thin short wings, T-tail, long needle nose"),
    ("AF-15 Iron Eagle", "F-15 Eagle", "allied", 3, "air", "large twin-engine fighter with a flat wide body, big rectangular box intakes beside the cockpit, twin vertical tails, bubble canopy"),
    ("AF-14 Bobcat", "F-14 Tomcat", "allied", 3, "int", "two-seat carrier interceptor, variable-sweep wings shown spread, twin tails"),
    ("AF-16 Fighting Kestrel", "F-16 Fighting Falcon", "allied", 3, "multi", "single engine with a chin intake, bubble canopy, single tail"),
    ("Mirago 2000", "Dassault Mirage 2000", "allied", 3, "multi", "single-engine tailless delta wing with no canards, semicircular side intakes with shock cones, single tail fin"),
    ("AA-10 Thunderhog", "A-10 Thunderbolt II", "allied", 3, "attack", "straight wings, two engines on top of the rear fuselage, twin tails, big nose cannon"),
    ("AF-117 Nightjar", "F-117 Nighthawk", "allied", 3, "stealth", "faceted flat-panel stealth shape, V-tail, black finish"),
    ("AF/A-18 Stinger", "F/A-18 Hornet", "allied", 3, "carrier", "twin-engine carrier fighter with long wing-root extensions up to the cockpit, twin outward-canted tails, D-shaped intakes under the wing roots"),
    ("Harrow", "Harrier", "allied", 3, "vtol", "shoulder wings drooping down, four swivelling nozzles"),
    ("AF-15X Iron Eagle II", "F-15EX Eagle II", "allied", 4, "air", "F-15 shape with conformal fuel tanks and more pylons"),
    ("Gryphon E", "Saab JAS 39 Gripen E", "allied", 4, "multi", "small slim single-engine delta wing with close-coupled canards behind the cockpit, side intakes, single tail"),
    ("AF/A-18X Super Stinger", "F/A-18E/F Super Hornet", "allied", 4, "carrier", "larger Hornet with rectangular angled intakes, bigger wings, longer root extensions and more pylons"),
    ("AF-22 Raptorex", "F-22 Raptor", "allied", 5, "stealth", "diamond wings, twin canted tails, flat 2D nozzles"),
    ("AF-35 Stormbolt", "F-35A Lightning II", "allied", 5, "stealth", "single-engine stealth fighter with a wide flattened body, trapezoid wings, twin canted tails, one round nozzle and bump intakes on the sides"),
    ("AF-35C Stormbolt", "F-35C Lightning II", "allied", 5, "carrier", "F-35 with larger folding wings and a stealthy finish"),
    ("AB-2 Wraith", "B-2 Spirit", "allied", 5, "bomber", "huge tailless flying wing with a saw-tooth trailing edge, stealth finish"),
    ("AYF-23 Black Recluse", "Northrop YF-23", "allied", "X", "stealth", "diamond wings, ruddervators (V-tail), engine exhausts in troughs"),
    ("AF-16XL Kestrel XL", "F-16XL", "allied", "X", "multi", "F-16 body with a large cranked-arrow delta wing"),
    ("AX-32 Monarch", "Boeing X-32", "allied", "X", "multi", "chunky stealth demonstrator with a large chin intake"),

    # --- USA ---
    ("AF-105 Thunderhead", "F-105 Thunderchief", "usa", 2, "strike", "long fuselage, forward-swept wing-root intakes, internal bomb bay"),
    ("AF-106 Delta Lance", "F-106 Delta Dart", "usa", 2, "int", "tailless delta wing, one tall swept tail, area-ruled 'coke bottle' waist, side intakes behind the cockpit"),
    ("AA-4 Skyhook", "A-4 Skyhawk", "usa", 2, "carrier", "small delta wing, humped back, short legs"),
    ("AA-6 Invader", "A-6 Intruder", "usa", 2, "carrier", "two crew side by side, bulbous nose, mid swept wings"),
    ("AB-52 Stratoforce", "B-52 Stratofortress", "usa", 2, "bomber", "huge swept-wing bomber with eight engines in four pods"),
    ("AF-111 Anteater", "F-111 Aardvark", "usa", 3, "strike", "variable-sweep wings shown half swept, side-by-side crew"),
    ("AF-15E Strike Eagle", "F-15E Strike Eagle", "usa", 3, "strike", "two-seat F-15 with conformal fuel tanks"),
    ("SR-7 Blackwing", "SR-71 Blackbird", "usa", 3, "recon", "long black titanium body with chines, two huge engine nacelles with inlet spikes, black finish"),
    ("AB-1 Lancet", "B-1B Lancer", "usa", 3, "bomber", "large blended bomber with variable-sweep wings shown half swept, four engines"),
    ("AB-21 Reaver", "B-21 Raider", "usa", "X", "bomber", "tailless stealth flying wing, smaller than the B-2"),
    ("AF-47 Dominion", "F-47 (NGAD) concept", "usa", "X", "stealth", "sixth-generation tailless stealth fighter (design not public: invent a believable one)"),
    ("AX-47 Stingray", "Northrop Grumman X-47B", "usa", "X", "ucav", "short wide tailless cranked-kite flying wing with a dorsal intake behind the nose, a carrier arrestor hook, no cockpit"),
    ("AQ-44 Wingmate", "CCA loyal-wingman drone (YFQ-44A)", "usa", "X", "ucav", "small single-engine combat drone shaped like a miniature fighter: pointed nose, dorsal intake behind the nose, shoulder swept wings, V-tail, no cockpit"),

    # --- France ---
    ("Mirago III", "Dassault Mirage IIIC", "france", 2, "int", "tailless delta wing, side intakes with half-cone shock bodies"),
    ("Mirago IV", "Dassault Mirage IV", "france", 2, "bomber", "large two-seat delta-wing nuclear bomber, twin engines"),
    ("Mirago F1", "Dassault Mirage F1", "france", 3, "multi", "high swept wings with a conventional tail"),
    ("Super Étendart", "Dassault Super Étendard", "france", 3, "carrier", "swept wings, an anti-ship missile under one wing"),
    ("Jaguara", "SEPECAT Jaguar", "france", 3, "attack", "shoulder wings, twin engines, long thin nose (joint France / England, also India)"),
    ("Rafal F4", "Dassault Rafale", "france", 4, "multi", "delta wing with close-coupled canards, two engines side by side, intakes low on the fuselage sides under the cockpit, refuelling probe beside the canopy"),
    ("Neuro", "Dassault nEUROn", "france", "X", "ucav", "tailless stealth drone with a sharply swept arrowhead planform, a single intake on top behind the nose, a pointed nose, no cockpit"),

    # --- Germany ---
    ("Alphajet", "Dassault/Dornier Alpha Jet", "germany", 3, "light", "two-seat jet with shoulder wings and two engines (joint Germany / France)"),
    ("Tornada", "Panavia Tornado IDS", "germany", 3, "strike", "two-seat variable-sweep wings shown half swept, big single tail (joint Germany / England / Italy)"),
    ("Typhon", "Eurofighter Typhoon", "germany", 4, "air", "cranked delta wing with canards just ahead of the cockpit, a wide 'smiling' chin intake under the cockpit, two engines, a single tall tail"),
    ("Vertika", "EWR VJ 101C", "germany", "X", "vtol", "supersonic VTOL prototype with tilting engine pods on the wingtips"),
    ("Barracada", "EADS Barracuda", "germany", "X", "ucav", "sleek unmanned jet with a dorsal intake and V-tail"),

    # --- England ---
    ("Huntsman", "Hawker Hunter", "england", 2, "multi", "elegant single-engine swept-wing fighter with intakes in the wing roots, a short fat fuselage and a mid-mounted tailplane on the fin"),
    ("Volcan", "Avro Vulcan", "england", 2, "bomber", "huge delta-wing V-bomber with a thick wing, four engines buried in the wing roots with slot intakes, one large tail fin, no horizontal tail"),
    ("Sea Vixa", "de Havilland Sea Vixen", "england", 2, "carrier", "twin-boom carrier fighter with an offset cockpit"),
    ("Thunderflash", "English Electric Lightning", "england", 2, "int", "two engines stacked on top of each other, sharply swept wings, nose intake"),
    ("Privateer", "Blackburn Buccaneer", "england", 2, "carrier", "carrier strike jet with a T-tail and area-ruled fuselage"),
    ("TSR-2 Strikemaster", "BAC TSR-2", "england", "X", "strike", "long fuselage, small delta wings with drooped tips, all-moving tail"),
    ("Taranys", "BAE Taranis", "england", "X", "ucav", "tailless stealth drone with a wide blended body, a small diamond-shaped intake on top, swept wings with a W-shaped trailing edge, no cockpit"),
    ("Tempesta", "GCAP / Tempest concept", "england", "X", "stealth", "sixth-generation stealth fighter with a large delta wing and twin canted tails (joint England / Italy / Japan)"),

    # --- Italy ---
    ("Macchi 339", "Aermacchi MB-339", "italy", 2, "light", "two-seat light attack jet with wingtip tanks"),
    ("AMK Ghibly", "AMX A-11 Ghibli", "italy", 3, "attack", "small subsonic attack jet with swept shoulder wings"),

    # --- Turkey ---
    ("Hurrjet", "TAI Hürjet", "turkey", 4, "light", "two-seat supersonic light jet with side intakes"),
    ("KHAN", "TAI KAAN", "turkey", 5, "stealth", "large twin-engine stealth fighter with a long chined nose, intakes under the cockpit sides, trapezoid wings, twin canted tails, two round nozzles"),
    ("Anka-X", "TAI Anka-3", "turkey", "X", "ucav", "tailless jet drone with a broad cranked-kite flying wing, a flush intake on top behind a rounded nose, no cockpit"),
    ("Kizilma", "Bayraktar Kızılelma", "turkey", "X", "ucav", "single-engine jet combat drone with canards and twin canted tails"),

    # --- Pakistan ---
    ("QX-5 Fanblade", "Nanchang Q-5 / A-5", "china", 2, "attack", "MiG-19-based attack jet with side intakes and a pointed nose (China, also Pakistan)"),
    ("JF-17 Thunderclap", "PAC/CAC JF-17 Thunder", "pakistan", 4, "multi", "single engine, side intakes with bump inlets, single tail"),
    ("AZM", "Project AZM concept", "pakistan", "X", "stealth", "fifth-generation stealth fighter concept (invent a believable one)"),

    # --- Japan ---
    ("Mitsuboshi F-1", "Mitsubishi F-1", "japan", 3, "attack", "Jaguar-like shoulder wings, twin engines, anti-ship missiles"),
    ("Zero-II", "Mitsubishi F-2", "japan", 4, "multi", "F-16-like body with a larger wing, anti-ship missiles"),
    ("Shinden-X", "Mitsubishi X-2 Shinshin", "japan", "X", "stealth", "small stealth demonstrator with a short body, large canted twin tails, rectangular side intakes and paddle thrust-vectoring nozzles"),

    # --- South Korea ---
    ("FX-50 Gilded Eagle", "KAI FA-50 Fighting Eagle", "southkorea", 3, "light", "F-16-like light jet with side intakes"),
    ("KX-21 Maehawk", "KAI KF-21 Boramae", "southkorea", 4, "multi", "twin-engine fighter with stealth-shaped body and twin canted tails"),
    ("Loyal-K", "Korean loyal-wingman drone (LOWUS)", "southkorea", "X", "ucav", "small stealthy combat drone with a flat chined body, an intake under the nose, swept wings and a V-tail, no cockpit"),

    # --- Russia ---
    ("Tv-22M Backfin", "Tupolev Tu-22M", "russia", 3, "bomber", "variable-sweep wings shown half swept, two engines with large side intakes"),
    ("Tv-160 Swanwing", "Tupolev Tu-160", "russia", 3, "bomber", "huge white variable-sweep bomber, wings half swept, four engines in two pods"),
    ("Sk-70 Okhota", "Sukhoi S-70 Okhotnik-B", "russia", "X", "ucav", "very large bat-like tailless stealth flying wing, a dorsal intake, a single exhaust at the centre of the trailing edge, no cockpit"),
    ("Grom-K", "Kronshtadt Grom", "russia", "X", "ucav", "small jet combat drone with a slim body, an intake on top behind the nose, short swept wings and a V-tail, no cockpit"),
    ("Sk-75 Stalemate", "Sukhoi Su-75 Checkmate", "russia", "X", "stealth", "single-engine stealth fighter with a V-tail and chin intake"),
    ("MiK-41", "MiG-41 concept", "russia", "X", "int", "future long-range high-speed interceptor (invent a believable one)"),
    ("Sk-100 Sotnya", "Sukhoi T-4", "russia", "X", "bomber", "Mach 3 delta-wing bomber with a drooping nose and canards"),
    ("PAK-DX", "Tupolev PAK DA concept", "russia", "X", "bomber", "stealth flying-wing strategic bomber (invent a believable one)"),

    # --- Ukraine ---
    ("L-39U Albatross", "Aero L-39 Albatros", "ukraine", 2, "light", "two-seat jet trainer with wingtip tanks, armed for light attack"),
    ("An-225 Dreamer", "Antonov An-225 Mriya", "ukraine", 4, "transport", "the world's largest aircraft: six engines, twin tails, high wings"),

    # --- India ---
    ("Tejaz", "HAL Tejas Mk1A", "india", 4, "multi", "small tailless compound-delta fighter with no canards and no horizontal tail, intakes on the fuselage sides, single tail"),
    ("Seatejaz", "HAL TEDBF concept", "india", "X", "carrier", "twin-engine carrier fighter with canards and a delta wing"),
    ("AMKA", "HAL AMCA concept", "india", "X", "stealth", "twin-engine stealth fighter with diamond-shaped wings, intakes on the fuselage sides, twin canted tails and a pointed chined nose"),
    ("Ghatak", "DRDO Ghatak", "india", "X", "ucav", "tailless stealth drone with a lambda-shaped wing, a long pointed nose, a dorsal intake and a saw-tooth trailing edge, no cockpit"),
    ("CATS Warrior", "HAL CATS Warrior", "india", "X", "ucav", "small stealthy loyal-wingman drone with twin canted tails"),

    # --- Egypt ---
    ("Helwan HX-300", "Helwan HA-300", "egypt", "X", "int", "tiny delta-wing supersonic interceptor prototype"),

    # --- China ---
    ("JX-8 Finbacker", "Shenyang J-8II", "china", 3, "int", "twin-engine delta-wing interceptor with side intakes"),
    ("JHX-7 Flounderer", "Xi'an JH-7", "china", 3, "strike", "two-seat twin-engine strike jet with high swept wings"),
    ("HX-6 Godwing", "Xi'an H-6K", "china", 3, "bomber", "swept-wing bomber with large turbofans in the wing roots and cruise missiles under the wings"),
    ("JX-10 Vigor", "Chengdu J-10C", "china", 4, "multi", "single-engine delta wing with canards behind the cockpit, a bump chin intake under the cockpit, twin ventral fins under the tail"),
    ("JX-15 Sea Shark", "Shenyang J-15", "china", 4, "carrier", "Su-33-style naval fighter with canards beside the cockpit, folding wings shown spread, arrestor hook, grey radar nose"),
    ("JX-20 Jade Dragon", "Chengdu J-20", "china", 5, "stealth", "long stealth fighter with canards, delta wing and twin canted tails"),
    ("JX-35 Seastar", "Shenyang J-35", "china", 5, "carrier", "twin-engine carrier stealth fighter with twin canted tails"),
    ("GX-11 Keen Sword", "Hongdu GJ-11 Sharp Sword", "china", "X", "ucav", "tailless stealth flying wing with a long narrow pointed nose, a dorsal intake, swept wings and a jagged trailing edge, no cockpit"),
    ("HX-20 Night Phoenix", "Xi'an H-20 concept", "china", "X", "bomber", "stealth flying-wing strategic bomber (invent a believable one)"),
    ("JX-36 Tri-Dragon", "Chengdu 'J-36' prototype", "china", "X", "stealth", "large tailless diamond-wing stealth jet with three engines"),
    ("JX-50 Silver Kite", "Shenyang 'J-50' prototype", "china", "X", "stealth", "tailless stealth fighter with a lambda wing and folding wingtips"),
    # --- Iran (IDEA-15) ---
    ("Saeqa", "HESA Saeqeh", "iran", 3, "air", "F-5-based light fighter with twin outward-canted tails"),
    ("Karrak", "Karrar jet drone", "iran", 3, "ucav", "small jet drone with a top-mounted engine pod, straight wings and a twin tail"),
    ("Shard-171 Simurgh", "Shahed-171 Simorgh", "iran", "X", "ucav", "tailless flying-wing drone shaped like the RQ-170"),
    ("Qahir-X", "IAIO Qaher-313 concept", "iran", "X", "stealth", "small angular stealth fighter with downturned wingtips and twin canted tails"),
]

# (game name, base game name, real inspiration, nation, tier, role, how it differs)
VARIANTS = [
    ("AF-22 Raptorex Liberty", "AF-22 Raptorex", "F-22 Raptor", "usa", 5, "stealth", "US national version"),
    ("Mirago 2000-5", "Mirago 2000", "Mirage 2000-5", "france", 3, "air", "air-superiority version"),
    ("Mirago 2000N", "Mirago 2000", "Mirage 2000N/D", "france", 3, "strike", "two-seat strike version"),
    ("Starflash G", "AF-104 Starflash", "F-104G", "germany", 2, "strike", "strike / anti-ship version"),
    ("Spectre F", "AF-4 Spectre II", "F-4F Phantom II", "germany", 3, "air", "lightened air-defence version"),
    ("Tornada GR", "Tornada", "Tornado GR4", "england", 3, "strike", "RAF strike version"),
    ("Sea Harrow", "Harrow", "Sea Harrier", "england", 3, "vtol", "naval version with a raised cockpit and a radar nose"),
    ("Starflash S", "AF-104 Starflash", "F-104S", "italy", 2, "int", "Italian interceptor version"),
    ("Harrow II+", "Harrow", "AV-8B+ Harrier II", "italy", 4, "vtol", "larger wing and a radar nose"),
    ("Spectre T Terminator", "AF-4 Spectre II", "F-4E 2020 Terminator", "turkey", 3, "multi", "upgraded Turkish version"),
    ("AF-16T Ozgur", "AF-16 Fighting Kestrel", "F-16 (Turkish licence-built)", "turkey", 3, "multi", "Turkish version"),
    ("Typhon T", "Typhon", "Eurofighter Typhoon", "turkey", 4, "air", "Turkish version"),
    ("Mirago III-5 ROSE", "Mirago III", "Mirage III/5 ROSE", "pakistan", 2, "strike", "upgraded strike / anti-ship version"),
    ("FX-6 Farmhand-P", "MiK-19 Farmhand", "Shenyang F-6", "pakistan", 2, "air", "Chinese-built version"),
    ("FX-7 Skybolt", "MiK-21 Fishbone", "Chengdu F-7PG", "pakistan", 2, "int", "Chinese-built version with a double-delta wing"),
    ("JX-10P Vigor", "JX-10 Vigor", "J-10CE", "pakistan", 4, "multi", "export version"),
    ("JX-35P Seastar", "JX-35 Seastar", "J-35A", "pakistan", 5, "stealth", "land-based export version"),
    ("Starflash J", "AF-104 Starflash", "F-104J", "japan", 2, "int", "Japanese version"),
    ("Spectre J Kai", "AF-4 Spectre II", "F-4EJ Kai", "japan", 3, "int", "Japanese version"),
    ("Iron Eagle J", "AF-15 Iron Eagle", "F-15J", "japan", 3, "air", "Japanese version"),
    ("Tiger-K", "AF-5 Tigerette", "F-5E Jegong-ho", "southkorea", 2, "air", "Korean-built version"),
    ("Spectre K", "AF-4 Spectre II", "F-4E", "southkorea", 3, "multi", "Korean version"),
    ("Iron Eagle K", "AF-15E Strike Eagle", "F-15K Slam Eagle", "southkorea", 4, "strike", "Korean version"),
    ("KX-21EX", "KX-21 Maehawk", "KF-21 Block III", "southkorea", 5, "stealth", "stealthier version with internal weapon bays"),
    ("Sk-27U Flankard", "Sk-27 Flankard", "Su-27 P1M", "ukraine", 3, "air", "upgraded Ukrainian version"),
    ("MiK-29U Fulcra", "MiK-29 Fulcra", "MiG-29MU2", "ukraine", 3, "multi", "upgraded Ukrainian version"),
    ("Sk-24U Stormcarrier", "Sk-24 Fencor", "Su-24M with cruise missiles", "ukraine", 3, "strike", "carries two large cruise missiles"),
    ("Sk-25U Rook", "Sk-25 Rook", "Su-25M1", "ukraine", 3, "attack", "upgraded Ukrainian version"),
    ("Gryphon EU", "Gryphon E", "Gripen E", "ukraine", 4, "multi", "Ukrainian version"),
    ("MiK-19P", "MiK-19 Farmhand", "MiG-19P", "cuba", 2, "int", "radar-nose interceptor version"),
    ("MiK-21 Fishbone-Bis", "MiK-21 Fishbone", "MiG-21bis", "cuba", 2, "air", "Cuban version"),
    ("MiK-23 Flintlock-C", "MiK-23 Flintlock", "MiG-23ML", "cuba", 3, "int", "Cuban version"),
    ("MiK-29 Fulcra-C", "MiK-29 Fulcra", "MiG-29", "cuba", 3, "air", "Cuban version"),
    ("MiK-21 Bisonne", "MiK-21 Fishbone", "MiG-21 Bison", "india", 3, "int", "upgraded Indian version"),
    ("MiK-27 Bahadur", "MiK-27 Flailer", "MiG-27ML Bahadur", "india", 3, "attack", "Indian version"),
    ("Jaguara Shamsher", "Jaguara", "Jaguar IS Shamsher", "india", 3, "strike", "Indian deep-strike version"),
    ("Sk-30I Flankard-I", "Sk-30 Flankard-C", "Su-30MKI", "india", 4, "multi", "Indian version with thrust vectoring"),
    ("MiK-29K Seafulcra-I", "MiK-29K Seafulcra", "MiG-29K", "india", 4, "carrier", "Indian navy version"),
    ("Tejaz Mk2", "Tejaz", "HAL Tejas Mk2", "india", 4, "multi", "larger version with canards"),
    ("Rafal-I", "Rafal F4", "Rafale EH", "india", 4, "multi", "Indian version"),
    ("MiK-21 Fishbone-E", "MiK-21 Fishbone", "MiG-21", "egypt", 2, "int", "Egyptian version"),
    ("Mirago 5E", "Mirago III", "Mirage 5", "egypt", 2, "multi", "ground-attack version with a slimmer nose"),
    ("Sk-20 Fitterwing-E", "Sk-17 Fitterwing", "Su-20", "egypt", 3, "attack", "Egyptian version"),
    ("Spectre E", "AF-4 Spectre II", "F-4E Phantom II", "egypt", 3, "multi", "Egyptian version"),
    ("Alphajet E", "Alphajet", "Alpha Jet MS", "egypt", 3, "light", "Egyptian light-attack version"),
    ("Rafal EM", "Rafal F4", "Rafale EM", "egypt", 4, "multi", "Egyptian version"),
    ("MiK-29M Fulcra-M", "MiK-29 Fulcra", "MiG-29M", "egypt", 4, "multi", "upgraded multirole version"),
    ("JX-6 Farmhand-C", "MiK-19 Farmhand", "Shenyang J-6", "china", 2, "air", "Chinese-built version"),
    ("JX-7 Fishbone-C", "MiK-21 Fishbone", "Chengdu J-7", "china", 2, "int", "Chinese-built version"),
    ("JX-11 Copperflank", "Sk-27 Flankard", "Shenyang J-11B", "china", 3, "air", "Chinese-built version"),
    ("JX-16 Red Eagle", "Sk-30 Flankard-C", "Shenyang J-16", "china", 4, "strike", "two-seat Chinese strike version"),
    ("AF-86 Sabrecat-IR", "AF-86 Sabrecat", "F-86F Sabre", "iran", 1, "air", "Iranian version"),
    ("Tigerette-IR", "AF-5 Tigerette", "F-5E Tiger II", "iran", 3, "air", "Iranian version"),
    ("Azarakh", "AF-5 Tigerette", "HESA Azarakhsh", "iran", 3, "air", "Iranian-built version with a lengthened body"),
    ("Kosar", "AF-5 Tigerette", "HESA Kowsar", "iran", 3, "light", "two-seat Iranian-built version"),
    ("Spectre IR", "AF-4 Spectre II", "F-4E Phantom II", "iran", 3, "strike", "Iranian version"),
    ("Persian Bobcat", "AF-14 Bobcat", "F-14A Tomcat", "iran", 4, "int", "Iranian version with very long-range missiles"),
    ("MiK-29 Fulcra-IR", "MiK-29 Fulcra", "MiG-29A", "iran", 3, "air", "Iranian version"),
    ("Sk-24 Fencor-IR", "Sk-24 Fencor", "Su-24MK", "iran", 3, "strike", "Iranian version"),
    ("Mirago F1-IR", "Mirago F1", "Mirage F1EQ", "iran", 3, "multi", "Iranian version"),
]
