#!/usr/bin/env python3
"""
Generates artsrc/prompts/sound-prompts.md: one prompt per sound the mod plays, to replace the original Red Alert
audio (IDEA-31). Edit the tables below and re-run.

  python3 artsrc/prompts/make_sound_prompts.py

Voices (announcer and unit lines) are written for Gemini text-to-speech: pick the listed prebuilt voice, paste the
prompt, download the WAV. Sound effects can't be made with Gemini TTS, so their prompts are plain text-to-audio
descriptions for a sound-effect generator (ElevenLabs Sound Effects, Stable Audio Open...).

Inventory taken on 2026-10-29 from mods/rapx/audio/*.yaml, rules/, weapons/ and the C# trait defaults.
The Save-as name keeps the original file name so the yaml needs as few changes as possible.
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sound-prompts.md")

# ---------------------------------------------------------------------------------------------------------------
# Characters: key -> (display name, Gemini prebuilt voice, style used in every prompt, save folder)
# Voices are suggestions; audition a few in AI Studio and keep one per character for every line.
# ---------------------------------------------------------------------------------------------------------------
CAST = {
    "eva-union": ("Union announcer (EVA)", "Kore",
                  "a calm, precise female military command-AI voice: cool, confident and clipped, slightly synthetic, "
                  "like a modern NATO operations computer, neutral international English",
                  "eva/union"),
    "eva-vanguard": ("Vanguard announcer (EVA)", "Charon",
                     "a deep, stern male command voice: slow, heavy and authoritative, with a slight Eastern European "
                     "accent, like a state military radio broadcast",
                     "eva/vanguard"),
    "union-inf1": ("Union infantry, voice 1", "Puck",
                   "a young, alert male infantry soldier on a field radio, crisp and eager, General American accent",
                   "voices/union-inf1"),
    "union-inf2": ("Union infantry, voice 2", "Algenib",
                   "a gravelly veteran male sergeant on a field radio, calm and dry, General American accent",
                   "voices/union-inf2"),
    "union-veh1": ("Union vehicle crew, voice 1", "Iapetus",
                   "a male tank commander speaking over a vehicle intercom with engine rumble implied, clear and "
                   "professional, General American accent",
                   "voices/union-veh1"),
    "union-veh2": ("Union vehicle crew, voice 2", "Alnilam",
                   "a firm male armoured-vehicle driver on a crackly intercom, short and matter-of-fact, British accent",
                   "voices/union-veh2"),
    "vanguard-inf1": ("Vanguard infantry, voice 1", "Fenrir",
                      "an eager young male conscript on a field radio, fast and keen, slight Eastern European accent",
                      "voices/vanguard-inf1"),
    "vanguard-inf2": ("Vanguard infantry, voice 2", "Gacrux",
                      "a hardened older male soldier on a field radio, deep and unhurried, slight Eastern European accent",
                      "voices/vanguard-inf2"),
    "vanguard-veh1": ("Vanguard vehicle crew, voice 1", "Orus",
                      "a stern male tank commander over a vehicle intercom, heavy and firm, slight Eastern European accent",
                      "voices/vanguard-veh1"),
    "vanguard-veh2": ("Vanguard vehicle crew, voice 2", "Schedar",
                      "a gruff male vehicle driver over a crackly intercom, blunt and short, slight Eastern European accent",
                      "voices/vanguard-veh2"),
    "engineer": ("Engineer", "Sadaltager",
                 "a practical, slightly nerdy male combat engineer, helpful and quick", "voices/engineer"),
    "medic": ("Medic", "Sulafat",
              "a warm, steady female field medic, reassuring but brisk", "voices/medic"),
    "mechanic": ("Mechanic", "Umbriel",
                 "a laid-back male mechanic with a thick American Southern drawl, folksy and cheerful", "voices/mechanic"),
    "tanya": ("Tanya (commando)", "Zephyr",
              "a cocky, confident female special-forces commando, playful and fearless", "voices/tanya"),
    "spy": ("Spy", "Algieba",
            "a smooth, quietly confident male spy with a refined British accent, understated", "voices/spy"),
    "thief": ("Thief", "Enceladus",
              "a sly, whispery male thief, sneaky and amused", "voices/thief"),
    "shock": ("Shock Trooper", "Rasalgethi",
              "an aggressive male shock trooper in a powered suit, electric and intense, slight Eastern European accent",
              "voices/shock"),
    "civ-male": ("Civilian (male)", "Achird", "a nervous ordinary male civilian", "voices/civ-male"),
    "civ-female": ("Civilian (female)", "Aoede", "a nervous ordinary female civilian", "voices/civ-female"),
    "dying": ("Infantry deaths", "Puck",
              "a soldier being hit in battle; no words, only the vocal sound", "voices/deaths"),
}

DELIVERY = {
    "": "in a steady, even tone",
    "urgent": "urgently, as an alarm",
    "warn": "as a clear warning, slightly faster",
    "win": "with restrained triumph",
    "grim": "gravely",
    "ok": "briskly",
}

# ---------------------------------------------------------------------------------------------------------------
# EVA announcements: (notification key, file, text, delivery). Recorded once per side.
# ---------------------------------------------------------------------------------------------------------------
EVA_NOW = [  # used by skirmish and multiplayer today
    ("StartGame", "bctrinit", "Battle control online.", ""),
    ("Leave", "bct1", "Battle control terminated.", "grim"),
    ("Win, MissionAccomplished", "misnwon1", "Mission accomplished.", "win"),
    ("Lose, MissionFailed", "misnlst1", "Mission failed.", "grim"),
    ("GameSaved", "save1", "Game saved.", ""),
    ("GameLoaded", "load1", "Game loaded.", ""),
    ("Building", "abldgin1", "Building.", "ok"),
    ("ConstructionComplete", "conscmp1", "Construction complete.", ""),
    ("Training", "train1", "Training.", "ok"),
    ("UnitReady", "unitrdy1", "Unit ready.", ""),
    ("OnHold", "onhold1", "On hold.", "ok"),
    ("Cancelled", "cancld1", "Cancelled.", "ok"),
    ("BuildingInProgress", "progres1", "Unable to comply. Building in progress.", ""),
    ("NoBuild", "nobuild1", "Unable to build more.", ""),
    ("NewOptions", "newopt1", "New construction options.", ""),
    ("BuildingCannotPlaceAudio", "nodeply1", "Cannot deploy here.", ""),
    ("PrimaryBuildingSelected", "pribldg1", "Primary building selected.", ""),
    ("StructureSold", "strusld1", "Structure sold.", ""),
    ("Repairing", "repair1", "Repairing.", "ok"),
    ("UnitRepaired", "unitrep1", "Unit repaired.", ""),
    ("ReinforcementsArrived", "reinfor1", "Reinforcements have arrived.", ""),
    ("SelectTarget", "slcttgt1", "Select target.", ""),
    ("InsufficientFunds", "nofunds1", "Insufficient funds.", ""),
    ("SilosNeeded", "silond1", "Silos needed.", ""),
    ("LowPower", "lopower1", "Low power.", "warn"),
    ("InsufficientPower", "nopowr1", "Insufficient power.", "warn"),
    ("BaseAttack", "baseatk1", "Our base is under attack.", "urgent"),
    ("HarvesterAttack", "harvatk1", "Harvester under attack.", "urgent"),
    ("UnitLost", "unitlst1", "Unit lost.", "grim"),
    ("AirUnitLost", "aunitl1", "Aircraft lost.", "grim"),
    ("NavalUnitLost", "navylst1", "Naval unit lost.", "grim"),
    ("BuildingCaptured", "strucap1", "Structure captured.", ""),
    ("BuildingInfiltrated", "bldginf1", "Building infiltrated.", "warn"),
    ("CreditsStolen", "credit1", "Credits stolen.", "warn"),
    ("UnitStolen", "unitsto", "Unit stolen.", "warn"),
    ("AbombPrepping", "aprep1", "Atomic weapon being prepared.", ""),
    ("AbombReady", "aready1", "Atomic weapon ready.", ""),
    ("AbombLaunchDetected", "alaunch1", "Warning: atomic launch detected.", "urgent"),
    ("ChronosphereCharging", "chrochr1", "Chronosphere charging.", ""),
    ("ChronosphereReady", "chrordy1", "Chronosphere ready.", ""),
    ("IronCurtainCharging", "ironchg1", "Iron Curtain charging.", ""),
    ("IronCurtainReady", "ironrdy1", "Iron Curtain ready.", ""),
    ("SonarPulseReady", "pulse1", "Sonar pulse ready.", ""),
    ("SpyPlaneReady", "spypln1", "Spy plane ready.", ""),
    ("SatelliteLaunched", "satlnch1", "Satellite launched.", ""),
    ("FourtyMinutesRemaining", "40minr", "Forty minutes remaining.", ""),
    ("ThirtyMinutesRemaining", "30minr", "Thirty minutes remaining.", ""),
    ("TwentyMinutesRemaining", "20minr", "Twenty minutes remaining.", ""),
    ("TenMinutesRemaining", "10minr", "Ten minutes remaining.", ""),
    ("WarningFiveMinutesRemaining", "5minr", "Warning: five minutes remaining.", "warn"),
    ("WarningFourMinutesRemaining", "4minr", "Warning: four minutes remaining.", "warn"),
    ("WarningThreeMinutesRemaining", "3minr", "Warning: three minutes remaining.", "warn"),
    ("WarningTwoMinutesRemaining", "2minr", "Warning: two minutes remaining.", "warn"),
    ("WarningOneMinuteRemaining", "1minr", "Warning: one minute remaining.", "urgent"),
]

EVA_CAMPAIGN = [  # not used in skirmish; generic lines worth having for our own campaign (IDEA-18)
    ("ObjectiveMet", "objmet1", "Objective complete.", "win"),
    ("FirstObjectiveMet", "1objmet1", "First objective complete.", "win"),
    ("SecondObjectiveMet", "2objmet1", "Second objective complete.", "win"),
    ("ThirdObjectiveMet", "3objmet1", "Third objective complete.", "win"),
    ("ObjectiveNotMet", "objnmet1", "Objective failed.", "grim"),
    ("ObjectiveReached", "objrch1", "Objective reached.", ""),
    ("ObjectiveNotReached", "objnrch1", "Objective not reached.", "grim"),
    ("MissionTimerInitialised", "mtimein1", "Mission timer initialised.", ""),
    ("TimerStarted", "timergo1", "Timer started.", ""),
    ("TimerStopped", "timerno1", "Timer stopped.", ""),
    ("EnemyDetected", "enmydet", "Enemy detected.", "warn"),
    ("EnemyUnitsApproaching", "enmyapp1", "Enemy units approaching.", "warn"),
    ("CommandCenterAttack", "cmdcntr1", "Command center under attack.", "urgent"),
    ("StructureDestroyed", "strckil1", "Structure destroyed.", "grim"),
    ("ExplosiveChargePlaced", "xploplc1", "Explosive charge placed.", ""),
    ("ControlCenterDeactivated", "cntlded1", "Control center deactivated.", ""),
    ("ConvoyApproaching", "convyap1", "Convoy approaching.", ""),
    ("ConvoyUnitLost", "convlst1", "Convoy unit lost.", "grim"),
    ("TargetFreed", "targfre1", "Target freed.", ""),
    ("TargetRescued", "targres1", "Target rescued.", "win"),
    ("SignalFlare", "flare1", "Signal flare detected.", ""),
    ("SignalFlareNorth", "flaren1", "Signal flare detected. North.", ""),
    ("SignalFlareSouth", "flares1", "Signal flare detected. South.", ""),
    ("SignalFlareEast", "flaree1", "Signal flare detected. East.", ""),
    ("SignalFlareWest", "flarew1", "Signal flare detected. West.", ""),
    ("AlliedReinforcementsArrived", "aarrive1", "Union reinforcements have arrived.", ""),
    ("SovietReinforcementsArrived", "sovrein1", "Vanguard reinforcements have arrived.", ""),
    ("AlliedForcesApproaching", "aappro1", "Union forces approaching.", "warn"),
    ("SovietForcesApproaching", "sovfapp1", "Vanguard forces approaching.", "warn"),
    ("UnitArmorUpgraded", "armorup1", "Unit armor upgraded.", ""),
    ("UnitFirepowerUpgraded", "firepo1", "Unit firepower upgraded.", ""),
    ("UnitSpeedUpgraded", "unitspd1", "Unit speed upgraded.", ""),
    ("UnitFull", "unitful1", "Unit full.", ""),
    ("UnitSold", "unitsld1", "Unit sold.", ""),
]

EVA_SKIP = [  # tied to the classic missions or never played; not recorded
    ("AbombAvailable, AtomBombPrepping, AtomBombLaunchDetected", "never played (duplicates of the Abomb lines above)"),
    ("BuildingProgress, OperationControlTerminated", "never played"),
    ("ChronosphereTestSuccessful", "classic Allied mission"),
    ("CommandoFreed/Rescued, KosyginFreed/Rescued, MercenaryFreed/Rescued, TanyaFreed/Rescued",
     "classic mission characters"),
    ("AlliedReinforcementsNorth/South/East/West", "classic missions; the campaign can use the flare + reinforcement lines"),
    ("AlliedForcesSelected/Fallen, SovietEmpireSelected/Fallen, SovietForcesFallen", "never played; old side names"),
]

# ---------------------------------------------------------------------------------------------------------------
# Unit voices: (file, text, delivery note). Side voices are recorded by both voices of each side.
# ---------------------------------------------------------------------------------------------------------------
INFANTRY = [  # GenericVoice: riflemen, grenadiers, rocket soldiers, flamethrowers...
    ("await1", "Awaiting orders.", "select"),
    ("ready", "Ready.", "select"),
    ("report1", "Reporting.", "select"),
    ("yessir1", "Yes, sir?", "select"),
    ("ackno", "Acknowledged.", "order"),
    ("affirm1", "Affirmative.", "order"),
    ("noprob", "No problem.", "order"),
    ("overout", "Over and out.", "order"),
    ("ritaway", "Right away.", "order"),
    ("roger", "Roger that.", "order"),
    ("ugotit", "You got it.", "order"),
]
VEHICLE = [  # VehicleVoice: all tanks and vehicles
    ("vehic1", "Vehicle reporting.", "select"),
    ("yessir1", "Yes, sir?", "select"),
    ("report1", "Reporting.", "select"),
    ("await1", "Awaiting orders.", "select"),
    ("ackno", "Acknowledged.", "order"),
    ("affirm1", "Affirmative.", "order"),
]
SPECIAL = {
    "engineer": [("eengin1", "Engineer here.", "select"), ("eyessir1", "Yes, sir?", "select"),
                 ("eaffirm1", "Affirmative.", "order"), ("emovout1", "Moving out.", "order")],
    "medic": [("mrespon1", "Medic responding.", "select"), ("myessir1", "Yes, sir?", "select"),
              ("maffirm1", "Affirmative.", "order"), ("mmovout1", "Moving out.", "order")],
    "mechanic": [("mhuh1", "Huh?", "select"), ("mhowdy1", "Howdy!", "select"),
                 ("mlaff1", "(a short amused chuckle) <laugh> Heh heh heh.", "select"),
                 ("mboss1", "Sure thing, boss.", "move"), ("mhear1", "I hear ya.", "move"),
                 ("myes1", "Yep.", "move"), ("mrise1", "Rise and shine!", "move"),
                 ("mhotdig1", "Hot diggity!", "repair order"), ("mwrench1", "Pass me that wrench.", "repair order"),
                 ("myeehaw1", "Yee-haw!", "repair order")],
    "tanya": [("yo1", "Yo!", "select"), ("yes1", "Yes?", "select"), ("yeah1", "Yeah?", "select"),
              ("onit1", "I'm on it.", "move"), ("cmon1", "Come on!", "move"), ("rokroll1", "Let's rock!", "move"),
              ("tuffguy1", "That all you've got?", "attack"), ("bombit1", "Light it up!", "attack"),
              ("laugh1", "(a short confident laugh) <laugh> Ha!", "spawned"),
              ("gotit1", "Got 'em.", "after a kill"), ("lefty1", "Too easy.", "after a kill"),
              ("keepem1", "Keep 'em coming!", "after demolishing a building"),
              ("tandeth1", "(a short sharp pained cry as she is hit, no words) Aah—!", "death")],
    "spy": [("syessir1", "Yes, sir?", "select"), ("scomnd1", "Commander?", "select"),
            ("sonway1", "On my way.", "move"), ("sindeed1", "Indeed.", "move"),
            ("sking1", "Consider it done.", "infiltrate order")],
    "thief": [("swhat1", "What?", "select"), ("syeah1", "Yeah?", "select"),
              ("saffirm1", "Affirmative.", "move"), ("smout1", "Moving out.", "move"), ("sokay1", "Okay.", "move"),
              ("scandy", "Easy money.", "steal order"), ("sclean1", "Cleaned 'em out.", "steal order"),
              ("ssteal1", "Nobody will notice.", "steal order")],
    "shock": [("jjuice1", "Got the juice!", "select"), ("jjump1", "Charged up.", "select"), ("jyes1", "Yes?", "select"),
              ("jdance1", "Let's dance.", "move"), ("jchrge1", "Charging!", "move"), ("jpower1", "Full power!", "move"),
              ("jburn1", "Burn!", "attack"), ("jcrisp1", "Extra crispy!", "attack"),
              ("jshock1", "Shock therapy!", "attack"), ("jlight1", "Lights out!", "attack")],
    "civ-male": [("guyyeah1", "Yeah?", "select"), ("guyokay1", "Okay, okay!", "order")],
    "civ-female": [("girlyeah", "Yes?", "select"), ("girlokay", "Okay!", "order")],
    "dying": [("dedman1", "(a short sharp cry of pain, no words) Agh!", "shot"),
              ("dedman2", "(a choked grunt, then a groan, no words) Ugh... hhh.", "shot"),
              ("dedman3", "(a loud agonised scream, no words) Aaaaagh!", "shot"),
              ("dedman4", "(a surprised gasp cut short, no words) Hhuh—!", "shot"),
              ("dedman5", "(a long falling scream fading out, no words) Aaaaaaaah...", "blown up"),
              ("dedman7", "(a short winded grunt, no words) Ugh!", "shot"),
              ("dedman8", "(a pained yell, no words) Yaaagh!", "shot"),
              ("dedman10", "(a panicked scream of someone on fire, no words) Aaah! Aaaah!", "burned"),
              ("dedman6", "(a strangled, shaking cry of someone electrocuted, no words) Ggghhaaagh!", "electrocuted")],
}
VOICE_SKIP = [("EinsteinVoice, StavrosVoice, AntVoice", "classic mission characters, removed with the classic missions")]

# ---------------------------------------------------------------------------------------------------------------
# Sound effects (not Gemini): (file, used by, prompt). Prompts are written for a text-to-sound-effect model.
# ---------------------------------------------------------------------------------------------------------------
SFX = {
    "Guns": [
        ("gun11", "M1Carbine (rifle infantry)", "Short burst of three rapid modern assault-rifle shots, outdoors, punchy, dry tail, no echo"),
        ("gun27", "Pistol", "Single sharp 9mm pistol shot, outdoors, crisp crack, short tail"),
        ("silppk", "SilencedPPK (spy)", "Single suppressed pistol shot, a muffled 'thwip' with a soft metallic slide click"),
        ("gun5", "Sniper weapons", "Single powerful high-calibre sniper rifle shot, sharp crack with a long rolling outdoor echo"),
        ("pillbox1", "M60mg (pillbox, vehicles)", "Medium machine-gun burst, about one second of steady rapid fire, outdoors, gritty"),
        ("gun13", "Heavy machine guns", "Heavy .50 calibre machine-gun burst, slow thumping rate, deep and powerful, about one second"),
        ("aacanon3", "Anti-aircraft cannons", "Rapid anti-aircraft autocannon burst firing upward, four heavy thuds in quick succession with metallic clank"),
    ],
    "Cannons and turrets": [
        ("cannon1", "Tank cannons (most tanks)", "Single modern tank main-gun shot, big deep boom with a sharp crack and a short rumble tail"),
        ("cannon2", "25mm / 2-inch guns (light vehicles, gunboats)", "Single light autocannon shot, sharp mid-weight bang with metallic ring"),
        ("tank5", "155mm (artillery)", "Single heavy artillery howitzer firing, huge low boom with a long rolling echo across open terrain"),
        ("turret1", "8-inch naval guns, turret guns", "Single big naval gun shot, massive deep blast with a metallic turret clank and long echo over water"),
    ],
    "Rockets and missiles": [
        ("missile6", "Anti-ground rockets (rocket soldiers, launchers)", "Single shoulder-fired rocket launch: sharp pop then a fast whooshing hiss moving away"),
        ("missile7", "Maverick (aircraft air-to-ground)", "Air-launched missile release: short thump followed by a roaring rocket motor quickly streaking away"),
        ("missile1", "Nike SAM, SCUD", "Large missile launch from a launcher: heavy ignition roar building into a powerful rocket blast that rises and fades"),
        ("torpedo1", "Torpedo tubes (subs, destroyers)", "Submarine torpedo launch: compressed-air thump and an underwater whoosh with bubbles"),
        ("grenade1", "Grenade (grenadier)", "Hand grenade throw: a grunt-free arm swish and a small metallic clink of the pin, quiet"),
    ],
    "Explosions": [
        ("kaboom15", "Small explosions: depth charges, torpedoes, small units, artillery shells", "Small sharp explosion, tight punchy blast with a little debris, short tail"),
        ("kaboom12", "Medium cannon impacts, Mammoth tusk missiles", "Medium explosion, solid boom with crunching debris, about one second"),
        ("kaboom25", "Missile and grenade impacts, barrels, ore explosions, ship deaths", "Medium-large explosion with a fiery roar and falling debris, about two seconds"),
        ("kaboom22", "Big building and vehicle explosions, artillery, nuke", "Large building explosion, huge deep blast, collapsing structure and rubble raining down, three seconds"),
        ("kaboom1", "Nuclear blast, building heavy-damage", "Massive thunderous explosion like a nuclear detonation, deep sub-bass shockwave and long rumbling roar, five seconds"),
        ("firebl3", "Napalm, fireball weapons, SCUD impact, burning barrels", "Big fireball burst: whooshing ignition of flammable fuel with a roaring flame that dies down, two seconds"),
        ("h2obomb2", "Depth charges", "Underwater explosion: deep muffled thump followed by a large water eruption splash"),
        ("splash9", "Shots and debris landing in water", "Heavy object hitting water: a single big splash with droplets falling back"),
        ("mine1", "Anti-personnel mine", "Small landmine detonation, sharp crack with dirt spray"),
        ("mineblo1", "Anti-tank mine, MAD tank", "Big landmine explosion under a vehicle: heavy blast with metal debris clanging"),
    ],
    "Special weapons and powers": [
        ("tesla1", "Tesla coils and tanks, orbital laser", "Powerful electric discharge: a loud crackling Tesla-coil zap with buzzing arcs, one second"),
        ("tslachg2", "Tesla coil charging", "Tesla coil charging up: rising electric hum and crackle building tension, one and a half seconds"),
        ("ironcur9", "Iron Curtain activation, invulnerability crate", "Sci-fi force field activating: deep resonant hum swelling with a metallic shimmer, two seconds"),
        ("chrono2", "Chronosphere teleport", "Teleportation effect: a warping time-distortion whoosh with a bright crystalline ping, two seconds"),
        ("chrotnk1", "Chrono Tank jump", "Short sci-fi teleport zap: quick reverse-whoosh and an electric pop, one second"),
        ("madchrg2", "MAD tank charging", "Heavy machine winding up: hydraulic pumping and a rising mechanical whine, two seconds"),
        ("madexplo", "MAD tank shockwave", "Huge seismic shockwave: a deep booming pulse with ground rumble and metallic rattling, two seconds"),
        ("sonpulse", "Sonar pulse power", "Submarine sonar ping: a single clear resonant underwater 'ping' with a long echo"),
        ("heal2", "Healing (medic, heal crate)", "Gentle magical healing chime: soft shimmering ascending tones, one second"),
        ("fixit1", "Mechanic repairing", "Quick mechanic repair: two wrench clanks and a ratchet tightening a bolt"),
    ],
    "Units": [
        ("appear1", "Phase Tank cloak / decloak", "Stealth cloaking device: a soft rising electronic shimmer that fades out, one second"),
        ("subshow1", "Submarine surfacing", "Submarine surfacing: rush of water draining and a hull groan"),
        ("chute1", "Parachutes (paratroopers, parabombs, pilots)", "Parachute opening: a sudden fabric snap and flutter"),
        ("squishy2", "Infantry crushed by a vehicle", "Short cartoonish wet crunch, not graphic, quick"),
        ("minelay1", "Minelayer placing a mine", "Mechanical mine dispenser: a metal clunk and a latch click"),
        ("dogw3px", "Attack dog, select", "Single alert bark from a large guard dog"),
        ("dogy1", "Attack dog, move", "Short eager yip from a large dog"),
        ("dogg5p", "Attack dog, attack", "Large dog's aggressive snarl and bark lunging to attack"),
        ("dogw5", "Attack dog, death", "Dog's sharp pained yelp"),
        ("dogw7", "Attack dog, death (2)", "Dog's short whimper fading out"),
        ("dogw6", "Attack dog, burned / electrocuted", "Dog's frantic high yelp"),
    ],
    "Buildings": [
        ("placbldg", "Placing a building, wall", "Heavy construction piece slamming into place: deep thud with metal clank and dust"),
        ("build5", "Building construction animation, MCV deploy", "Construction site sounds: quick hydraulic hiss, metal panels unfolding and locking, two seconds"),
        ("cashturn", "Selling a building", "Building being dismantled for cash: a short metallic rattle ending in a cash register 'ka-ching'"),
        ("sandbag2", "Sandbag wall destroyed", "Sandbags bursting: a dull thump with sand pouring"),
        ("crmble2", "Concrete wall damaged", "Concrete crumbling: cracking stone and small rubble falling"),
        ("kaboom30", "Concrete wall destroyed", "Concrete wall collapsing: a heavy crunch and large chunks falling"),
    ],
    "Interface (UI)": [
        ("ramenu1", "Menu button click", "Short clean futuristic UI click, military computer style, very short"),
        ("rabeep1", "Chat message", "Short soft two-tone digital chat notification beep"),
        ("bleep11", "Power on, player joined", "Short rising electronic bleep, positive"),
        ("bleep12", "Power off, player left", "Short falling electronic bleep"),
        ("bleep17", "Lobby option changed", "Very short soft digital tick"),
        ("bleep9", "Base setup", "Short double electronic confirmation bleep"),
        ("bleep6", "Alert", "Short urgent electronic alert bleep"),
        ("bleep5", "Angry bleep (invalid action)", "Short low 'denied' error buzz, digital"),
        ("buzzy1", "Alert buzzer", "Harsh short military alarm buzzer"),
        ("beepslct", "Map beacon placed", "Bright radar beacon ping with a short echo"),
        ("radaron2", "Radar online", "Radar screen powering up: rising electronic sweep and a static fizz, one and a half seconds"),
        ("radardn1", "Radar offline", "Radar screen powering down: falling electronic tone and static fading out"),
        ("cashup1", "Credits counting up", "Tiny single coin-counter tick, very short, bright"),
        ("cashdn1", "Credits counting down", "Tiny single coin-counter tick, very short, slightly lower"),
        ("hydrod1", "Unit promoted (veterancy)", "Short triumphant electronic promotion chime, rising three notes"),
    ],
}
SFX_SKIP = [("antbite", "giant ants, classic missions only")]


def split_line(text):
    """'(performance note) spoken' -> ('performance note', 'spoken'); plain lines have no note."""
    if text.startswith("("):
        note, spoken = text[1:].split(")", 1)
        return note, spoken.strip()
    return "", text


def tts_style(cast_key, text, delivery):
    """Style for the Gemini TTS `style` field: character, delivery and any performance note."""
    note, _ = split_line(text)
    style = f"{CAST[cast_key][2]}; {delivery}"
    return f"{style}; {note}" if note else style


def tts_prompt(cast_key, text, delivery):
    note, spoken = split_line(text)
    extra = f" ({note})" if note else ""
    return f'In the voice of {CAST[cast_key][2]}, {delivery}{extra}, say: "{spoken}"'


def tts_jobs():
    """Every Gemini TTS line as (group, cast key, file, spoken text, style). Used by generate_sounds.py."""
    jobs = []
    for group, rows in (("eva-now", EVA_NOW), ("eva-campaign", EVA_CAMPAIGN)):
        for side in ("eva-union", "eva-vanguard"):
            for _key, f, text, d in rows:
                jobs.append((group, side, f, split_line(text)[1], tts_style(side, text, DELIVERY[d])))
    for kind, rows in (("inf", INFANTRY), ("veh", VEHICLE)):
        for side in ("union", "vanguard"):
            for n in (1, 2):
                ck = f"{side}-{kind}{n}"
                for f, text, when in rows:
                    d = "short and alert" if when == "select" else "briskly confirming an order"
                    jobs.append(("units", ck, f, text, tts_style(ck, text, d)))
    for ck, rows in SPECIAL.items():
        for f, text, _when in rows:
            d = "performing it naturally" if text.startswith("(") else "in character"
            jobs.append(("special", ck, f, split_line(text)[1], tts_style(ck, text, d)))
    return jobs


def main():
    eva_now, eva_camp = len(EVA_NOW), len(EVA_CAMPAIGN)
    inf, veh = len(INFANTRY) * 4, len(VEHICLE) * 4
    special = sum(len(v) for v in SPECIAL.values())
    sfx = sum(len(v) for v in SFX.values())
    L = []
    w = L.append
    w("# Sound and voice prompts (IDEA-31)\n")
    w("Generated by `artsrc/prompts/make_sound_prompts.py`. Edit the script, not this file.\n")
    w("Every sound the mod plays today, with a prompt to make our own version. Voices are made with **Gemini "
      "text-to-speech**; sound effects can't be (see section 5).\n")
    w("## How to use\n")
    w("**Voices (Gemini TTS)**")
    w("1. Open Google AI Studio's speech generation (or use the Gemini API TTS model).")
    w("2. Pick the **Gemini voice** listed for the character and keep it for every line of that character.")
    w("3. Paste the prompt. Generate 2–3 takes and keep the best.")
    w("4. Download the WAV and save it as `assets/sounds/<Save as>` (the folder is given per section).")
    w("5. Later step (not done yet): trim silence, level the volume, add the radio filter to unit lines, "
      "and wire the files into `audio/*.yaml`.\n")
    w("**Sound effects**: paste the prompt into a sound-effect generator (ElevenLabs Sound Effects, Stable Audio "
      "Open), or find a match in a CC0 library (freesound.org filtered to CC0). Save as `assets/sounds/sfx/<file>.wav`.\n")
    w("## Summary\n")
    w("| Group | Files | Tool |")
    w("|-------|-------|------|")
    w(f"| 1. Announcer, used now (× 2 sides) | {eva_now} × 2 = {eva_now * 2} | Gemini TTS |")
    w(f"| 2. Announcer, for our campaign later (× 2 sides) | {eva_camp} × 2 = {eva_camp * 2} | Gemini TTS |")
    w(f"| 3. Infantry and vehicle voices (2 voices per side) | {inf + veh} | Gemini TTS |")
    w(f"| 4. Special unit voices and deaths | {special} | Gemini TTS |")
    w(f"| 6. Sound effects | {sfx} | Sound-effect generator / CC0 library |")
    w(f"| **Total** | **{eva_now * 2 + eva_camp * 2 + inf + veh + special + sfx}** | |\n")
    w("Do group 1 first: it is the biggest audible change and needs only two voices.\n")

    w("## Voice cast\n")
    w("Suggested Gemini prebuilt voices. Audition alternatives freely, but once chosen, keep one voice per character.\n")
    w("| Character | Gemini voice | Character style | Save folder |")
    w("|-----------|--------------|-----------------|-------------|")
    for k, (name, voice, style, folder) in CAST.items():
        w(f"| {name} | {voice} | {style} | `assets/sounds/{folder}/` |")
    w("")

    def eva_section(title, rows, intro):
        w(f"## {title}\n")
        w(intro + "\n")
        for side in ("eva-union", "eva-vanguard"):
            name, voice, _, folder = CAST[side]
            w(f"### {name}: Gemini voice **{voice}**, save to `assets/sounds/{folder}/`\n")
            w("| Save as | Plays when | Prompt |")
            w("|---------|------------|--------|")
            for key, f, text, d in rows:
                w(f"| `{f}.wav` | {key} | {tts_prompt(side, text, DELIVERY[d])} |")
            w("")

    eva_section("1. Announcer (EVA), used now", EVA_NOW,
                "One announcer per side (IDEA-31 decision). Same lines for both sides; the voice gives each side its "
                "character. `HarvesterAttack` is silent today, so `harvatk1` is new.")
    eva_section("2. Announcer (EVA), for our campaign later", EVA_CAMPAIGN,
                "Not played in skirmish. Generic mission lines kept for the Project X campaign (IDEA-18). "
                "Lower priority.")
    w("### Not recorded\n")
    for k, why in EVA_SKIP:
        w(f"- {k}: {why}.")
    w("")

    w("## 3. Infantry and vehicle voices\n")
    w("Each line is recorded by both voices of a side (4 takes per line). The game picks one at random, so a squad "
      "doesn't all sound the same. Select lines play when you click the unit, order lines when you give a command.\n")
    for group, rows, kind in (("Infantry", INFANTRY, "inf"), ("Vehicles", VEHICLE, "veh")):
        for side in ("union", "vanguard"):
            for n in (1, 2):
                ck = f"{side}-{kind}{n}"
                name, voice, _, folder = CAST[ck]
                w(f"### {name}: Gemini voice **{voice}**, save to `assets/sounds/{folder}/`\n")
                w("| Save as | When | Prompt |")
                w("|---------|------|--------|")
                for f, text, when in rows:
                    d = "short and alert" if when == "select" else "briskly confirming an order"
                    w(f"| `{f}.wav` | {when} | {tts_prompt(ck, text, d)} |")
                w("")

    w("## 4. Special unit voices and deaths\n")
    w("Deaths are vocal sounds, not words. Gemini may read the description aloud instead of performing it; if a take "
      "sounds wrong, make that one in the sound-effect tool instead.\n")
    for ck, rows in SPECIAL.items():
        name, voice, _, folder = CAST[ck]
        w(f"### {name}: Gemini voice **{voice}**, save to `assets/sounds/{folder}/`\n")
        w("| Save as | When | Prompt |")
        w("|---------|------|--------|")
        for f, text, when in rows:
            d = "performing it naturally" if text.startswith("(") else "in character"
            w(f"| `{f}.wav` | {when} | {tts_prompt(ck, text, d)} |")
        w("")
    w("### Not recorded\n")
    for k, why in VOICE_SKIP:
        w(f"- {k}: {why}.")
    w("")

    w("## 5. Can Gemini make the sound effects?\n")
    w("No. Gemini's audio models generate **speech** (TTS) and **music** (Lyria), not sound effects. Veo video can "
      "add sound to a clip, but cutting single gunshots out of generated videos is slow and inconsistent. Use one of:\n")
    w("- **ElevenLabs Sound Effects**: text-to-SFX, good quality, commercial use on paid plans.")
    w("- **Stable Audio Open**: runs locally and free (fits the IDEA-24 local-tools plan); check its licence before release.")
    w("- **CC0 libraries** (freesound.org filtered to CC0): no licence worries; good for UI clicks and dog barks.\n")
    w("Generate a few variations of each weapon sound; we can later play them at random so repeated fire sounds less "
      "mechanical.\n")

    w("## 6. Sound effects\n")
    w("Save to `assets/sounds/sfx/`. Aim for 0.2–2 seconds unless the prompt says otherwise, mono, no music.\n")
    for group, rows in SFX.items():
        w(f"### {group}\n")
        w("| Save as | Used by | Prompt |")
        w("|---------|---------|--------|")
        for f, used, p in rows:
            w(f"| `{f}.wav` | {used} | {p}. Isolated sound effect, no music, no voice. |")
        w("")
    w("### Not recorded\n")
    for k, why in SFX_SKIP:
        w(f"- `{k}`: {why}.")
    w("")
    w("### Already ours (no prompt needed)\n")
    w("Weather sounds in `mods/rapx/audio/weather/` (rain, heavy rain, wind, sand, thunder).\n")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
