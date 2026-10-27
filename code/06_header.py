"""Step 6. Render header.png (1200 x 630 social card) with Playwright Chromium.

Fonts: pass a folder holding FrauncesVar.ttf, SourceSerif4-Regular.ttf and IBMPlexMono-Regular.ttf /
-Medium.ttf as FONT_DIR; otherwise system serif fonts are used.
Usage:
    FONT_DIR=/path/to/fonts python3 code/06_header.py
"""
import json
import math
import os

import pandas as pd
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.environ.get("FONT_DIR", "")
R = json.load(open(os.path.join(ROOT, "data", "results.json")))
L = pd.read_csv(os.path.join(ROOT, "data", "lost_villages.csv"))
COL = {"Before 1348": "#A898D8", "1348 to 1449": "#F07A4C", "1450 to 1549": "#E8B640", "1550 to 1699": "#6CC096", "1700 onwards": "#71A9E6"}
k = math.cos(math.radians(53))
x0, x1, y0, y1 = L.lon.min() * k, L.lon.max() * k, -L.lat.max(), -L.lat.min()
H = 590
W = H * (x1 - x0) / (y1 - y0)
dots = []
for _, r in L.sort_values("depop_period", key=lambda s: s.isin(COL.keys())).iterrows():
    x, y = (r.lon * k - x0) / (y1 - y0) * H, (-r.lat - y0) / (y1 - y0) * H
    c = COL.get(r.depop_period)
    dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3.2 if c else 2.2}" fill="{c or "#C9CCB8"}" fill-opacity="{0.95 if c else 0.33}"/>')
ff = ""
if FD:
    ff = "".join(f"@font-face{{font-family:'{n}';src:url('file://{FD}/{f}');font-weight:{w};}}" for n, f, w in [
        ("Fraunces", "FrauncesVar.ttf", "100 900"), ("Source Serif 4", "SourceSerif4-Regular.ttf", "400"),
        ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "400"), ("IBM Plex Mono", "IBMPlexMono-Medium.ttf", "500")])
html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{ff}
body{{margin:0;width:1200px;height:630px;background:#141612;color:#E9E9DE;overflow:hidden;position:relative;font-family:'Source Serif 4',Georgia,serif}}
.k{{position:absolute;left:70px;top:70px;font:500 15px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#A3A495;display:flex;gap:12px;align-items:center}}
.k b{{background:#EE7444;color:#141612;padding:7px 9px;font-weight:500}}
h1{{position:absolute;left:66px;top:112px;margin:0;font:900 96px/.9 Fraunces,Georgia,serif;letter-spacing:-.02em;font-variation-settings:"SOFT" 50}}
h1 em{{font-style:normal;color:#EE7444;display:block}}
p{{position:absolute;left:70px;top:420px;width:560px;margin:0;font-size:26px;line-height:1.36;color:#DCDCCF}}
.f{{position:absolute;left:70px;bottom:40px;font:400 14px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#7F8173}}
svg{{position:absolute;right:60px;top:20px}}
</style></head><body>
<div class="k"><b>Data study</b><span>History × data</span></div>
<h1>The villages<br>that <em>vanished</em></h1>
<p>{R['n_sites']:,} lost villages of England, mapped. The doomed were already smaller in 1086, and most emptied long after the Black Death.</p>
<div class="f">Dr Tristan Hotham · Independent researcher</div>
<svg width="{W:.0f}" height="{H}" viewBox="0 0 {W:.0f} {H}">{''.join(dots)}</svg>
</body></html>"""
tmp = os.path.join(ROOT, "_header.html")
open(tmp, "w").write(html)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file://") else r.abort())
    pg.goto("file://" + tmp)
    pg.wait_for_timeout(500)
    pg.screenshot(path=os.path.join(ROOT, "header.png"))
    b.close()
os.remove(tmp)
print("header.png written")
