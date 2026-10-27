"""Step 1. Parse Beresford's Lost Villages (University of Hull) into a clean table.

Input: the 2,222 records of the Hull "Beresford's Lost Villages" Village Explorer feature service,
saved as JSON (one object per site, the service's own field names).

Output: data/lost_villages.csv, one row per site, with
  * id = the service's FID (unique); hull_id = the service's own ID field, which is NOT unique
    (74 numbers are shared by two different sites in different counties), so it is kept only for reference;
  * identity, location (WGS84 from the service, checked against its British National Grid x/y),
    counties, parishes, site type, scheduled status;
  * every documentary field parsed into a number plus a status;
  * the presumed date of depopulation parsed into one or more year intervals;
  * a short description snippet.

Parsing rules for the documentary fields (all documented in README.md):
  value      the cell is a bare number ("12", "469.25"): used in every analysis
  qualified  a number followed by a note in brackets, e.g. "896 (Holme with)" or "51 (and Muscott)".
             Most such notes say the figure is shared with other places, so the number is kept in
             a separate column but NOT used for sizes or trajectories. It still counts as "recorded".
             For the censuses, a note that only names the unit ("(Parish)", "(Township)", ...) is
             treated as a plain value with that unit.
  recorded   the cell says "Recorded" (or similar) without a number: counts as recorded
  absent     "Not recorded" (any capitalisation or spelling slip): the source survives for the area
             but the place is not in it, or not separately
  no_source  "No surviving record", "No information", empty: the source does not survive or was not
             searched; left out of every denominator
  other      anything else (kept as text)

Usage:
    python3 code/01_parse.py [path/to/lost_villages_beresford.json]
"""
import csv
import json
import os
import re
import sys

import numpy as np
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "_data2", "lost_villages_beresford.json")
OUT = os.path.join(ROOT, "data", "lost_villages.csv")

FIELDS = {  # short name: service field
    "dom1086": "Domesday_min_no_indivs",
    "tax1291": "Taxation_1291_main",
    "sub1334": "Lay_subsidy_1334_total_paid",
    "poll1377n": "Poll_Tax_1377_no_paid",
    "poll1377d": "Poll_Tax_1377_total_paid",
    "poll1379n": "Poll_Tax_1379_no_paid",
    "poll1381n": "Poll_Tax_1381_no_paid",
    "sub1524n": "Lay_subsidy_1524_no_paid",
    "sub1524d": "Lay_Subsidy_1524_total_paid",
    "sub1525n": "Lay_Subsidy_1525_no_paid",
    "sub1543n": "Lay_Subsidy_1543_or_1544_no_pai",
    "dio1563": "Diocesan_returns_1563",
    "cen1801": "Census_popn_1801",
    "cen1841": "Census_popn_1841",
    "houses1841": "Inhabited_houses_1841",
}
UNITS = {"parish", "township", "village", "hamlet", "tithing", "chapelry", "extra-parochial", "extra parochial",
         "liberty", "parish part", "township part", "parish/township"}


def parse_cell(v, census=False):
    """Return (number or None, status, unit or '')."""
    if v is None:
        return None, "no_source", ""
    s = str(v).replace("\r", " ").replace("\n", " ").strip().rstrip("`").strip()
    low = s.lower()
    if s == "" or low in ("v", "-", "?", "blank"):
        return None, "no_source", ""
    if re.match(r"^no surviv|^no survin|^not surviving|^no information", low):
        return None, "no_source", ""
    if re.match(r"^(not|no) r[e]?c[o]?rded", low) or low == "absent":
        return None, "absent", ""
    if low in ("recorded",):
        return None, "recorded", ""
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)), "value", ""
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(\(.*)$", s)
    if m:
        note = m.group(2)
        notes = [n.strip().lower() for n in re.findall(r"\(([^)]*)\)", note)]
        if census and notes and all(n in UNITS for n in notes[:1]) and len(notes) == 1:
            return float(m.group(1)), "value", notes[0]
        return float(m.group(1)), "qualified", ""
    if low.startswith("not recorded") or low.startswith("not rcorded"):
        return None, "absent", ""
    if re.search(r"\(chapel recorded|^recorded", low):
        return None, "recorded", ""
    return None, "other", ""


# ---------------- presumed date of depopulation
ORD = {"12th": 12, "13th": 13, "14th": 14, "15th": 15, "16th": 16, "17th": 17, "18th": 18, "19th": 19, "20th": 20}


def century_part(word, c):
    """Years for '(early|mid|late|later) Nth century'. early = first 40 years, mid = years 30 to 70,
    late = last 40 years, plain = the whole century (e.g. 15th = 1400 to 1499)."""
    s = (c - 1) * 100
    w = (word or "").lower()
    if w.startswith("early"):
        return s, s + 39
    if w.startswith("mid"):
        return s + 30, s + 69
    if w.startswith("late"):
        return s + 60, s + 99
    return s, s + 99


def seg_intervals(seg):
    """Intervals in one segment of the text (see parse_dates)."""
    low = seg.lower().strip()
    if re.match(r"^\s*pre\b", low):
        return [], "vague"
    ivs = []
    for a, b in re.findall(r"(\d{4})\s*-\s*(?:c\.\s*)?(\d{1,4})", seg):
        a = int(a)
        b = int(str(a)[:4 - len(b)] + b) if len(b) < 4 else int(b)
        ivs.append((a, b))
    if ivs:
        rest = re.sub(r"(\d{4})\s*-\s*(?:c\.\s*)?(\d{1,4})", "", seg)
        extra = [int(y) for y in re.findall(r"(\d{4})", rest)]
        if extra and re.search(r"\bto\b", low):  # "1761 to 1876-7"
            ivs = [(min(extra + [a for a, _ in ivs]), max(b for _, b in ivs))]
        return ivs, "years"
    cs = [(w, c) for w, c in re.findall(r"(early|mid|later|late)?\s*(\d{2}th)", low) if c in ORD]
    ys = [int(y) for y in re.findall(r"(\d{4})", seg)]
    if cs:
        parts = [century_part(w, ORD[c]) for w, c in cs]
        lo, hi = min(p[0] for p in parts), max(p[1] for p in parts)
        if ys:  # "1761 to early 19th century"
            lo = min(lo, min(ys))
        return [(lo, hi)], "centuries"
    if ys:
        if len(ys) == 2 and re.search(r"\bto\b", low):
            return [(ys[0], ys[1])], "years"
        if re.search(r"post|after|onwards|final", low):
            return [(ys[0], ys[0] + 49)], "open-ended (start + 49 years)"
        return [(y, y) for y in ys], "years"
    return [], "vague"


def parse_dates(txt):
    """Return (list of (start, end) year intervals, rule label). Empty list = too vague to place.

    Rules: "1350-1400" and "c. 1350 - c. 1450" are read as written ("c." is ignored); "15th century"
    = 1400 to 1499; "early" = first 40 years of a century, "mid" = years 30 to 69, "late"/"later" = last
    40 years; "A to B" or "A-B" across centuries spans both; "between A and B" = A to B; "post 1761",
    "1600 onwards", "final stage post X" = X to X + 49 (an assumption); "pre X", "Medieval", "Late
    medieval" and similar are too vague to place and are left out of the timeline. Texts naming
    several phases ("1400-1500 then 1700-1800", "1761 and 1877-8") give several intervals.
    """
    if not txt:
        return [], ""
    t = txt.replace("\u2013", "-").replace("\u2014", "-").strip()
    t = re.sub(r"(?i)between (.+?) and (.+)", r"\1 to \2", t)
    segs = re.split(r"(?i),|\bthen\b|\band\b|\bplus\b|\bfurther\b|\bor earlier\b", t)
    ivs, rules = [], set()
    for s in segs:
        if not s.strip():
            continue
        v, rule = seg_intervals(s)
        ivs += v
        if v:
            rules.add(rule)
    if " or " in t.lower() and len(ivs) > 1:  # "15th or 16th century" style already merged; merge "A or B" years
        ivs = [(min(a for a, _ in ivs), max(b for _, b in ivs))]
    return ivs, "+".join(sorted(rules)) if ivs else "vague"


def snippet(desc, n=420):
    if not desc:
        return ""
    s = re.sub(r"\s+", " ", desc).strip()
    s = re.sub(r"\[\d+\]", "", s).replace(" .", ".").strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    k = max(cut.rfind(". "), 0)
    return (cut[:k + 1] if k > 200 else cut.rsplit(" ", 1)[0] + "...")


def nice_name(n):
    n = re.sub(r"\s+", " ", (n or "").strip())
    m = re.match(r"^(.*), (Great|Little|North|South|East|West|Upper|Lower|Nether|Over|Old|New|Middle|High|Low|Long|Far|Near)$", n)
    return f"{m.group(2)} {m.group(1)}" if m else n


def gridref_xy(g):
    """OS grid reference text ("TL 213385", "NZ 11 08") -> British National Grid metres (SW corner)."""
    g = str(g or "").replace(" ", "").upper()
    m = re.match(r"^([A-HJ-Z]{2})(\d+)$", g)
    if not m or len(m.group(2)) % 2:
        return None
    letters, digits = m.groups()
    a = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    l1, l2 = a.index(letters[0]), a.index(letters[1])
    e100 = ((l1 - 2) % 5) * 5 + (l2 % 5)
    n100 = (19 - (l1 // 5) * 5) - (l2 // 5)
    n = len(digits) // 2
    return e100 * 100000 + int(digits[:n]) * 10 ** (5 - n), n100 * 100000 + int(digits[n:]) * 10 ** (5 - n)


def consensus(r, to_bng, to_wgs):
    """The service gives each site three positions: the grid reference text, the x/y in British
    National Grid and a latitude/longitude. For 19 sites they disagree. I keep a position that at
    least one other witness confirms to within 1 km, preferring the grid reference, and record which."""
    lat, lon = float(r["Latitude"]), float(r["Longitude"])
    w = {"latlon": to_bng.transform(lon, lat), "xy": (r["x_coord"], r["y_coord"])}
    g = gridref_xy(r["Grid_reference"])
    if g:
        w["gridref"] = g
    agree = lambda a, b: np.hypot(w[a][0] - w[b][0], w[a][1] - w[b][1]) <= 1000
    for k in ("gridref", "xy", "latlon"):
        if k in w and any(agree(k, o) for o in w if o != k):
            if k == "latlon":
                return lat, lon, "latlon (confirmed)", w
            lo, la = to_wgs.transform(*w[k])
            return la, lo, k + (" (all agree)" if all(agree(k, o) for o in w) else " (confirmed)"), w
    return lat, lon, "latlon (unconfirmed)", w


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    tr = Transformer.from_crs(27700, 4326, always_xy=True)
    to_bng = Transformer.from_crs(4326, 27700, always_xy=True)
    rows = []
    for r in d:
        lat0, lon0 = float(r["Latitude"]), float(r["Longitude"])
        lat, lon, csrc, wit = consensus(r, to_bng, tr)
        x, y = to_bng.transform(lon, lat)
        dkm = max(float(np.hypot(x - v[0], y - v[1])) for v in wit.values()) / 1000
        status = (r["Site_status"] or "").strip()
        sched = "" if not status else ("scheduled" if status.lower().startswith("scheduled") else "not scheduled")
        ivs, rule = parse_dates(r["Presumed_date_of_depopulation"])
        row = {
            "id": r["FID"], "hull_id": r["ID"], "name": nice_name(r["Site_name"]), "name_source": (r["Site_name"] or "").strip(),
            "site_type": r["Site_type"], "county_pre1974": r["Pre_1974_county"],
            "county_now": r["Present_county_or_unitary_area"], "parish_modern": r["Parish_modern"],
            "parish_historic": r["Parish_historic"], "grid_ref": r["Grid_reference"],
            "x_bng": round(x), "y_bng": round(y), "lat": round(lat, 6), "lon": round(lon, 6),
            "position_source": csrc, "position_spread_km": round(dkm, 2),
            "source_lat": lat0, "source_lon": lon0, "source_x": r["x_coord"], "source_y": r["y_coord"],
            "scheduled_status": sched, "scheduled_text": status,
            "domesday_ref": (r["Domesday_reference"] or "").strip(),
        }
        for k, f in FIELDS.items():
            census = k.startswith("cen")
            v, st, unit = parse_cell(r[f], census)
            row[k] = "" if v is None or st != "value" else v
            row[k + "_any"] = "" if v is None else v
            row[k + "_status"] = st
            if census:
                row[k + "_unit"] = unit
        row["depop_text"] = (r["Presumed_date_of_depopulation"] or "").strip()
        row["depop_intervals"] = ";".join(f"{a}-{b}" for a, b in ivs)
        row["depop_rule"] = rule
        if ivs:
            row["depop_start"] = min(a for a, _ in ivs)
            row["depop_end"] = max(b for _, b in ivs)
        else:
            row["depop_start"] = row["depop_end"] = ""
        row["e179_last"] = (r["E179_date_and_type_last_doc"] or "").strip()
        m = re.match(r"^\s*(\d{4})", row["e179_last"])
        row["e179_last_year"] = int(m.group(1)) if m else ""
        row["has_description"] = bool(r["Description"] and len(r["Description"].strip()) > 20)
        row["description_snippet"] = snippet(r["Description"])
        row["description_full"] = re.sub(r"\s+", " ", r["Description"] or "").strip()
        rows.append(row)
    rows.sort(key=lambda x: x["id"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "sites ->", OUT)
    import collections
    print(collections.Counter(x["position_source"] for x in rows))
    print([(x["name"], x["position_source"], x["position_spread_km"]) for x in rows if "all agree" not in x["position_source"]])
    for x in rows:
        if x["depop_text"]:
            print(f'{x["depop_text"]!r:70} -> {x["depop_intervals"]} [{x["depop_rule"]}]')


if __name__ == "__main__":
    main()
