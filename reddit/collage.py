"""r/dataisbeautiful collage: reddit/lost_villages.png (2400 x 3000).
Reads data/lost_villages.csv and data/results.json, plus the ONS county outlines used by the
How Roman Is Your Road? project for the coastline. Fonts: Fraunces, Source Serif 4, IBM Plex Mono
from FONT_DIR (default: the scratchpad fonts folder used by the other collages).
Usage: python3 reddit/collage.py
"""
import json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
F = os.environ.get("FONT_DIR", "/tmp/claude-0/-home-claude/c232619d-81e0-53f3-9de6-41e973630753/scratchpad/fonts") + "/"
for f in ["FrauncesVar.ttf", "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "SourceSerif4-Regular.ttf", "SourceSerif4-Semibold.ttf", "SourceSerif4-It.ttf"]:
    fm.fontManager.addfont(F + f)
DISP = fm.FontProperties(fname=F + "FrauncesVar.ttf", weight=900)
SER, MONO = "Source Serif 4", "IBM Plex Mono"
BG, LAND, LAND2, FG, MUT, GHOST = "#24301F", "#2E3B28", "#29351F", "#EFEBDA", "#A9AE94", "#E6E2C8"
PCOL = {"Before 1348": "#B7A6EA", "1348 to 1449": "#FF7A4A", "1450 to 1549": "#F2C14E", "1550 to 1699": "#77D19E", "1700 onwards": "#7FB6F0"}
ACC = "#F2C14E"

R = json.load(open(os.path.join(ROOT, "data", "results.json")))
L = pd.read_csv(os.path.join(ROOT, "data", "lost_villages.csv"))
tr = Transformer.from_crs(4326, 27700, always_xy=True)
L["x"], L["y"] = tr.transform(L.lon.values, L.lat.values)

g = json.load(open(os.path.join(ROOT, "..", "how-roman-is-your-road", "data", "counties.geojson")))
PE, PO = [], []
for f in g["features"]:
    geos = f["geometry"]["geometries"] if f["geometry"]["type"] == "GeometryCollection" else [f["geometry"]]
    for geo in geos:
        polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]] if geo["type"] == "Polygon" else []
        for poly in polys:
            a = np.array(poly[0])
            if len(a) < 4:
                continue
            x, y = tr.transform(a[:, 0], a[:, 1])
            (PE if f["properties"].get("nation") == "England" else PO).append(Polygon(np.c_[x, y], closed=True))

fig = plt.figure(figsize=(12, 15), dpi=200, facecolor=BG)
# ---------------------------------------------------------------- title
fig.text(0.045, 0.968, "The villages that vanished", fontproperties=DISP, fontsize=52, color=FG, va="top")
fig.text(0.047, 0.912, f"England's {R['n_sites']:,} lost medieval villages, mapped from Beresford's gazetteer and set against\n"
         "Domesday Book. Were they doomed from the start, and was it really the Black Death?",
         family=SER, fontsize=15.5, color=FG, va="top", linespacing=1.4)

# ---------------------------------------------------------------- hero map
ax = fig.add_axes([0.0, 0.315, 0.62, 0.575]); ax.set_facecolor(BG)
ax.add_collection(PatchCollection(PO, facecolor=LAND2, edgecolor="none", zorder=0))
ax.add_collection(PatchCollection(PE, facecolor=LAND, edgecolor="#3A4933", lw=0.4, zorder=0))
und = L[~L.depop_period.isin(PCOL)]
ax.scatter(und.x, und.y, s=55, c=GHOST, alpha=0.06, lw=0, zorder=2)          # halo
ax.scatter(und.x, und.y, s=5, c=GHOST, alpha=0.55, lw=0, zorder=3)           # ghost dot
for k, c in PCOL.items():
    q = L[L.depop_period == k]
    ax.scatter(q.x, q.y, s=120, c=c, alpha=0.16, lw=0, zorder=4)
    ax.scatter(q.x, q.y, s=13, c=c, alpha=0.98, lw=0, zorder=5)
ax.set_xlim(135000, 660000); ax.set_ylim(0, 670000); ax.set_aspect("equal"); ax.axis("off")
for nm, cty, dx, dy, txt in (("Wharram Percy", "Yorkshire", -150000, 42000, "Wharram Percy\n30 homes in 1368, 16 by 1435"),
                             ("Ravenserod", "Yorkshire", 2000, -95000, "Ravenserod\ntwo-thirds lost\nto the sea by 1346"),
                             ("Caythorpe", "Yorkshire", 25000, 60000, "Caythorpe\n300 acres enclosed\nfor sheep, 1517")):
    r = L[(L.name == nm) & (L.county == cty)].iloc[0]
    ax.annotate(txt, (r.x, r.y), (r.x + dx, r.y + dy), family=MONO, fontsize=10.5, color=FG, linespacing=1.3,
                arrowprops=dict(arrowstyle="-", color=FG, lw=0.8, shrinkA=2, shrinkB=3), ha="left", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.35", fc=BG, ec="none", alpha=0.82))
# legend
lx, ly = 0.05, 0.835
fig.text(lx, ly + 0.012, "PRESUMED DATE OF DEPOPULATION", family=MONO, fontsize=10, color=MUT)
items = [("No date in the record", GHOST, 0.6)] + [(k, c, 1) for k, c in PCOL.items()]
for i, (lab, c, a) in enumerate(items):
    yy = ly - 0.0105 - i * 0.0155
    fig.patches.append(matplotlib.patches.Circle((lx + 0.006, yy + 0.003), 0.0042, transform=fig.transFigure, color=c, alpha=a, figure=fig))
    n = R["period_counts_mid"].get(lab, R["period_counts_mid"]["No date given"] + R["period_counts_mid"]["No usable date"] if i == 0 else 0)
    fig.text(lx + 0.018, yy, f"{lab}  {n:,}", family=MONO, fontsize=11, color=FG, va="center")

# ---------------------------------------------------------------- headline numbers
tx = fig.add_axes([0.63, 0.31, 0.35, 0.545]); tx.axis("off")
notes = [(f"{R['hh_lost_median']:.0f} v {R['hh_surv_median']:.0f}", "median households in 1086 in places\nlater deserted, against places that\nsurvived. The doomed began smaller."),
         (f"{R['dom_county_share'][0]['share'] * 100:.0f}%", f"of {R['dom_county_share'][0]['county']}'s Domesday places later\nvanished. In Devon and Cornwall,\nalmost none did."),
         (f"{R['share_after_1450'] * 100:.0f}%", "of dated depopulation came after 1450.\nOnly " f"{R['periods'][1]['share'] * 100:.0f}% falls in the century\nafter the Black Death."),
         (f"{R['causes'][0]['n']}", f"written accounts mention enclosure\nor pasture; {R['causes'][2]['n']} mention plague\n(of {R['desc_n']} sites described).")]
for (big, small), y in zip(notes, [1.0, 0.75, 0.50, 0.25]):
    tx.text(0, y, big, fontproperties=DISP, fontsize=40, color=ACC, va="top", transform=tx.transAxes)
    tx.text(0, y - 0.088, small, family=SER, fontsize=13, color=FG, va="top", transform=tx.transAxes, linespacing=1.3)

# ---------------------------------------------------------------- bottom row
fig.text(0.05, 0.287, "WHEN THE RECORD SAYS THEY EMPTIED", family=MONO, fontsize=11, color=MUT)
fig.text(0.05, 0.271, f"{R['dated_parsed']} dated sites, each spread over its presumed range; sites per decade", family=SER, fontsize=11.5, color=FG)
a1 = fig.add_axes([0.065, 0.085, 0.53, 0.165]); a1.set_facecolor(BG)
dec = np.array(R["decades"])
cols = [list(PCOL.values())[0 if y < 1348 else 1 if y < 1450 else 2 if y < 1550 else 3 if y < 1700 else 4] for y in dec[:, 0]]
for a, b, c, t, yy, ha, xx in ((1348, 1450, "#FF7A4A", "Black Death century", 12.0, "right", 1446), (1450, 1550, "#F2C14E", "enclosure century", 10.4, "left", 1454)):
    a1.axvspan(a, b, color=c, alpha=0.10, lw=0)
    a1.text(xx, yy, t, ha=ha, va="bottom", family=MONO, fontsize=10.5, color=c)
a1.bar(dec[:, 0] + 5, dec[:, 1], width=8.6, color=cols)
a1.set_xlim(1100, 2000); a1.set_ylim(0, 13.4)
for s in ("top", "right", "left"):
    a1.spines[s].set_visible(False)
a1.spines["bottom"].set_color(MUT); a1.tick_params(colors=MUT, labelsize=11, length=3)
a1.set_xticks(range(1100, 2001, 100)); a1.set_xticklabels([str(y) if y % 200 == 0 else "" for y in range(1100, 2001, 100)], family=MONO, color=FG)
a1.set_yticks([0, 5, 10]); a1.set_yticklabels(["0", "5", "10"], family=MONO, color=MUT)

fig.text(0.665, 0.287, "WHO WAS AT RISK IN 1086", family=MONO, fontsize=11, color=MUT)
fig.text(0.665, 0.271, "Share of Domesday places later deserted,\nby households recorded in 1086", family=SER, fontsize=11.5, color=FG, va="top")
a2 = fig.add_axes([0.69, 0.085, 0.28, 0.14]); a2.set_facecolor(BG)
rows = R["loss_by_size"]
v = [r["share"] * 100 for r in rows]
a2.bar(range(5), v, color=[ACC if x == max(v) else "#C9C29A" for x in v], width=0.68)
for i, x in enumerate(v):
    a2.text(i, x + 0.35, f"{x:.0f}%" if x >= 3 else f"{x:.1f}%", ha="center", family=MONO, fontsize=10.5, color=FG)
a2.set_xticks(range(5), ["1-5", "6-10", "11-20", "21-40", "41+"], family=MONO, fontsize=10.5, color=FG)
a2.set_ylim(0, 14); a2.set_yticks([])
for s in ("top", "right", "left"):
    a2.spines[s].set_visible(False)
a2.spines["bottom"].set_color(MUT); a2.tick_params(colors=MUT, length=0)

# ---------------------------------------------------------------- footer
fig.text(0.045, 0.018, "Data: Beresford's Lost Villages, University of Hull (CC BY-NC-SA 4.0); Hull Domesday Project data, J.J.N. Palmer, G. Slater and the\n"
         "University of Hull (CC BY-NC-SA). Dates and descriptions exist only for the " f"{R['n_full_counties']} fully documented counties; the gazetteer is the 1968 list.\n"
         "Coastline: ONS boundaries, contains OS data © Crown copyright. Analysis and chart: Tristan Hotham, with Python and matplotlib.",
         family=MONO, fontsize=9, color=MUT, linespacing=1.45)
fig.savefig(os.path.join(HERE, "lost_villages.png"), facecolor=BG, dpi=200)
print("ok")
