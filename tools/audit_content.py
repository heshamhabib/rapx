#!/usr/bin/env python3
"""
Lists every sprite and terrain file the mod still takes from the original Red Alert download (IDEA-31).

Copies mods/rapx (without movies/ and maps/) to a temporary mod `rapxaudit` whose `content` folder points nowhere
and whose content packages are all optional, then runs `OpenRA.Utility rapxaudit --check-missing-sprites`.
Every "not found" is a file still taken from the original game.

  python3 tools/audit_content.py            # summary: counts per area and the sprite list
  python3 tools/audit_content.py --full     # also every terrain tile
"""
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGINE = os.path.join(ROOT, "engine")


def run_audit():
    tmp = tempfile.mkdtemp(prefix="rapxaudit-")
    mod = os.path.join(tmp, "rapxaudit")
    shutil.copytree(os.path.join(ROOT, "mods", "rapx"), mod, ignore=shutil.ignore_patterns("movies", "maps"))
    os.makedirs(os.path.join(mod, "maps"))
    path = os.path.join(mod, "mod.yaml")
    s = open(path).read()
    s = s.replace("$rapx: ra", "$rapxaudit: ra")
    s = re.sub(r"~\^SupportDir\|Content/ra/v2/: content", "~^SupportDir|NoSuchContent/: content", s)
    s = re.sub(r"^(\t\t)content\|", r"\1~content|", s, flags=re.M)
    open(path, "w").write(s)
    env = dict(os.environ, MOD_SEARCH_PATHS=f"{tmp},../mods,./mods", ENGINE_DIR="..",
               PATH=os.path.expanduser("~/.dotnet") + ":" + os.environ["PATH"],
               DOTNET_ROOT=os.path.expanduser("~/.dotnet"))
    out = subprocess.run(["dotnet", "bin/OpenRA.Utility.dll", "rapxaudit", "--check-missing-sprites"],
                         cwd=ENGINE, env=env, capture_output=True, text=True).stdout
    shutil.rmtree(tmp)
    return out


def sequence_at(ref, lineno):
    """`image.sequence` that the given line of a sequences file belongs to."""
    path = os.path.join(ROOT, "mods", "rapx", ref.split("|", 1)[1])
    image = seq = "?"
    for i, line in enumerate(open(path).read().split("\n")[:lineno], 1):
        if re.match(r"^[^\s#][^:]*:", line):
            image, seq = line.split(":")[0], "?"
        m = re.match(r"^\t([\w-]+):", line)
        if m:
            seq = m.group(1)
    return f"{image}.{seq}"


def main():
    out = run_audit()
    tiles = collections.defaultdict(set)
    sprites = collections.defaultdict(set)
    tileset = None
    for line in out.splitlines():
        m = re.match(r"Tileset: (\w+)", line)
        if m:
            tileset = m.group(1)
            continue
        m = re.search(r"references sprite `([^`]+)`", line)
        if m:
            tiles[tileset].add(m.group(1))
            continue
        m = re.search(r"(\S+\.yaml):(\d+): (\S+) not found", line)
        if m:
            sprites[m.group(1)].add(f"{m.group(3)} ({sequence_at(m.group(1), int(m.group(2)))})")
    print("Terrain tiles still original:")
    for ts in sorted(tiles):
        print(f"  {ts:9} {len(tiles[ts])}" + ("  " + " ".join(sorted(tiles[ts])) if "--full" in sys.argv else ""))
    total = len({x.split()[0] for v in sprites.values() for x in v})
    print(f"Sprites still original: {total}")
    for f in sorted(sprites):
        print(f"  {f}:")
        for x in sorted(sprites[f]):
            print(f"    {x}")


if __name__ == "__main__":
    main()
