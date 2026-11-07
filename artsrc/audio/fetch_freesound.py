#!/usr/bin/env python3
"""
Finds and downloads CC0 sound effects from freesound.org for the weapon and world sounds (IDEA-31). No account or
API key: it reads the public search page (filtered to CC0 and a maximum length), checks the licence on each sound's
own page, and saves the site's high-quality MP3 preview to artsrc/audio/sfx/source/fs<id>.mp3.
Candidates are listed in artsrc/audio/sfx/candidates.json; make_world_sounds.py says which one is used.

  python3 artsrc/audio/fetch_freesound.py            # every sound in SEARCHES, 3 candidates each
  python3 artsrc/audio/fetch_freesound.py cannon1 --count 5
"""
import argparse
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SFX = os.path.join(HERE, "sfx")
SRC = os.path.join(SFX, "source")
CAND = os.path.join(SFX, "candidates.json")
UA = {"User-Agent": "Mozilla/5.0 (rapx sound sourcing)"}

# game sound -> (search words, max length in seconds)
SEARCHES = {
    "aacanon3": ("anti aircraft gun", 4),
    "cannon1": ("tank cannon shot", 5),
    "cannon2": ("autocannon", 4),
    "tank5": ("artillery howitzer shot", 6),
    "turret1": ("naval gun", 6),
    "grenade1": ("grenade launcher", 3),
    "missile1": ("missile launch", 5),
    "missile6": ("rocket launch", 4),
    "missile7": ("missile whoosh", 4),
    "torpedo1": ("torpedo launch", 5),
    "h2obomb2": ("depth charge", 6),
    "kaboom1": ("huge explosion", 10),
    "kaboom12": ("explosion medium", 4),
    "kaboom15": ("small explosion", 3),
    "kaboom22": ("large explosion", 6),
    "kaboom25": ("grenade explosion", 4),
    "kaboom30": ("concrete collapse", 5),
    "crmble2": ("concrete debris crumble", 3),
    "sandbag2": ("sandbag impact", 3),
    "mine1": ("landmine explosion", 4),
    "mineblo1": ("big explosion boom", 5),
    "minelay1": ("metal latch clunk", 2),
    "firebl3": ("fireball whoosh", 4),
    "splash9": ("water splash", 3),
    "squishy2": ("squish splat", 2),
    "subshow1": ("submarine surfacing", 6),
    "chute1": ("parachute open", 3),
    "build5": ("construction machinery", 6),
    "placbldg": ("heavy metal thud", 2),
    "cashturn": ("cash register", 3),
    "fixit1": ("ratchet wrench", 3),
    "tesla1": ("electric zap", 3),
    "tslachg2": ("electric charge up", 4),
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def search(words, max_len, count):
    f = f'license:"Creative Commons 0" duration:[0 TO {max_len}]'
    url = "https://freesound.org/search/?" + urllib.parse.urlencode(
        {"q": words, "f": f, "s": "Downloads (most first)"})
    page = get(url).decode("utf-8", "replace")
    out = []
    # each result: preview link, then its page link (user, id, title) and duration
    for m in re.finditer(r'data-mp3="(https://cdn\.freesound\.org/previews/\d+/(\d+)_\d+-lq\.mp3)"', page):
        sid = m.group(2)
        if any(c["id"] == sid for c in out):
            continue
        tail = page[m.end():m.end() + 6000]
        who = re.search(r'href="/people/([^/]+)/sounds/' + sid + r'/"[^>]*title="([^"]*)"', page)
        dur = re.search(r'data-duration="([\d.]+)"', tail)
        if not who:
            continue
        out.append({"id": sid, "user": urllib.parse.unquote(who.group(1)), "title": html.unescape(who.group(2)),
                    "duration": round(float(dur.group(1)), 2) if dur else None,
                    "preview": m.group(1).replace("-lq.mp3", "-hq.mp3")})
        if len(out) >= count:
            break
    return out


def licence_ok(c):
    page = get(f"https://freesound.org/people/{urllib.parse.quote(c['user'])}/sounds/{c['id']}/").decode(
        "utf-8", "replace")
    lic = re.search(r'creativecommons\.org/(publicdomain/zero|licenses/[a-z-]+)/[\d.]+', page)
    return bool(lic and lic.group(1) == "publicdomain/zero")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="game sounds to fetch (default: all)")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--query", help="override the search words (with one name)")
    ap.add_argument("--max", type=float, help="override the maximum length in seconds")
    args = ap.parse_args()

    os.makedirs(SRC, exist_ok=True)
    cand = json.load(open(CAND)) if os.path.exists(CAND) else {}
    for name in args.names or SEARCHES:
        words, max_len = SEARCHES[name]
        words = args.query or words
        max_len = args.max or max_len
        found = []
        for c in search(words, max_len, args.count * 2):
            if len(found) >= args.count:
                break
            if not licence_ok(c):
                print(f"  skip {c['id']}: not CC0 on its page")
                continue
            path = os.path.join(SRC, f"fs{c['id']}.mp3")
            if not os.path.exists(path):
                with open(path, "wb") as fh:
                    fh.write(get(c["preview"]))
            found.append(c)
            time.sleep(0.5)
        cand[name] = {"query": words, "candidates": found}
        print(f"{name:9} \"{words}\": " + " | ".join(f"fs{c['id']} {c['title'][:30]} ({c['duration']}s)"
                                                     for c in found))
        json.dump(cand, open(CAND, "w"), indent=1)


if __name__ == "__main__":
    main()
