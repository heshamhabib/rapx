#!/usr/bin/env python3
"""
Downloads the Sketchfab models picked for the remaining units (glTF .zip, the format make_sketchfab.py
imports) into assets/inbox/new_3d_models_2/, plus a credits list for mods/rapx/CREDITS.

  python3 tools/download_sketchfab.py              download everything not downloaded yet
  python3 tools/download_sketchfab.py --dry-run    only check that each model is still downloadable and its licence
  python3 tools/download_sketchfab.py 2tnk jet.f16 only these units
  python3 tools/download_sketchfab.py --extras     also the optional parts (Tesla coil, Terror Drone)
  python3 tools/download_sketchfab.py --carriers   the US carrier era ladder (IDEA-08 2a) into assets/inbox/carriers/
  python3 tools/download_sketchfab.py --cruisers   cruiser candidates into assets/inbox/cruisers/
  python3 tools/download_sketchfab.py --nation-carriers   carriers for the other nations into assets/inbox/carriers-nations/
  python3 tools/download_sketchfab.py --launchers  national rocket-launcher chassis (IDEA-17) into assets/inbox/launchers/
  python3 tools/download_sketchfab.py --airdef     air-defence tiers 2-4 (IDEA-26 B2) into assets/inbox/airdef/
  python3 tools/download_sketchfab.py --missiles   real missile models (fired sprites and jet stores) into assets/inbox/missiles/
  python3 tools/download_sketchfab.py --ironward   city buildings for the Ironward painted map into assets/inbox/ironward-buildings/

Sketchfab only hands out downloads to a logged-in account: put your API token (sketchfab.com -> Settings ->
Password & API -> API Token) in ~/.sketchfab_token or the SKETCHFAB_TOKEN environment variable.

Every model's licence is checked before downloading: ones that no longer allow derivative works (the sprites
are derivatives) or are no longer downloadable are skipped. Writes <out dir>/credits.md with the credit lines.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "assets", "inbox", "new_3d_models_2")
API = "https://api.sketchfab.com/v3/models/"

# (unit id, unit name, Sketchfab uid)
MODELS = [
    # Ground vehicles
    ("1tnk", "Light Tank", "bc61470bf6f34716a223f45a6b9e8df1"),          # M551 Sheridan
    ("2tnk", "Medium Tank", "1529f5d842cb4f578aa8cb672524f044"),         # M1A1 Abrams
    ("jeep", "Ranger", "b635f6d5a7a045cf9bae3cc71952cd23"),              # Willy Jeep
    ("arty", "Artillery", "7bc24252d4b84ac5bb7fd3b67f119b0a"),           # M109A6 Paladin
    ("ftrk", "Flak Truck", "c12fc87214fc44fa9613498a65de1bb9"),          # IFV vehicle Red Alert 2
    ("truk", "Supply Truck", "f953c51a5dbc4a15949f4dcc0905c4e8"),        # Ural 4320
    ("dtrk", "Demolition Truck", "4ae573e2fb084f63bd63a2bb44852c68"),    # Gaz 66
    ("harv", "Ore Truck", "dZM64cBYmcGvXfIPfctL7VYthzj"),                # Caterpillar 797F Mining Truck
    ("mnly", "Minelayer", "7fe132c071584049b51d3569726021a0"),           # M113
    ("mrj", "Radar Jammer", "1ad95e5724624a3bba7d36a686817efc"),         # Renault TRM Radar Truck
    ("mgg", "Mobile Gap Generator", "7605ca0df95544b9a0584e1f91413703"), # fire control radar vehicle
    ("ctnk", "Chrono Tank", "eafb340ee30b41f89c793b73475edd1d"),         # "Cobra" futuristic tank concept
    ("stnk", "Phase Transport", "b7fbbcf93a2e4631b89de82f1ae63ef6"),     # Stealth tank
    ("ptnk", "Prism Tank", "26751eca0c61489ca0b545df03741fea"),          # Prism Tank
    ("ttnk", "Tesla Tank (hull, with the ttnk-coil on top)", "c61279bad4ca4502bcc8e584b558d10e"),  # T-62A
    ("qtnk", "MAD Tank", "ba8b84d78c0a42038cf2eaa4210ef296"),            # KV-2 heavy tank 1940 (comrade1280)
    ("mcv.union", "Construction Vehicle (Union)", "d1761adbbf534f13bc6519ecae231acb"),     # Oshkosh M1070 HET
    ("mcv.vanguard", "Construction Vehicle (Vanguard)", "317c5dbcad974d9f99efd079060d4344"),  # Ural KS3574 crane
    ("ftrk.pantsir", "Flak Truck", "8be7dcff46794b809560e2377561546e"),            # 96K6 Pantsir-S1 (ALI1388)
    ("harv.komatsu", "Ore Truck", "2bf4dcd62e484f01bcb446af263bd65c"),             # Komatsu HD-465-7EO
    ("ptnk.cyber", "Prism Tank", "8882ab6534e14ce6b09ed9cd65206290"),              # Cyber Tank (kraytay)
    # Humanoid robots (IDEA-29), bodies for the 3D soldier pipeline (artsrc/units/soldiers/prep_sketchfab.py)
    ("robot.cybt", "Cyborg Trooper", "890f5493c9c041c0a0923fc23b01d086"),         # Cyborg Soldier SciFi (3dUVpro)
    ("robot.bdrd", "Battle Droid", "e4caf58f757d4a688e7abe8ef64e3b3a"),           # VX-09 Sentinel pack (another unit)
    ("robot.rgun", "Railgun Robot", "e4caf58f757d4a688e7abe8ef64e3b3a"),          # VX-09 Sentinel (DevPoly3D)
    ("robot.irgd", "Iron Guard", "de876bfdce1c47a4aa67670faee7208e"),             # Sci-Fi Soldier (evgenytvidov)
    ("robot.taut", "Tesla Automaton", "3f18e4e7b6c643c4b7763febf1361ee4"),        # Heavy robot (Scarecrow_original)
    # Ships
    ("ss", "Submarine", "b5c0eae394c94e0caa91fa511bae4ca6"),             # U-85 Type VIIB U-boat
    ("msub", "Missile Submarine", "c9adff3a72d7462f8f82a35459a582d2"),   # Ohio class SSBN
    ("dd", "Destroyer", "17be09c31c6047e4a5969b68c29eba03"),             # USS Arleigh Burke
    # ca: no cruiser yet ("BB-61 Iowa New Year Mode" ad1f1a06... is a ship-girl; CLAA Uranus c9f29e4e... looks
    # ripped from a warship game: its materials are named like game assets, am433_...)
    ("pt", "Gunboat", "ca6b98e1100e4c81adefdc36d1f5af19"),               # Type 22 Houbei
    ("lst", "Transport", "14ad629070db445eaf2364eda019192f"),            # LCAC hovercraft
    # Aircraft
    ("yak", "Yak Attack Plane", "a0e72d7a03fe423d9e85db646745cbea"),     # Yak-9
    ("u2", "Spy Plane", "29d8eb26c0fa47f3967de8b0334ef20e"),             # U-2C, Duxford scan
    ("jet.f104", "F-104", "96e60f2f463b4b1c8822079f1b2e21eb"),
    ("jet.f4", "F-4", "1ea38a66a59048529d27b24a570c5e07"),
    ("jet.f16", "F-16", "ea8edb08d79e4eafa9c794c581f88cf3"),
    ("jet.f117", "F-117", "037698ed02624d45b5ba5cd774d54b68"),
    ("jet.sr71", "SR-71", "e2400e6119f5414c89e075654a82d30a"),
    ("jet.b52", "B-52", "ec3485da9ec3462aab91863edd707afa"),             # Duxford scan
    ("jet.b2", "B-2", "06464acbeca94381893c037b6dfa3d12"),
    ("jet.yf23", "YF-23", "53936b1d83b74e6a8598f793fabe7119"),
    ("jet.v22", "V-22", "cf00a682505f479a903e9600cce051f7"),
    ("jet.harrier", "Harrier", "8482e199f18b44f3bede5a5806aa1cb1"),
    ("jet.m2000", "Mirage 2000", "3894c147f6474d5eb6308b8d2724a914"),
    ("jet.rafale", "Rafale", "fabb8472bc2e413282c80406b13ff1a7"),
    ("jet.typhoon", "Typhoon", "5650572af6c14dc09e1fd77d98724a1a"),      # scan
    ("jet.vulcan", "Vulcan", "accfa2763c574b4991d4d6234a318b2b"),        # scan
    ("jet.seavixen", "Sea Vixen", "a0a22b0f53d04a20b5e04cb94af9349a"),   # scan
    ("jet.mig3", "MiG-3", "6ba63e06628e491a9836e4a9c54c50f1"),
    ("jet.mig21", "MiG-21", "18927e007c3b47ed9e676f88b4adb578"),
    ("jet.mig23", "MiG-23", "7a13c91f07e042a685b4d265644fdc06"),
    ("jet.mig25", "MiG-25", "afe67617c5294dce9056106a22f640ff"),
    ("jet.su25", "Su-25", "956d0cb0bbe54fa8ad72e8c3e224fd2d"),
    ("jet.su27", "Su-27", "4b73e72471b440be949b5cbc3ca36184"),
    ("jet.su47", "Su-47", "87373815a47841b8999666c477a7190a"),
    ("jet.tu160", "Tu-160", "a6d878f3e2a24c9a89078d082f8d70db"),
    ("jet.l39", "L-39", "8e9bd5454ca848b699356a7a06559216"),
    ("jet.an225", "An-225", "1b315978f1f74759814786db7c8ae893"),
    ("jet.j20", "J-20", "b9e81062c94545ffb0232d3ac6b7adc5"),
    ("jet.saeqeh", "Saeqeh", "cdf665a536b34879b3b56026ce4ae962"),        # F-5E Tiger II scan
    ("jet.grom", "Grom", "c1f0bfab4e924753994a8d953aad2621"),            # Stealth drone concept
]
EXTRAS = [
    ("ttnk-coil", "Tesla Tank (coil to put on a hull)", "deffdea10a0b4742bae2d6d16a743c67"),
    ("sdrn", "Spider Drone (needs a walk animation)", "de36bf7c69b64f4c9d6dfef1d2ac2ef7"),
]

# US Navy carriers, one per era (docs/DESIGN-IDEAS.md IDEA-08 2a). Not used: lxyun_2's models (USS Hornet CV-8 and
# others) and shangus930's USS Midway: their material names (am448_..., cm056_...) are a warship game's asset names,
# and lxyun_2's catalogue is World of Warships ships, so they are most likely ripped despite the CC-BY label.
CARRIERS = [
    # kriss50's USS Essex (CV-9) a0e0ed78... is out too: kriss50's Salem has the same game asset names
    ("cv.essex2", "Fleet Carrier", "92033a1dcd9f417797997871e6d1c2ea"),      # Essex-Class Aircraft Carrier, Spark_Customs
    ("cv.enterprise", "Battle Carrier", "f1b46fa2de8f409cbbe693f7f10dc3b8"), # USS Enterprise CVN-65, MirzaArrafiERV_45
    ("cv.nimitz", "Supercarrier", "06cf0dba66874934a105b3fe2bfdb0f7"),       # USS Nimitz CVN-68, MirzaArrafiERV_45
    ("cv.ford2", "Future Carrier", "562bf516e1494df38d8f222504dc798b"),      # Gerald R Ford, waelXcm
    ("cv.ford", "Future Carrier (spare)", "abefde1453ae4d78bd9bea70e80bb1b0"),  # USS Gerald R. Ford, veron66
    ("cv.kittyhawk", "Kitty Hawk (photo scan, rough)", "d34dc09652bb482eb93c718d459c984a"),  # juanbrualla
]
# Cruiser (CA) candidates
CRUISERS = [
    ("ca.cleveland", "Cruiser", "6267ab80b28745a68d6d1357e1e0543a"),         # USS Cleveland (CL-55), bsterling
    ("ca.salem", "Cruiser", "7f02805238234dd18ce30b0212032144"),             # USS Salem (CA-139), kriss50
    ("ca.ticonderoga", "Cruiser", "397bd2b7bcd946e4b508869f4ca1e1cf"),       # Ticonderoga missile cruiser, waelXcm
]
# National carrier candidates (one per nation that has carriers in real life; near matches where no model exists)
NATION_CARRIERS = [
    ("cv.england.qe", "HMS Queen Elizabeth", "b7394547685749ae9e1c48afe29586ab"),     # MirzaArrafiERV_45
    ("cv.france.cdg", "Charles de Gaulle", "4ed9674d1adf406bb1b358dd4a8c93a1"),      # MirzaArrafiERV_45
    ("cv.japan.kaga", "JS Kaga", "91cd810a0ade403590193e22a2aadd56"),                 # hrd4588 (vet: game names?)
    ("cv.japan.izumo", "JS Izumo", "a4f51fe27b684cceaf2ceebefc2ffa66"),               # hrd4588 (vet)
    ("cv.lha.tarawa", "USS Tarawa LHA-1", "0d1692199c2847b3a8eae40e285d4ea1"),        # MirzaArrafiERV_45
    ("cv.lhd.wasp", "USS Wasp LHD-1", "bf391bb56fbf44c4a924cb6a5bd8bf81"),            # MirzaArrafiERV_45
    ("cv.egypt.mistral", "Mistral class", "200f78ee68b44788833f097b88d5aad3"),        # MirzaArrafiERV_45
    ("cv.soviet.kiev", "Kiev class", "f854eda1eab54a40aae8628e6456ae78"),             # MirzaArrafiERV_45
    ("cv.soviet.moskva", "Moskva class", "535adcf1560245e48e93b3759f0237ae"),         # MirzaArrafiERV_45
    ("cv.russia.kuznetsov", "Admiral Kuznetsov (prop)", "825917092d784fc285bc6c31d2b6e7d8"),  # mansoorsajidp
    ("cv.china.generic", "Chinese Aircraft Carrier", "f9ddadfc6988414fa15da2cb1b1de545"),  # businessyuen
    ("cv.china.type004", "Type-004", "0953bebe3ae34d7582fe0e2bcff0925f"),             # MirzaArrafiERV_45
    ("cv.india.vikrant", "INS Vikrant", "7fc21f7a6d6e4fc5ade592f5f4eec0a0"),          # Chenzoss
    ("cv.turkey.anadolu", "TCG Anadolu", "90c0f1a1e2ae42e89d96d8ed84862ac5"),         # ammar_ssr
    ("cv.turkey.anadolu2", "TCG Anadolu (low poly)", "03fd769c194d4349b77a19729dd51703"),  # Kellot
    ("cv.iran.container", "Container Ship", "4f7cf10593824061bfe2e36ffd823cde"),     # lavawave (Shahid Bagheri stand-in)
]

# IDEA-17 national rocket launchers: one shared chassis model per silhouette, national paint in the game
LAUNCHERS = [
    ("rl.light", "HIMAX (light 6x6)", "95d255cd685e4cc5afc35ba5f58679d4"),        # Ukrainian M142 HIMARS (42manako)
    ("rl.tracked", "Tracked MLRS", "fc879301999a4cd0a09721b51affba9b"),           # Free M270 (DaHoon)
    ("rl.heavy", "Heavy 8x8 launcher", "536cf77932ae4784ad5ad1d69937eaa2"),       # BM-27 Uragan (javanilga)
    ("rl.medium", "Medium 6x6 launcher", "c90559a30e6a414d993a0d3bdf6c5ff8"),     # BM-21 Grad (Hsu.Pei.Ge)
    ("rl.tank", "TOZ-1 Sunflare", "255fba6ba6c44b97aaea91d0225d0c75"),           # TOS-1 Buratino (lm9241221)
    ("rl.canister", "Type-12 Sea Arrow", "f808eb27a4af42309ec6b71343b871a6"),     # 3K60 Bal-E (42manako)
]

# IDEA-26 B2 generic air-defence tiers 2-4: one Allied and one Soviet look per tier (national systems come in B4)
AIRDEF = [
    ("msam.allies", "Medium SAM (Allies)", "3cd0c368823c420c9a2c5d7c49cdd5e6"),   # US NASAMS 3 TEL (KojfDiscord)
    ("msam.soviet", "Medium SAM (Soviets)", "7663f9fca2ce485da8c0fafcf2d40d10"),  # BUK Missile System (azlan)
    ("lsam.allies", "Long-range SAM (Allies)", "7a64d0af78514a159877edab1ab2bccb"),  # MIM-104 Patriot (MirzaArrafi)
    ("lsam.soviet", "Long-range SAM (Soviets)", "3458009aa5df425f9bd3e1651709d54d"),  # S-400 (sami1230)
    ("bmd.allies", "Missile Shield (Allies)", "4ab96bf250e64f3c92c74feb835dd4a9"),  # THAAD (Chenzoss)
    ("bmd.soviet", "Missile Shield (Soviets)", "246c635701c0421ca02e67202a6494e9"),  # Chinese HQ-9 (42manako), S-500 stand-in
]

# Real missiles and bombs (artsrc/jets/ordnance.py REAL): the fired sprites and the stores hung on jets. The R-27T came
# from the user (assets/inbox/su_r-27t_air-to-air_missiles_war_thunder.zip).
MISSILES = [
    ("aim9", "AIM-9 Sidewinder", "caaf15b49bac4144b6c6be577c2b872a"),        # rickslash
    ("aim120", "AIM-120C AMRAAM", "838fa923340a4d108e05c99bf0146ff6"),       # Jeyhun1985
    ("aim54", "AIM-54 Phoenix", "0f93756f393d498f95c4364244f8bda0"),         # MustafaGarip
    ("r73", "R-73", "00e9be4be4d447a7963eae1fa4ab5cb9"),                     # jokesforboats
    ("r77", "R-77", "0da27c5b53f24542843a4a423c59b96a"),                     # MustafaGarip
    ("agm65", "AGM-65 Maverick", "a4336b95b8364dd78a52b8426598f789"),        # xFORTUNAx
    ("kh29", "Kh-29T", "d13c7039142d46b5b61baef9db11fa80"),                  # xFORTUNAx
    ("gbu", "GBU-12 Paveway II", "e25425b8a86a439bb7890536fcfc3fb1"),        # KojfDiscord
    ("s8", "S-8KOM rocket", "06f720ad261041719210e60de6a94dd7"),             # xFORTUNAx
    ("tomahawk", "BGM-109 Tomahawk", "da71eb1c023b444aba15ff37710e9613"),    # rickslash
]


# City buildings for the Ironward painted map (artsrc/maps/ironward/build_backdrop.py): placed into the house lots of the
# Blender scene. The user's own pick, the Longworth Building (assets/inbox/longworth_building_low_poly_game_ready.zip,
# Ruslan Malovsky, CC-BY-4.0), is used too.
IRONWARD = [
    ("row", "Chicago row buildings", "c4a3993ef1e84e6d9d5a15c78da88aae"),           # 99.Miles
    ("brownstone", "Brownstone set", "b15e6344acd844eabc823e1cc8332574"),           # Daniel Zhabotinsky
    ("industrial", "Old industrial building", "0dafa7aaadfd4666bb4a32776c84b14e"),  # Hrvoje Wächter
    ("block", "City block 5", "73b1d5fc97ca46bab7f80b7c95001e79"),                  # ModelMaker
    ("midrise", "Mid-rise building", "dc4f6a49d8a7462b9349936b8dc7256e"),           # ModelMaker
    ("newyork", "New York buildings", "98faceefdc154d60a2b8617ca5e182e7"),          # 99.Miles
    ("brick", "Old American brick building", "3170993b67ee4e58b27d69d5877f71bd"),   # Orzechu
    ("artdeco", "Art deco tower", "80898b00703f4fbd9a0622c90193032a"),              # Oneironauticus
    ("hotel", "Old hotel", "06b7d0bc033f4a35b1036243cadc2a9e"),                     # SebastianSosnowski
    ("factory", "Abandoned factory", "5df9f2662a824117b1e6c5597b29b33f"),           # Klasy
    ("oldbuilding", "Old building", "ce2281fd0dc84a748b143c8de6004fc0"),            # BumpkinCZ
    ("cityblock", "School block under construction", "5c8aee93ca77449eb85ec439ea1d6dae"),  # Hubert Małyszek
    ("deco", "Art deco building", "88067844b13b4bc0b7234aab9f70713d"),              # Wobbs_
    ("brownstone2", "Brownstone set 2", "43548bdec0b84e62986e9f1df181ee32"),        # Dakta.Grower.Nzl
    ("nyc", "NYC low poly building", "3f6d0db9954746d38d398c759e53524c"),           # AdarshMPro
    ("apartment", "Apartment block", "58c2196f53fd48afbd4228521dc39b04"),           # Kerem Biçer
    ("cathedral", "Gothic cathedral", "9192b34b2136494aaf519b032a6ad1da"),          # SenyorEtziba
    ("clocktower", "Gothic clock tower", "aeb85300d0734071966c379d0c173527"),       # Darknest
]


def token():
    t = os.environ.get("SKETCHFAB_TOKEN")
    path = os.path.expanduser("~/.sketchfab_token")
    if not t and os.path.exists(path):
        t = open(path).read().strip()
    return t


def get_json(url, auth=None):
    req = urllib.request.Request(url, headers={"Authorization": f"Token {auth}"} if auth else {})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited
                time.sleep(30 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"rate limited: {url}")


def download(url, path):
    tmp = path + ".part"
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        total, done = int(r.headers.get("Content-Length", 0)), 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    os.replace(tmp, path)
    print()


def slug(name):
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")[:60]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    global OUT
    models = MODELS + (EXTRAS if "--extras" in sys.argv else [])
    if "--carriers" in sys.argv:
        models, OUT = CARRIERS, os.path.join(ROOT, "assets", "inbox", "carriers")
    if "--nation-carriers" in sys.argv:
        models, OUT = NATION_CARRIERS, os.path.join(ROOT, "assets", "inbox", "carriers-nations")
    if "--missiles" in sys.argv:
        models, OUT = MISSILES, os.path.join(ROOT, "assets", "inbox", "missiles")
    if "--airdef" in sys.argv:
        models, OUT = AIRDEF, os.path.join(ROOT, "assets", "inbox", "airdef")
    if "--launchers" in sys.argv:
        models, OUT = LAUNCHERS, os.path.join(ROOT, "assets", "inbox", "launchers")
    if "--ironward" in sys.argv:
        models, OUT = IRONWARD, os.path.join(ROOT, "assets", "inbox", "ironward-buildings")
    if "--cruisers" in sys.argv:
        models, OUT = CRUISERS, os.path.join(ROOT, "assets", "inbox", "cruisers")
    if args:
        models = [m for m in models if m[0] in args]
    auth = token()
    if not dry and not auth:
        sys.exit("No Sketchfab API token: put it in ~/.sketchfab_token or SKETCHFAB_TOKEN (see the top of this script)")
    os.makedirs(OUT, exist_ok=True)
    credits, skipped = [], []
    for unit, unit_name, uid in models:
        info = get_json(API + uid)
        lic = (info.get("license") or {}).get("label", "?")
        name, author = info["name"], info["user"]["displayName"]
        page = info.get("viewerUrl", f"https://sketchfab.com/models/{uid}")
        print(f"{unit:13s} {name[:45]:45s} {lic}")
        if "NoDeriv" in lic or not info.get("isDownloadable"):
            skipped.append(f"{unit}: {name} ({'no derivatives' if 'NoDeriv' in lic else 'not downloadable'})")
            continue
        credits.append(f'* {unit_name} ({unit.upper()}):\n    "{name}" ({page})\n    by {author}, licensed under {lic}.')
        path = os.path.join(OUT, f"{unit}__{slug(name)}.zip")
        if dry or os.path.exists(path):
            continue
        links = get_json(API + uid + "/download", auth)
        if "gltf" not in links:
            skipped.append(f"{unit}: {name} (no glTF download offered)")
            continue
        download(links["gltf"]["url"], path)
        time.sleep(2)  # be gentle with the API
    with open(os.path.join(OUT, "credits.md"), "w") as f:
        f.write("\n\n".join(credits) + "\n")
    print(f"\n{len(credits)} models{' checked' if dry else ' in ' + OUT}; credits in credits.md")
    for s in skipped:
        print("  skipped", s)


if __name__ == "__main__":
    main()
