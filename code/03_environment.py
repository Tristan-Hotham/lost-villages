"""Step 3. Setting: height, relief, water and Roman roads for every lost village and Domesday place.

Adds these columns to data/lost_villages.csv and data/domesday_places_status.csv:
  elev_m        ground height at the point (AWS Terrain Tiles, zoom 10, about 100 m pixels here,
                bilinear interpolation; read with within-sight/code/dem.py)
  relief_m      highest minus lowest ground among the point and 16 points on rings 500 m and 1 km away
  river_m       distance to the nearest watercourse centre line in OS Open Rivers (rivers, tidal rivers,
                and lines through lakes; canals left out because almost all are post-medieval). Lines are
                densified to 25 m before a nearest-point search.
  river_named_m the same, for watercourses that carry a name
  roman_m       distance to the nearest Itiner-e Roman road (with the datum correction used in the
                "How Roman is your road?" project: results/itinere_gb_corrected.geojson)
  nn_dom_km     (Domesday places only) distance to the nearest other located Domesday place

Usage:
    python3 code/03_environment.py
Environment variables DEM_BIN, DEM_IDX, RIVERS, ROMAN override the default paths.
"""
import json
import os
import sqlite3
import struct
import sys

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "..")
sys.path.insert(0, os.path.join(HIST, "within-sight", "code"))
from dem import DEM  # noqa: E402

RIVERS = os.environ.get("RIVERS", os.path.join(HIST, "osrivers", "Data", "oprvrs_gb.gpkg"))
ROMAN = os.environ.get("ROMAN", os.path.join(HIST, "how-roman-is-your-road", "results", "itinere_gb_corrected.geojson"))
ENV_COLS = ["elev_m", "relief_m", "river_m", "river_named_m", "roman_m", "nn_dom_km"]
ENV_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def decode(blob):
    """GeoPackage binary -> list of (N,2) arrays (LineString / MultiLineString, 2D or 3D)."""
    flags = blob[3]
    wkb = blob[8 + ENV_BYTES[(flags >> 1) & 7]:]

    def read(p):
        bo = "<" if wkb[p] == 1 else ">"
        typ = struct.unpack(bo + "I", wkb[p + 1:p + 5])[0]
        dim = 3 if (typ // 1000 in (1, 2) or typ & 0x80000000) else 2
        base = (typ % 1000) & 0xFF
        p += 5
        n = struct.unpack(bo + "I", wkb[p:p + 4])[0]
        p += 4
        if base == 2:
            a = np.frombuffer(wkb[p:p + 8 * dim * n], dtype=bo + "f8").reshape(n, dim)[:, :2]
            return [a], p + 8 * dim * n
        out = []
        for _ in range(n):
            a, p = read(p)
            out += a
        return out, p
    return read(0)[0]


def densify(lines, step=25.0):
    pts = []
    for a in lines:
        if len(a) < 2:
            pts.append(a)
            continue
        seg = np.diff(a, axis=0)
        L = np.hypot(seg[:, 0], seg[:, 1])
        k = np.maximum(1, np.ceil(L / step).astype(int))
        for i in range(len(seg)):
            t = np.arange(k[i]) / k[i]
            pts.append(a[i] + seg[i] * t[:, None])
        pts.append(a[-1:])
    return np.vstack(pts)


def river_trees():
    con = sqlite3.connect(RIVERS)
    allp, named = [], []
    for geom, name in con.execute("select geometry, watercourse_name from watercourse_link where form != 'canal'"):
        for a in decode(geom):
            allp.append(a)
            if name:
                named.append(a)
    return cKDTree(densify(allp)), cKDTree(densify(named))


def roman_tree(to_bng):
    g = json.load(open(ROMAN))
    lines = []
    for f in g["features"]:
        geo = f["geometry"]
        parts = geo["coordinates"] if geo["type"] == "MultiLineString" else [geo["coordinates"]]
        for p in parts:
            a = np.array(p)[:, :2]
            x, y = to_bng.transform(a[:, 0], a[:, 1])
            lines.append(np.c_[x, y])
    return cKDTree(densify(lines))


def setting(lat, lon, dem, to_bng, trees):
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    out = {"elev_m": np.round(dem.elev(lat, lon), 1)}
    x, y = to_bng.transform(lon, lat)
    samples = [out["elev_m"]]
    to_wgs = Transformer.from_crs(27700, 4326, always_xy=True)
    for r in (500, 1000):
        for a in np.arange(8) * np.pi / 4:
            lo, la = to_wgs.transform(x + r * np.cos(a), y + r * np.sin(a))
            samples.append(dem.elev(la, lo))
    S = np.vstack(samples)
    out["relief_m"] = np.round(S.max(0) - S.min(0), 1)
    xy = np.c_[x, y]
    for k, t in trees.items():
        out[k] = np.round(t.query(xy)[0])
    return out


def main():
    to_bng = Transformer.from_crs(4326, 27700, always_xy=True)
    dem = DEM()
    print("reading rivers ...")
    tall, tnamed = river_trees()
    trees = {"river_m": tall, "river_named_m": tnamed, "roman_m": roman_tree(to_bng)}
    for fn, la, lo in (("lost_villages.csv", "lat", "lon"), ("domesday_places_status.csv", "lat", "lng")):
        path = os.path.join(ROOT, "data", fn)
        T = pd.read_csv(path, dtype={"placeId": str})
        T = T.drop(columns=[c for c in ENV_COLS if c in T.columns])
        for k, v in setting(T[la].values, T[lo].values, dem, to_bng, trees).items():
            T[k] = v
        if fn.startswith("domesday"):
            k = np.cos(np.radians(52.5))
            xy = np.c_[T[lo] * k * 111.32, T[la] * 110.57]
            T["nn_dom_km"] = np.round(cKDTree(xy).query(xy, k=2)[0][:, 1], 2)
        T.to_csv(path, index=False)
        print(fn, len(T), T[[c for c in ENV_COLS if c in T.columns]].median().to_dict())


if __name__ == "__main__":
    main()
