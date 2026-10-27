"""Step 5. Build index.html from code/page_template.html.

Every number in the text is a {{path|format}} token filled from data/results.json, so the page cannot
drift from the analysis. The map data (_site_data.json from step 4) and a slim copy of results.json are
embedded so the page works as a single file. Formats: int, f0, f1, f2, pct, pct1, money (pence to
pounds, shillings and pence), ordpct (0.33 -> "33rd"), raw.

Usage:
    python3 code/05_build_page.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json"), encoding="utf-8"))
SITE_PATH = os.path.join(ROOT, "_site_data.json")
SITE = open(SITE_PATH, encoding="utf-8").read()
# the source descriptions use typographic dashes; show them as plain hyphens on the page
SITE = SITE.replace("–", "-").replace("—", ", ").replace("--", "-")
tpl = open(os.path.join(ROOT, "code", "page_template.html"), encoding="utf-8").read()


def get(path):
    v = R
    for k in path.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def money(p):
    d = round(p)
    L, s, dd = d // 240, (d % 240) // 12, d % 12
    return " ".join(x for x in [f"£{L}" if L else "", f"{s}s" if s else "", f"{dd}d" if dd else ""] if x) or "0"


def fmt(v, f):
    if f is None or f == "raw":
        return str(v)
    return {"int": lambda: f"{round(v):,}", "f0": lambda: f"{round(v):,}", "f1": lambda: f"{v:.1f}",
            "f2": lambda: f"{v:.2f}", "pct": lambda: f"{round(v * 100)}%", "pct1": lambda: f"{v * 100:.1f}%",
            "money": lambda: money(v), "ordpct": lambda: ordinal(round(v * 100))}[f]()


def fill(text):
    return re.sub(r"\{\{([^}|]+)(\|(\w+))?\}\}", lambda m: fmt(get(m.group(1)), m.group(3)), text)


if __name__ == "__main__":
    html = fill(tpl)
    slim = {k: R[k] for k in ["dom_county_share", "by_county", "loss_by_size", "env", "traj_examples", "decades",
                              "stories", "causes", "desc_n"]}
    html = html.replace("/*SITE*/", SITE).replace("/*RESULTS*/", json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
    assert "{{" not in html
    for bad in ("–", "—"):
        assert bad not in html, bad
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html", len(html.encode()), "bytes")
    md = os.path.join(ROOT, "code", "README_template.md")
    if os.path.exists(md):
        open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8").write(fill(open(md, encoding="utf-8").read()))
        print("README.md written")
