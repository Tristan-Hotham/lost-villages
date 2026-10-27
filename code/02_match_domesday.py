"""Step 2. Find each lost village among the places of Domesday Book (1086).

Domesday places come from the "Is Domesday Destiny?" project (data/domesday_places.csv there), which
was built from the realm-domesday repository (Hull Domesday Project data, CC BY-NC-SA, with place
links from Open Domesday). Each place has a location (centre of its 1 km grid square), the households
recorded in 1086 (heads of household, shared equally when an entry describes several places), plough
teams, mills, value and the Domesday entries (Phillimore references) its households come from.

A Beresford site is matched to a Domesday place when, within 5 km:
  (a) the names agree: identical once case, punctuation, [bracketed] modern additions, a trailing
      roman numeral, a part after a comma or a leading Great/Little/North/East/... are set aside
      (score 1.0), or a string similarity of at least 0.85 between such forms (difflib ratio); or
  (b) the site's own Domesday reference (e.g. "BEDS 23,45-47. 32,12") shares at least one entry with
      the entries that describe the Domesday place, and the names are at least 0.5 similar.
The best candidate (highest name score, a shared reference breaking ties, then the nearest) is kept.
A match is flagged qualifier_mismatch when the site's name has a distinguishing word (Little, North,
Parva, a roman numeral...) that the Domesday name lacks: the Domesday place may then be a parent vill
that also covers a surviving neighbour, so step 4 leaves such places out of the lost/survivor contrast.
Output: data/domesday_matches.csv (one row per Beresford site) and data/domesday_places_status.csv
(one row per located Domesday place, with a flag for "lost": matched by at least one Beresford site).

Usage:
    python3 code/02_match_domesday.py [path/to/domesday_places.csv]
"""
import difflib
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOM = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "domesday-destiny", "data", "domesday_places.csv")
MAX_KM = 5.0

CODES = {"BEDS": "Bedfordshire", "BERK": "Berkshire", "BUCK": "Buckinghamshire", "CAMB": "Cambridgeshire",
         "CHES": "Cheshire", "CORN": "Cornwall", "DERB": "Derbyshire", "DEVN": "Devon", "DORT": "Dorset",
         "ESSX": "Essex", "GLOS": "Gloucestershire", "HAMP": "Hampshire", "HERE": "Herefordshire",
         "HERT": "Hertfordshire", "HUNT": "Huntingdonshire", "KENT": "Kent", "LEIC": "Leicestershire",
         "LINC": "Lincolnshire", "MDX": "Middlesex", "NFOK": "Norfolk", "NHAM": "Northamptonshire",
         "NOTS": "Nottinghamshire", "OXFD": "Oxfordshire", "RUTD": "Rutland", "SHRO": "Shropshire",
         "SOMT": "Somerset", "STAF": "Staffordshire", "SUFF": "Suffolk", "SURY": "Surrey", "SUSX": "Sussex",
         "WARW": "Warwickshire", "WILT": "Wiltshire", "WORS": "Worcestershire", "YORK": "Yorkshire"}
PREFIX = r"^(great|little|north|south|east|west|upper|lower|nether|over|old|new|middle|high|low|long|far|near|king's|kings|bishop's|bishops)\s+"


def norm(s):
    s = str(s or "").lower()
    s = re.sub(r"[\[\]{}()`'.,]", "", s).replace("-", " ").replace("&", "and")
    return re.sub(r"\s+", " ", s).strip()


def variants(s):
    """Forms of a name to compare: as written; without [bracketed] modern additions; the part before a
    comma; without a trailing roman numeral; and each of these without a leading Great/Little/North/..."""
    s = str(s or "")
    forms = {s, re.sub(r"\[[^\]]*\]", "", s), s.split(",")[0], re.sub(r"\s+[IVX]+$", "", s), re.sub(r"\s*\([^)]*\)", "", s)}
    m = re.match(r"^(.*?)\s*\(([^)]*)\)", s)  # "Werateworde (Wratworth)"
    if m:
        forms.add(m.group(2))
    out = set()
    for f in forms:
        f = norm(f)
        if f:
            out.add(f)
            out.add(re.sub(PREFIX, "", f))
    return {f for f in out if f}


def name_score(a, b):
    """1.0 if any forms are identical, otherwise the best difflib ratio between forms (spaces removed)."""
    va, vb = variants(a), variants(b)
    if not va or not vb:
        return 0.0
    if va & vb:
        return 1.0
    return max(difflib.SequenceMatcher(None, x.replace(" ", ""), y.replace(" ", "")).ratio() for x in va for y in vb)


def beresford_refs(ref):
    """'BEDS 23,45-47. 32,12' -> {'Bedfordshire 23,45', ... '32,12'}; Yorkshire '1N8. 5N15' style kept."""
    out = set()
    ref = str(ref or "")
    m = re.match(r"\s*([A-Za-z]{3,4})\s+(.*)$", ref)
    if not m or m.group(1).upper() not in CODES:
        return out
    county = CODES[m.group(1).upper()]
    for tok in re.split(r"[.;]\s*|\s+and\s+", m.group(2)):
        tok = tok.strip().strip("()")
        mm = re.match(r"^([A-Za-z]*\d+[A-Za-z]?),(\d+)(?:-(\d+))?", tok)       # 23,45-47  /  IoW6,18
        if mm:
            a = int(mm.group(2)); b = int(mm.group(3)) if mm.group(3) else a
            for k in range(a, min(b, a + 30) + 1):
                out.add(f"{county} {mm.group(1)},{k}")
            continue
        mm = re.match(r"^(\d+[NEWY])(\d+)(?:-(\d+))?", tok)                       # Yorkshire 1N8
        if mm:
            a = int(mm.group(2)); b = int(mm.group(3)) if mm.group(3) else a
            for k in range(a, min(b, a + 30) + 1):
                out.add(f"{county} {mm.group(1)}{k}")
    return out


QUAL = r"\b(great|little|north|south|east|west|upper|lower|nether|over|old|new|middle|high|low|long|far|near|parva|magna|minor|major|[ivx]+)\b"


def qualifier_mismatch(site_names, dom_name):
    """True when the site's name carries a distinguishing word (Little, North, Parva, a roman numeral...)
    that the Domesday name lacks, even in [brackets]. Such a Domesday place may stand for a parent vill
    that also covers a surviving neighbour (e.g. Little Ringstead matched to Domesday "Ringstead")."""
    d = set(re.findall(QUAL, str(dom_name).lower()))
    for n in site_names:
        q = set(re.findall(QUAL, str(n).lower().replace("-", " "))) - {"over"}
        if q and not (q & d):
            return True
    return False


def place_refs(s):
    return {re.sub(r"\s*\([^)]*\)$", "", t.strip()) for t in str(s or "").split(";") if t.strip() and s == s}


def main():
    L = pd.read_csv(os.path.join(ROOT, "data", "lost_villages.csv"))
    P = pd.read_csv(DOM, dtype={"placeId": str})
    P = P[P.lat.notna()].reset_index(drop=True)
    k = np.cos(np.radians(52.5))
    tree = cKDTree(np.c_[P.lng * k * 111.32, P.lat * 110.57])
    P["refs"] = P.householdEntries.apply(place_refs)
    rows = []
    for _, r in L.iterrows():
        refs = beresford_refs(r.domesday_ref)
        idx = tree.query_ball_point([r.lon * k * 111.32, r.lat * 110.57], MAX_KM)
        best = None
        for i in idx:
            p = P.iloc[i]
            sc = max(name_score(r["name"], p["name"]), name_score(r["name_source"], p["name"]))
            shared = len(refs & p.refs)
            km = float(np.hypot((p.lng - r.lon) * k * 111.32, (p.lat - r.lat) * 110.57))
            ok = sc >= 0.85 or (shared and sc >= 0.5)
            if not ok:
                continue
            key = (round(sc, 3), shared > 0, -km)
            if best is None or key > best[0]:
                best = (key, i, sc, shared, km)
        row = {"id": r.id, "name": r["name"], "beresford_dom1086": r.dom1086, "beresford_dom_status": r.dom1086_status,
               "beresford_ref_entries": len(refs)}
        if best:
            p = P.iloc[best[1]]
            row.update({"placeId": p.placeId, "dom_name": p["name"], "dom_county": p.countyName, "name_score": round(best[2], 3),
                        "shared_refs": best[3], "km": round(best[4], 2), "households1086": p.households1086,
                        "ploughTeams1086": p.ploughTeams1086, "value1086": p.value1086, "mills1086": p.mills1086,
                        "slaves1086": p.slaves1086, "openDomesdayPath": p.openDomesdayPath,
                        "rule": "name" if best[2] >= 0.85 else "reference+name",
                        "qualifier_mismatch": qualifier_mismatch([r["name"], r["name_source"]], p["name"])})
        rows.append(row)
    M = pd.DataFrame(rows)
    M.to_csv(os.path.join(ROOT, "data", "domesday_matches.csv"), index=False)
    lostids = set(M.placeId.dropna())
    P["lost_beresford"] = P.placeId.isin(lostids)
    keep = ["placeId", "name", "county", "countyName", "lat", "lng", "households1086", "villagers1086", "smallholders1086",
            "slaves1086", "ploughTeams1086", "mills1086", "value1086", "entries", "mostPlacesInOneEntry", "parishName",
            "likelyLost", "lost_beresford"]
    P[keep].to_csv(os.path.join(ROOT, "data", "domesday_places_status.csv"), index=False)
    m = M.placeId.notna()
    print("matched", m.sum(), "of", len(M), "| rules", M.rule.value_counts().to_dict())
    hasref = L.dom1086_status.isin(["value", "qualified"]).values | L.domesday_ref.str.match(r"^[A-Za-z]{4}\s+\d", na=False).values
    print("matched among sites Beresford says are in Domesday:", (m & hasref).sum(), "/", hasref.sum())
    print("matched among sites with no Domesday reference:", (m & ~hasref).sum(), "/", (~hasref).sum())
    print("distinct Domesday places matched", len(lostids))
    both = M[m & M.beresford_dom1086.notna() & M.households1086.notna()]
    print("both figures", len(both), "spearman", both[["beresford_dom1086", "households1086"]].corr("spearman").iloc[0, 1],
          "within 1", (abs(both.beresford_dom1086 - both.households1086) <= 1).mean())


if __name__ == "__main__":
    main()
