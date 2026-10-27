"""Step 4. Every number used on the page, README, paper, blog and collage -> data/results.json.

Reads data/lost_villages.csv (steps 1 and 3), data/domesday_matches.csv and
data/domesday_places_status.csv (steps 2 and 3). Also writes:
  data/lost_villages.geojson   one point per site with the key fields (for reuse in GIS)
  data/county_summary.csv      per historic county: sites, types, Domesday places and share lost
  data/depopulation_dates.csv  one row per site with a presumed date: text, intervals, period
  _site_data.json              compact data embedded in the page by step 5 (temporary)

Definitions (all documented in README.md):
  "lost Domesday place"   a located Domesday place matched (step 2) by a site of type DMV or DMH
                          (deserted village or hamlet) without a qualifier mismatch. Places matched only
                          by shrunken, shifted, migrated or doubtful sites, or only through a qualifier
                          mismatch (e.g. Little X matched to Domesday X), are left out of both groups.
  "survivor"              any other located Domesday place in the same Domesday counties. Some will be
                          deserted places that Beresford's 1968 list missed, so the contrast is, if
                          anything, understated.
  depopulation timeline   each dated site carries weight 1, spread evenly over the years of its parsed
                          interval(s) (several intervals share the weight in proportion to length).
Usage:
    python3 code/04_analyse.py
"""
import json
import os
import re

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
L = pd.read_csv(os.path.join(D, "lost_villages.csv"))
M = pd.read_csv(os.path.join(D, "domesday_matches.csv"), dtype={"placeId": str})
P = pd.read_csv(os.path.join(D, "domesday_places_status.csv"), dtype={"placeId": str})
R = {}

FULL = ["Bedfordshire", "Berkshire", "Buckinghamshire", "Cambridgeshire", "Cheshire", "Cornwall", "Cumberland",
        "Derbyshire", "Devon", "Dorset", "Durham", "Essex", "Gloucestershire", "Yorkshire East Riding"]
TYPES = ["DMV", "DMH", "Shrunken", "Shifted", "Migrated", "Doubtful"]
TYPE_LABEL = {"DMV": "Deserted village", "DMH": "Deserted hamlet", "Shrunken": "Shrunken village",
              "Shifted": "Shifted village", "Migrated": "Migrated village", "Doubtful": "Doubtful site"}


def hist_county(c):
    c = str(c)
    for k in ("Yorkshire", "Lincolnshire", "Suffolk", "Sussex"):
        if c.startswith(k):
            return k
    return "Hampshire" if c == "Isle of Wight" else c


def r2(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


L["county"] = L.county_pre1974.map(hist_county)
L["full_record"] = L.county_pre1974.isin(FULL)
L["deserted"] = L.site_type.isin(["DMV", "DMH"])

# ------------------------------------------------------------------ 1. the gazetteer
R["n_sites"] = len(L)
R["types"] = {t: int((L.site_type == t).sum()) for t in TYPES}
R["n_deserted"] = int(L.deserted.sum())
R["n_counties"] = int(L.county.nunique())
R["n_full_counties"] = len(FULL)
R["n_full_sites"] = int(L.full_record.sum())
R["full_counties"] = FULL
R["n_with_description"] = int(L.has_description.sum())
R["position_fixed"] = int((~L.position_source.str.contains("all agree")).sum())
R["position_far"] = int((L.position_spread_km > 5).sum())
cc = L.county.value_counts()
R["by_county"] = [{"county": c, "n": int(n)} for c, n in cc.items()]
R["top_counties"] = R["by_county"][:6]

# scheduled monuments (status given only in full-record counties)
st = L[L.scheduled_status.notna()]
R["sched_known"] = len(st)
R["sched_n"] = int((st.scheduled_status == "scheduled").sum())
R["sched_share"] = r2(R["sched_n"] / R["sched_known"], 4)

# ------------------------------------------------------------------ 2. Domesday comparison
R["beresford_in_domesday"] = int((L.dom1086_status.isin(["value", "qualified"]) |
                                  L.domesday_ref.str.match(r"^[A-Za-z]{4}\s+\d", na=False)).sum())
R["beresford_not_in_domesday"] = int((L.dom1086_status == "absent").sum())
R["beresford_dom_value_n"] = int((L.dom1086_status == "value").sum())
R["beresford_dom_median"] = r2(L.dom1086.median(), 1)
R["beresford_dom_zero"] = int((L.dom1086 == 0).sum())
mm = M[M.placeId.notna()]
R["matched_sites"] = len(mm)
R["matched_places"] = int(mm.placeId.nunique())
R["matched_by_ref_rule"] = int((mm.rule == "reference+name").sum())
both = mm[mm.beresford_dom1086.notna() & mm.households1086.notna()]
R["check_both_n"] = len(both)
R["check_spearman"] = r2(stats.spearmanr(both.beresford_dom1086, both.households1086)[0], 3)
R["check_within1"] = r2((abs(both.beresford_dom1086 - both.households1086) <= 1).mean(), 4)
R["match_km_median"] = r2(mm.km.median(), 2)

mt_ = mm.merge(L[["id", "site_type"]], on="id")
types_by_place = mt_.groupby("placeId").site_type.apply(set)
clean = mt_[mt_.site_type.isin(["DMV", "DMH"]) & ~mt_.qualifier_mismatch.astype(bool)]
lost_ids = set(clean.placeId)
R["qualifier_mismatch_sites"] = int(mm.qualifier_mismatch.astype(bool).sum())
other_ids = set(types_by_place.index) - lost_ids
P["group"] = np.where(P.placeId.isin(lost_ids), "lost", np.where(P.placeId.isin(other_ids), "other", "survivor"))
counties_with_lost = P[P.group == "lost"].countyName.value_counts()
Pc = P[P.group != "other"].copy()  # all Domesday counties are kept
R["dom_places_located"] = len(P)
R["dom_lost"] = int((P.group == "lost").sum())
R["dom_other_matched"] = int((P.group == "other").sum())
R["dom_survivors"] = int((P.group == "survivor").sum())
R["dom_lost_share"] = r2(R["dom_lost"] / (R["dom_lost"] + R["dom_survivors"]), 4)

hh = Pc[Pc.households1086 > 0]
lo, su = hh[hh.group == "lost"], hh[hh.group == "survivor"]
R["hh_lost_n"], R["hh_surv_n"] = len(lo), len(su)
R["hh_lost_median"], R["hh_surv_median"] = r2(lo.households1086.median(), 1), r2(su.households1086.median(), 1)
R["hh_lost_mean"], R["hh_surv_mean"] = r2(lo.households1086.mean(), 1), r2(su.households1086.mean(), 1)
R["hh_lost_q25"], R["hh_lost_q75"] = r2(lo.households1086.quantile(.25), 1), r2(lo.households1086.quantile(.75), 1)
R["hh_surv_q25"], R["hh_surv_q75"] = r2(su.households1086.quantile(.25), 1), r2(su.households1086.quantile(.75), 1)
R["hh_mwu_p"] = float(f"{stats.mannwhitneyu(lo.households1086, su.households1086).pvalue:.2g}")
# within county: percentile of each place in its own county's distribution
hh = hh.copy()
hh["pct_in_county"] = hh.groupby("countyName").households1086.rank(pct=True, method="average")
R["hh_lost_county_pct_median"] = r2(hh[hh.group == "lost"].pct_in_county.median(), 3)
R["hh_lost_below_county_median"] = r2((hh[hh.group == "lost"].pct_in_county < 0.5).mean(), 4)
# chance of being lost by size band
bands = [(0, 5, "1 to 5"), (5, 10, "6 to 10"), (10, 20, "11 to 20"), (20, 40, "21 to 40"), (40, 1e9, "Over 40")]
R["loss_by_size"] = []
for a, b, lab in bands:
    q = hh[(hh.households1086 > a) & (hh.households1086 <= b)]
    R["loss_by_size"].append({"band": lab, "n": len(q), "lost": int((q.group == "lost").sum()),
                              "share": r2((q.group == "lost").mean(), 4),
                              "lost_dist": r2((lo.households1086.between(a + 1e-9, b)).mean(), 4),
                              "surv_dist": r2((su.households1086.between(a + 1e-9, b)).mean(), 4)})
# the middling-size peak: share lost in the 6 to 20 band versus the rest
mid = hh[(hh.households1086 > 5) & (hh.households1086 <= 20)]
R["loss_mid_share"] = r2((mid.group == "lost").mean(), 4)
# other 1086 measures
for k, col in (("pt", "ploughTeams1086"), ("val", "value1086")):
    a, b = Pc[(Pc.group == "lost") & Pc[col].notna()][col], Pc[(Pc.group == "survivor") & Pc[col].notna()][col]
    R[f"{k}_lost_median"], R[f"{k}_surv_median"] = r2(a.median(), 1), r2(b.median(), 1)
R["mill_lost_share"] = r2((Pc[Pc.group == "lost"].mills1086 > 0).mean(), 4)
R["mill_surv_share"] = r2((Pc[Pc.group == "survivor"].mills1086 > 0).mean(), 4)
x = Pc[(Pc.households1086 > 0) & Pc.ploughTeams1086.notna()]
x = x.assign(ptph=x.ploughTeams1086 / x.households1086)
R["ptph_lost_median"] = r2(x[x.group == "lost"].ptph.median(), 2)
R["ptph_surv_median"] = r2(x[x.group == "survivor"].ptph.median(), 2)
R["destiny_flag_overlap"] = int(P[P.group == "lost"].likelyLost.fillna(False).astype(bool).sum())

# county share of Domesday places later lost
cs = Pc.groupby("countyName").agg(n=("group", "size"), lost=("group", lambda s: (s == "lost").sum()))
cs["share"] = cs.lost / cs.n
cs = cs[cs.n >= 100].sort_values("share", ascending=False)
R["dom_county_share"] = [{"county": c, "n": int(r.n), "lost": int(r.lost), "share": r2(r.share, 4)} for c, r in cs.iterrows()]
R["dom_counties_over10"] = int((cs.share >= 0.10).sum())
R["dom_counties_under3"] = int((cs.share < 0.03).sum())
R["dom_counties_n"] = len(cs)

# ------------------------------------------------------------------ 3. setting
env = {}
for k in ("elev_m", "relief_m", "river_m", "roman_m", "nn_dom_km"):
    a, b = Pc[Pc.group == "lost"][k].dropna(), Pc[Pc.group == "survivor"][k].dropna()
    env[k] = {"lost": r2(a.median(), 1), "surv": r2(b.median(), 1), "p": float(f"{stats.mannwhitneyu(a, b).pvalue:.2g}")}
    t = Pc[Pc[k].notna()].copy()
    t["pc"] = t.groupby("countyName")[k].rank(pct=True)
    env[k]["lost_county_pct"] = r2(t[t.group == "lost"].pc.median(), 3)
R["env"] = env
R["lv_elev_median"] = r2(L.elev_m.median(), 1)
R["lv_river_median"] = r2(L.river_m.median(), 0)
R["lv_over_200m"] = int((L.elev_m > 200).sum())

# ------------------------------------------------------------------ 4. the record fades
SRC = [("dom1086", "1086", "Domesday Book"), ("sub1334", "1334", "Lay subsidy"), ("poll1377n", "1377", "Poll tax"),
       ("sub1524n", "1524", "Lay subsidy"), ("sub1543n", "1543", "Lay subsidy"), ("dio1563", "1563", "Diocesan returns"),
       ("cen1801", "1801", "Census"), ("cen1841", "1841", "Census")]
fade = []
for k, yr, lab in SRC:
    s = L[k + "_status"]
    rec = s.isin(["value", "qualified", "recorded"]).sum()
    ab = (s == "absent").sum()
    fade.append({"key": k, "year": yr, "source": lab, "recorded": int(rec), "absent": int(ab),
                 "share": r2(rec / (rec + ab), 4), "median": r2(L[k].median(), 1), "n_value": int(L[k].notna().sum())})
R["fade"] = fade
R["tax1291_recorded"] = int(L.tax1291_status.isin(["value", "qualified", "recorded"]).sum())
R["tax1291_absent"] = int((L.tax1291_status == "absent").sum())
# villages in the 1377 poll tax that are missing from 1524/5 (where the 1524 source survives)
a = L[L.poll1377n_status.isin(["value", "qualified", "recorded"]) & L.sub1524n_status.isin(["value", "qualified", "recorded", "absent"])]
R["p1377_then_1524_n"] = len(a)
R["p1377_absent_1524"] = int((a.sub1524n_status == "absent").sum())
R["p1377_absent_1524_share"] = r2(R["p1377_absent_1524"] / len(a), 4)
a = L[L.sub1334_status.isin(["value", "qualified", "recorded"]) & L.sub1524n_status.isin(["value", "qualified", "recorded", "absent"])]
R["s1334_then_1524_n"] = len(a)
R["s1334_absent_1524_share"] = r2((a.sub1524n_status == "absent").mean(), 4)
pair = L[L.poll1377n.notna() & L.sub1524n.notna()]
R["pair_1377_1524_n"] = len(pair)
R["pair_1377_median"], R["pair_1524_median"] = r2(pair.poll1377n.median(), 1), r2(pair.sub1524n.median(), 1)
R["poll1377_median"] = r2(L.poll1377n.median(), 1)
R["poll1377_n"] = int(L.poll1377n.notna().sum())
R["poll1377_under20"] = r2((L.poll1377n.dropna() < 20).mean(), 4)
R["sub1524_le5"] = r2((L.sub1524n.dropna() <= 5).mean(), 4)
R["sub1524_n"] = int(L.sub1524n.notna().sum())
R["sub1524_median"] = r2(L.sub1524n.median(), 1)
R["e179_n"] = int(L.e179_last_year.notna().sum())
R["e179_median"] = int(L.e179_last_year.median())
R["e179_after1600"] = r2((L.e179_last_year.dropna() > 1600).mean(), 4)

# ------------------------------------------------------------------ 5. presumed dates of depopulation
dated = L[L.depop_text.notna()].copy()
R["dated_n"] = len(dated)
R["dated_full_n"] = int(dated.full_record.sum())
R["dated_parsed"] = int(dated.depop_intervals.notna().sum())
R["dated_vague"] = R["dated_n"] - R["dated_parsed"]
years = np.arange(1100, 2000)
mass = np.zeros(len(years))
for s in dated.depop_intervals.dropna():
    ivs = [tuple(map(int, t.split("-"))) for t in s.split(";")]
    tot = sum(b - a + 1 for a, b in ivs)
    for a, b in ivs:
        a, b = max(a, 1100), min(b, 1999)
        if b >= a:
            mass[a - 1100:b - 1100 + 1] += 1 / tot
PER = [("Before 1348", 1100, 1347), ("1348 to 1449", 1348, 1449), ("1450 to 1549", 1450, 1549),
       ("1550 to 1699", 1550, 1699), ("1700 onwards", 1700, 1999)]
tot = mass.sum()
R["periods"] = [{"label": l, "a": a, "b": b, "mass": r2(mass[(years >= a) & (years <= b)].sum(), 1),
                 "share": r2(mass[(years >= a) & (years <= b)].sum() / tot, 4)} for l, a, b in PER]
R["share_after_1450"] = r2(mass[years >= 1450].sum() / tot, 4)
dec = mass.reshape(-1, 10).sum(1)
R["decades"] = [[int(1100 + 10 * i), r2(v, 2)] for i, v in enumerate(dec)]
R["peak_decade"] = int(1100 + 10 * dec.argmax())
# by midpoint of each site's overall range (used for the map filter)


def period_of(r):
    if pd.isna(r.depop_start):
        return "No usable date" if pd.notna(r.depop_text) else "No date given"
    m = (r.depop_start + r.depop_end) / 2
    for l, a, b in PER:
        if a <= m <= b:
            return l
    return "Before 1348"


L["depop_period"] = L.apply(period_of, axis=1)
R["period_counts_mid"] = {k: int(v) for k, v in L.depop_period.value_counts().items()}
R["dated_ranges_touch_bd"] = int(((L.depop_start <= 1449) & (L.depop_end >= 1348)).sum())
R["dated_ranges_touch_enc"] = int(((L.depop_start <= 1549) & (L.depop_end >= 1450)).sum())
R["dated_ranges_after1700"] = int((L.depop_end >= 1700).sum())
widths = (L.depop_end - L.depop_start).dropna()
R["dated_width_median"] = int(widths.median())

# ------------------------------------------------------------------ 6. what the descriptions mention
CAUSES = [
    ("enclosure", "Enclosure or conversion to pasture",
     r"\bsheep\b|enclosure of \d|enclosed (for|by|in|between|c\.|around|about) ?[\dA-Za-z]|enclosure (for|by the|in 1|in the 1[4-6]|between|award|act)|convert\w* (\w+ ){0,4}(to|into) (sheep )?pasture|(arable|tillage) (to|into) pasture|depopulat\w* (\w+ ){0,6}enclos|enclos\w* (\w+ ){0,6}depopulat|inquisition|commission of 1517|in 1517"),
    ("park", "Emparking or a country house",
     r"empark|parkland|landscap\w* (park|garden)|(creat|construct|laid out|lay[- ]out|form|extension)\w* (of )?(the |a )?(\w+ ){0,3}park\b|\bpark (was|around)|cleared .{0,40}park|park .{0,30}cleared"),
    ("plague", "Black Death or plague", r"black death|\bplague|pestilence|\b134[89]\b"),
    ("monastic", "A monastic grange or landholder", r"grange|cistercian|monks|\bpriory\b|\babbey\b"),
    ("water", "Sea, erosion or flooding", r"erosion|\binto the sea|\bto the sea\b|flooded|flooding|inundat|sand[- ]?blow|drifting sand"),
]
d = L[L.has_description].copy()
R["desc_n"] = len(d)
R["causes"] = []
for k, lab, pat in CAUSES:
    hit = d.description_full.str.contains(re.sub(r"\((?!\?)", "(?:", pat), case=False, regex=True)
    L.loc[d.index, "mentions_" + k] = hit
    R["causes"].append({"key": k, "label": lab, "n": int(hit.sum()), "share": r2(hit.mean(), 4)})
R["desc_any_cause"] = int(L[[f"mentions_{k}" for k, _, _ in CAUSES]].fillna(False).astype(bool).any(axis=1).sum())

# ------------------------------------------------------------------ examples for the page
def ex(name, county=None):
    q = L[L.name == name]
    if county:
        q = q[q.county == county]
    r = q.iloc[0]
    m = M[M.id == r.id].iloc[0]
    return {"name": r["name"], "county": r.county, "type": r.site_type, "dom1086": r2(r.dom1086, 0),
            "poll1377": r2(r.poll1377n, 0), "sub1334": r2(r.sub1334, 0), "sub1524": r2(r.sub1524n, 0),
            "depop": r.depop_text if pd.notna(r.depop_text) else "", "hh1086": r2(m.households1086, 1)}


R["examples"] = {}
for nm, c in (("Wharram Percy", "Yorkshire"), ("Caythorpe", "Yorkshire"), ("Ravenserod", "Yorkshire"), ("Creslow", "Buckinghamshire")):
    try:
        R["examples"][nm] = ex(nm, c)
    except Exception as e:  # noqa
        print("no example", nm, e)

# lost villages with figures at 1086, 1377 and 1524 (for the trajectory table)
t = L[L.dom1086.notna() & L.poll1377n.notna() & L.sub1524n.notna()].copy()
R["traj_n"] = len(t)
R["traj_examples"] = [{"name": r["name"], "county": r.county, "d1086": r2(r.dom1086, 0), "p1377": r2(r.poll1377n, 0),
                       "s1524": r2(r.sub1524n, 0), "c1801": r2(r.cen1801, 0), "depop": r.depop_text if pd.notna(r.depop_text) else ""}
                      for _, r in t.sort_values("poll1377n", ascending=False).head(10).iterrows()]

# four stories told by the record's own descriptions (quotes are checked to be verbatim)
STORIES = [
    ("Wharram Percy", "Yorkshire", "pasture", ["A record of tenant holdings from 1368 also records 30 farmhouses and cottages in the village.",
                                               "By 1435 only 16 are recorded showing the decline of the settlement had begun.",
                                               "It has been well established that the fate of Wharram was the conversion to pasture.",
                                               "A legal case that was heard in 1555 helps date the final stage of conversion to 1527."]),
    ("Caythorpe", "Yorkshire", "enclosure", ["Depopulation at the site was reported in 1517 with 20 residents and five houses removed as a result of the enclosure of 300 acres for sheep pasture."]),
    ("Ravenserod", "Yorkshire", "sea", ["By 1346 two thirds of the town was destroyed.", "The residents had moved to Hull and taken up residence in the town."]),
    ("Derwent", "Derbyshire", "water", ["In essence this is not a truly deserted medieval village as it was not abandoned until the 1940s, when the settlement was flooded with the creation of Lady Bower Reservoir."]),
]
R["stories"] = []
for nm, c, k, qs in STORIES:
    r = L[(L.name == nm) & (L.county == c)].iloc[0]
    for q in qs:
        assert q in r.description_full, (nm, q)
    R["stories"].append({"name": nm, "county": c, "kind": k, "quotes": qs, "type": r.site_type,
                         "depop": r.depop_text if pd.notna(r.depop_text) else "", "poll1377": r2(r.poll1377n, 0),
                         "sub1334": r2(r.sub1334, 0), "scheduled": r.scheduled_status if pd.notna(r.scheduled_status) else "",
                         "lat": r.lat, "lon": r.lon})

# ------------------------------------------------------------------ outputs
L.to_csv(os.path.join(D, "lost_villages.csv"), index=False)
cs_all = L.groupby("county").agg(sites=("id", "size"), deserted=("deserted", "sum"),
                                 full_record=("full_record", "max")).reset_index()
cs_all.sort_values("sites", ascending=False).to_csv(os.path.join(D, "county_summary.csv"), index=False)
L[L.depop_text.notna()][["id", "name", "county", "site_type", "depop_text", "depop_intervals", "depop_rule",
                         "depop_start", "depop_end", "depop_period"]].to_csv(os.path.join(D, "depopulation_dates.csv"), index=False)
dom_lost = Pc[["placeId", "name", "countyName", "lat", "lng", "households1086", "ploughTeams1086", "value1086",
               "mills1086", "elev_m", "relief_m", "river_m", "roman_m", "nn_dom_km", "group"]]
dom_lost.to_csv(os.path.join(D, "domesday_lost_vs_survivors.csv"), index=False)

feats = []
for _, r in L.iterrows():
    props = {k: (None if pd.isna(r[k]) else (r[k].item() if hasattr(r[k], "item") else r[k])) for k in
             ["id", "name", "site_type", "county", "parish_modern", "grid_ref", "scheduled_status", "dom1086", "sub1334",
              "poll1377n", "sub1524n", "cen1801", "depop_text", "depop_period", "elev_m", "river_m"]}
    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]}, "properties": props})
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(D, "lost_villages.geojson"), "w"),
          separators=(",", ":"))

# compact page data
mt = M.set_index("id")
TY = {t: i for i, t in enumerate(TYPES)}
PERL = [p[0] for p in PER] + ["No usable date", "No date given"]
CO = sorted(L.county.unique())
rows = []
bad = lambda m: pd.isna(m.placeId) or bool(m.qualifier_mismatch)
for _, r in L.iterrows():
    m = mt.loc[r.id]
    num = lambda v: None if pd.isna(v) else (int(v) if float(v).is_integer() else round(float(v), 1))
    rows.append([round(r.lat, 4), round(r.lon, 4), r["name"], TY[r.site_type], CO.index(r.county),
                 num(r.dom1086), num(r.sub1334), num(r.poll1377n), num(r.sub1524n), num(r.cen1801),
                 PERL.index(r.depop_period), r.depop_text if pd.notna(r.depop_text) else "",
                 {"scheduled": 1, "not scheduled": 0}.get(r.scheduled_status, -1),
                 r.description_snippet if pd.notna(r.description_snippet) else "",
                 None if bad(m) else num(m.households1086), "" if bad(m) or pd.isna(m.openDomesdayPath) else m.openDomesdayPath,
                 r.parish_modern if pd.notna(r.parish_modern) else "", num(r.elev_m),
                 "" if bad(m) else m.dom_name])
site = {"sites": rows, "counties": CO, "types": TYPES, "typeLabels": [TYPE_LABEL[t] for t in TYPES], "periods": PERL}
json.dump(site, open(os.path.join(ROOT, "_site_data.json"), "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(R, open(os.path.join(D, "results.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in R.items() if k not in ("by_county", "decades", "full_counties")}, indent=0)[:9000])
