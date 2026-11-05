"""
Finds the weapons (stores) hanging on a jet model, from shape (IDEA-34). Used by artsrc/jets/loadouts.py (survey
pictures) and artsrc/units/meshes/import_sketchfab.py (splits the chosen stores off for the station overlays).

A store is a long thin body lying along the flight direction, round in section, 10-45% of the aircraft's length;
pieces on one axis (body, seeker, fins) merge into one store, small pieces touching it (fins, rails) join it.
Coordinates are the unit .blend's: nose +Y, ground z = 0.
"""

import math

import bmesh
import numpy as np


def islands(obj):
    """Loose pieces of a mesh: (face indices, world points)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    seen, out = set(), []
    mw = obj.matrix_world
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, faces = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            faces.append(g.index)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        pts = np.array([(mw @ v.co)[:] for i in faces for v in bm.faces[i].verts])
        out.append((faces, pts))
    bm.free()
    return out


def shape(pts):
    """Long axis, its length, the body's diameter and centre (PCA)."""
    c = pts.mean(0)
    w, vecs = np.linalg.eigh(np.cov((pts - c).T) + np.eye(3) * 1e-9)
    ax = vecs[:, np.argmax(w)]
    proj = (pts - c) @ ax
    rest = pts - c - np.outer(proj, ax)
    diam = 2 * np.percentile(np.linalg.norm(rest, axis=1), 90)
    return ax, proj.max() - proj.min(), diam, c


def roundness(pts, ax):
    """Cross-section ratio (1 = round like a missile, large = flat like a panel)."""
    c = pts.mean(0)
    rest = (pts - c) - np.outer((pts - c) @ ax, ax)
    w = np.sort(np.linalg.eigvalsh(np.cov(rest.T) + np.eye(3) * 1e-12))[1:]
    return math.sqrt(w[1] / max(w[0], 1e-12))


def bounds(meshes):
    pts = np.concatenate([np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) for o in meshes])
    return pts.min(0), pts.max(0)


def family(s, length):
    """A first guess from proportions; the loadout table has the final word."""
    ratio = s["len"] / s["diam"]
    if s["diam"] > 0.038 * length:
        return "tank"  # fat: drop tank or pod
    if ratio > 14:
        return "aam-short" if s["len"] < 0.21 * length else "aam-medium"
    if ratio > 7:
        return "agm"
    return "bomb"


def find(meshes):
    """Stores on the model: [{centre, len, diam, family, faces: [(object name, [face indices])]}]."""
    lo, hi = bounds(meshes)
    length, span, height = hi[1] - lo[1], hi[0] - lo[0], hi[2] - lo[2]
    pieces = []
    for o in meshes:
        for faces, pts in islands(o):
            if len(pts) < 8:
                continue
            ax, ln, diam, c = shape(pts)
            pieces.append({"obj": o.name, "faces": faces, "pts": pts, "axis": ax, "len": ln, "diam": diam, "centre": c})

    cand = [p for p in pieces if abs(p["axis"][1]) > 0.85 and p["diam"] < 0.08 * span and p["len"] < 0.5 * length
            and roundness(p["pts"], p["axis"]) < 2.2]
    cand.sort(key=lambda p: (round(p["centre"][0], 2), p["centre"][1]))
    stores = []
    for p in cand:
        y0, y1 = p["pts"][:, 1].min(), p["pts"][:, 1].max()
        for s in stores:
            tol = max(s["diam"], p["diam"]) * 0.6 + 0.01 * span
            if (abs(s["centre"][0] - p["centre"][0]) < tol and abs(s["centre"][2] - p["centre"][2]) < tol
                    and y0 < s["y1"] + 0.02 * length and y1 > s["y0"] - 0.02 * length):
                s["pts"] = np.concatenate([s["pts"], p["pts"]])
                s["parts"].append(p)
                s["y0"], s["y1"] = min(s["y0"], y0), max(s["y1"], y1)
                s["diam"] = max(s["diam"], p["diam"])
                break
        else:
            stores.append(dict(p, y0=y0, y1=y1, parts=[p]))
    for s in stores:
        s["len"] = s["y1"] - s["y0"]
        s["centre"] = s["pts"].mean(0)
    stores = [s for s in stores if 0.1 * length < s["len"] < 0.45 * length and s["len"] / max(s["diam"], 1e-6) > 3.5
              and (abs(s["centre"][0]) > 0.12 * span or s["centre"][2] < lo[2] + 0.35 * height)]
    taken = {id(p) for s in stores for p in s["parts"]}
    for p in pieces:  # fins and rails touching a store
        if p["len"] > 0.06 * length or id(p) in taken:
            continue
        for s in stores:
            smin, smax = s["pts"].min(0) - 0.03, s["pts"].max(0) + 0.03
            if np.all(p["centre"] >= smin) and np.all(p["centre"] <= smax):
                s["parts"].append(p)
                taken.add(id(p))
                break
    out = []
    for s in stores:
        faces = {}
        for p in s["parts"]:
            faces.setdefault(p["obj"], []).extend(p["faces"])
        out.append({"centre": [float(v) for v in s["centre"]], "len": float(s["len"]), "diam": float(s["diam"]),
                    "family": family(s, length), "faces": list(faces.items())})
    return out, {"length": float(length), "span": float(span), "lo": lo.tolist(), "hi": hi.tolist()}
