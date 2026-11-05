#!/usr/bin/env python3
"""
Extracts central Berlin from the OpenStreetMap Berlin extract (Geofabrik) into a small JSON file in local metres,
for the IDEA-28 painted-map pilot (build_scene.py turns it into a Blender scene).

  python3 artsrc/maps/berlin/extract_osm.py

Input:  artsrc/maps/berlin/osm/berlin-latest.osm.pbf  (https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf)
Output: artsrc/maps/berlin/berlin_osm.json
Data © OpenStreetMap contributors, ODbL (https://www.openstreetmap.org/copyright).

Area: Victory Column (west) to the TV Tower (east), Reichstag/Spree (north) to Potsdamer Platz/Leipziger Str. (south):
about 4.95 x 2.78 km = a 128 x 72 cell map at ~38.7 m per cell.
"""
import json
import math
import os

import osmium

HERE = os.path.dirname(os.path.abspath(__file__))
PBF = os.path.join(HERE, "osm", "berlin-latest.osm.pbf")
OUT = os.path.join(HERE, "berlin_osm.json")

# Bounding box (lon/lat)
WEST, EAST = 13.343, 13.416
SOUTH, NORTH = 52.503, 52.528
LAT0 = (SOUTH + NORTH) / 2
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))
WIDTH_M = (EAST - WEST) * M_PER_DEG_LON
HEIGHT_M = (NORTH - SOUTH) * M_PER_DEG_LAT

ROAD_WIDTH = {  # metres, drawn on the ground mask
    "motorway": 24, "trunk": 24, "primary": 22, "secondary": 17, "tertiary": 13,
    "unclassified": 9, "residential": 9, "living_street": 7, "pedestrian": 10, "service": 5,
    "footway": 3, "path": 3, "cycleway": 3, "track": 3,
}
GREEN = {"park", "garden", "grass", "meadow", "recreation_ground", "village_green", "cemetery", "playground"}
FOREST = {"forest", "wood"}
PAVED = {"square", "parking", "marketplace"}

# Landmarks (lon, lat): drawn as hand-built models, so the OSM buildings under them are left out
LANDMARKS = {
    "brandenburg_gate": (13.37770, 52.51628, 45),
    "reichstag": (13.37612, 52.51862, 85),
    "tv_tower": (13.40939, 52.52081, 30),
    "victory_column": (13.35010, 52.51451, 25),
}


def xy(lon, lat):
    return round((lon - WEST) * M_PER_DEG_LON, 2), round((lat - SOUTH) * M_PER_DEG_LAT, 2)


def inside(lon, lat, margin=0.002):
    return WEST - margin <= lon <= EAST + margin and SOUTH - margin <= lat <= NORTH + margin


def height_of(tags):
    for key in ("height", "building:height"):
        v = tags.get(key)
        if v:
            try:
                return float(v.split()[0].replace(",", "."))
            except ValueError:
                pass
    lv = tags.get("building:levels")
    if lv:
        try:
            return float(lv.split(";")[0].replace(",", ".")) * 3.3 + 2
        except ValueError:
            pass
    return None


class Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.buildings, self.water, self.green, self.forest, self.paved = [], [], [], [], []
        self.roads, self.rails, self.waterways = [], [], []

    def rings(self, a):
        out = []
        for outer in a.outer_rings():
            pts = [(n.lon, n.lat) for n in outer]
            if not any(inside(lo, la) for lo, la in pts):
                continue
            holes = [[xy(n.lon, n.lat) for n in inner] for inner in a.inner_rings(outer)]
            out.append({"outer": [xy(lo, la) for lo, la in pts], "holes": holes})
        return out

    def area(self, a):
        t = a.tags
        try:
            if "building" in t and t.get("building") != "no":
                h = height_of(t)
                for r in self.rings(a):
                    r["h"] = h
                    r["kind"] = t.get("building")
                    r["roof"] = t.get("roof:colour") or t.get("roof:material")
                    self.buildings.append(r)
            elif t.get("natural") == "water" or t.get("waterway") in ("riverbank", "canal", "dock") or t.get("landuse") == "basin":
                self.water.extend(self.rings(a))
            elif t.get("natural") in FOREST or t.get("landuse") in FOREST:
                self.forest.extend(self.rings(a))
            elif t.get("leisure") in GREEN or t.get("landuse") in GREEN:
                self.green.extend(self.rings(a))
            elif t.get("place") in PAVED or t.get("amenity") in PAVED or t.get("highway") == "pedestrian":
                self.paved.extend(self.rings(a))
        except osmium.InvalidLocationError:
            pass

    def way(self, w):
        t = w.tags
        hw = t.get("highway")
        rw = t.get("railway")
        ww = t.get("waterway")
        if not (hw in ROAD_WIDTH or rw in ("rail", "light_rail", "subway", "tram") or ww in ("river", "canal")):
            return
        try:
            pts = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if not any(inside(lo, la) for lo, la in pts):
            return
        line = [xy(lo, la) for lo, la in pts]
        if hw in ROAD_WIDTH:
            self.roads.append({"pts": line, "w": ROAD_WIDTH[hw], "kind": hw,
                               "bridge": t.get("bridge") == "yes", "tunnel": t.get("tunnel") in ("yes", "building_passage"),
                               "layer": t.get("layer")})
        elif rw:
            # Underground lines don't show
            if t.get("tunnel") == "yes" or rw == "subway":
                return
            self.rails.append({"pts": line, "kind": rw, "bridge": t.get("bridge") == "yes"})
        else:
            self.waterways.append({"pts": line, "kind": ww})


def main():
    h = Handler()
    h.apply_file(PBF, locations=True, idx="flex_mem")
    landmarks = {k: {"x": xy(lo, la)[0], "y": xy(lo, la)[1], "clear_radius": r} for k, (lo, la, r) in LANDMARKS.items()}
    data = {
        "bbox": {"west": WEST, "east": EAST, "south": SOUTH, "north": NORTH},
        "size_m": [round(WIDTH_M, 1), round(HEIGHT_M, 1)],
        "attribution": "Data (c) OpenStreetMap contributors, ODbL",
        "landmarks": landmarks,
        "buildings": h.buildings, "water": h.water, "green": h.green, "forest": h.forest, "paved": h.paved,
        "roads": h.roads, "rails": h.rails, "waterways": h.waterways,
    }
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{OUT}: {WIDTH_M:.0f} x {HEIGHT_M:.0f} m; buildings {len(h.buildings)}, water {len(h.water)}, "
          f"green {len(h.green)}, forest {len(h.forest)}, paved {len(h.paved)}, roads {len(h.roads)}, "
          f"rails {len(h.rails)}, waterways {len(h.waterways)}; "
          f"{sum(1 for b in h.buildings if b['h']) } buildings with a height")


if __name__ == "__main__":
    main()
