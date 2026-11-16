#!/usr/bin/env python3
"""Prints an .oramap's map UID the way the engine computes it (Map.ComputeUID: SHA1 of the package's .yaml, .bin and
.lua files, plus map.png from MapFormat 12, in package order). Test scripts use it instead of a hard-coded UID, which
goes stale whenever the map is edited.

  python3 tools/map_uid.py mods/rapx/maps/agenda.oramap
"""
import hashlib
import re
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
fmt = int(re.search(r"MapFormat:\s*(\d+)", z.read("map.yaml").decode("utf-8", "ignore")).group(1))
h = hashlib.sha1()
for name in z.namelist():
    if name.endswith((".yaml", ".bin", ".lua")) or (fmt >= 12 and name == "map.png"):
        h.update(z.read(name))
print(h.hexdigest())
