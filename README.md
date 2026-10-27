# The Villages That Vanished

England's lost medieval villages: where they were, how big they were in 1086, and what the record says about when and why they emptied. All 2,222 sites in Beresford's Lost Villages (University of Hull), set against Domesday Book.

**Interactive version:** https://tristan-hotham.github.io/lost-villages/

**Paper:** https://doi.org/10.5281/zenodo.23677161

This repository holds the interactive page, the cleaned datasets, the computed results and the analysis code for a data study by Dr Tristan Hotham (Independent researcher, ORCID 0000-0003-4931-9349). Companion study: [Is Domesday Destiny?](https://tristan-hotham.github.io/domesday-destiny/).

## Headline results

- The gazetteer holds 2,222 sites: 2,000 deserted villages, 74 deserted hamlets and 52 shrunken, 13 shifted, 13 migrated and 70 doubtful sites. Most are in Yorkshire (374), Lincolnshire (220) and Northumberland (165).
- 1,110 Domesday places later became deserted villages or hamlets (8.6% of located places in the comparison). The share runs from 20% in Lincolnshire to almost none in the south-west and the Welsh border counties.
- The doomed were smaller in 1086: median 13 households against 17 for places that survived. Within their own county they sat at the 33rd percentile; 72% were below the county median.
- Risk of desertion peaked for middling places: 11% of places with 6 to 20 households were later deserted, against 2.5% of places with over 40.
- Setting barely differs within counties: on height, relief, distance to water and to Roman roads, the median deserted place ranks between the 50th and 55th percentile of its county.
- Of 299 sites with a usable presumed date (all in the 14 fully recorded counties), 20% of the dated weight falls in 1348 to 1449, 26% in 1450 to 1549, 28% in 1550 to 1699 and 20% from 1700 on. The busiest decade is the 1500s.
- Of 357 villages recorded in the 1377 poll tax (where the 1524 subsidy survives), 30% are not recorded in 1524.
- Of 542 written accounts, 68 mention enclosure or conversion to pasture, 63 emparking, 53 a monastic grange or landholder, 38 the Black Death or plague and 11 the sea or flooding. 119 of 540 sites with a recorded status are scheduled monuments.

## Files

- `index.html`: the interactive page (Leaflet map with filters and popups, charts). Data embedded; works as a single file.
- `header.png`: social card (1200 by 630).
- `data/lost_villages.csv`: one row per site (2,222): names, type, counties, parishes, checked position, scheduled status, every documentary field parsed into a value and a status (columns `<field>`, `<field>_any`, `<field>_status`), presumed depopulation date parsed into intervals and a period, last E179 document, setting (elevation, relief, distance to watercourse and Roman road), cause mentions, description snippet and full description.
- `data/lost_villages.geojson`: the same sites as points with key fields.
- `data/domesday_matches.csv`: the Domesday place matched to each site, with name score, shared references, distance and flags.
- `data/domesday_places_status.csv` and `data/domesday_lost_vs_survivors.csv`: every located Domesday place with its 1086 figures, setting, and group (lost, survivor, or other).
- `data/depopulation_dates.csv`: the 308 presumed dates as written and as parsed.
- `data/county_summary.csv`: sites per historic county.
- `data/results.json`: every number quoted on the page, README, paper, blog and collage.
- `code/01_parse.py` to `code/06_header.py`: the pipeline (see below). `code/page_template.html` and `code/README_template.md` are filled from `results.json`.
- `release/`: paper (PDF, LaTeX and figures), blog figures and post, Zenodo files. `reddit/`: the collage and its script.

## How to rerun

Needs Python 3 with pandas, numpy, scipy, pyproj, matplotlib and playwright, plus the inputs: the Hull feature-service JSON (`lost_villages_beresford.json`), the processed Domesday places from the companion project (`domesday-destiny/data/domesday_places.csv`), the elevation reader and tiles used by the `within-sight` project, OS Open Rivers and the corrected Itiner-e roads from `how-roman-is-your-road`.

```
python3 code/01_parse.py path/to/lost_villages_beresford.json
python3 code/02_match_domesday.py path/to/domesday_places.csv
python3 code/03_environment.py
python3 code/04_analyse.py
python3 code/05_build_page.py
python3 code/06_header.py
```

## Method in brief

- **Positions.** The service gives three positions per site. For 25 sites they disagree; I keep the one a second field confirms within 1 km, preferring the grid reference. The service's `ID` field is not unique, so sites are keyed by its `FID`.
- **Parsing.** Bare numbers are values. "896 (Holme with)" style entries count as recorded but are not used as sizes. "Not recorded" means absent from a surviving source; "No surviving record" and blanks are left out of denominators. Money is in pence.
- **Dates.** Ranges read as written; centuries as 100 years; early, mid and late as 40-year spans; "post X" as X to X + 49; vague text dropped. Each site's weight of one is spread evenly across its years.
- **Domesday matching.** Same name (after normalising) within 5 km, or a shared Domesday entry with a looser name match. Agreement with the gazetteer's own Domesday figure: within one for 78% of 898 sites. Matches where the site's name has a qualifier the Domesday name lacks (73) are left out of the comparison.
- **Causes.** Regular-expression searches of the 542 written accounts; a mention is not a verdict.

## Known limits

- The gazetteer is Beresford and Hurst's 1968 list. Later discoveries are not yet included, and coverage reflects search effort as well as history.
- Full documentary records, descriptions, dates and scheduled status exist only for 14 counties (540 sites): Bedfordshire to Durham alphabetically, Essex, Gloucestershire and the East Riding of Yorkshire.
- Tax sources are not like for like (the 1524 subsidy omits the poorest). Census figures can cover a whole parish.
- Domesday counts heads of household on manors; Yorkshire's record is thin and the far north was not surveyed.

## Sources and licence

- Beresford's Lost Villages, University of Hull, https://dmv.wordpress.hull.ac.uk/ (CC BY-NC-SA 4.0), from M. Beresford and J. Hurst's 1968 gazetteer.
- Domesday data: Hull Domesday Project, Professor J.J.N. Palmer, George Slater and the University of Hull (CC BY-NC-SA), via https://github.com/embabel-worlds/realm-domesday; place links from Open Domesday by Anna Powell-Smith, https://opendomesday.org/.
- Elevation: AWS Terrain Tiles by Mapzen/Tilezen (https://github.com/tilezen/joerd/blob/master/docs/attribution.md).
- OS Open Rivers: contains OS data © Crown copyright and database right (OGL v3).
- Roman roads: de Soto, P., Pažout, A., Brughmans, T. and others (2025), Itiner-e: a high-resolution dataset of roads of the Roman Empire, Scientific Data, https://zenodo.org/records/17122148 (CC BY 4.0), with the datum correction from the How Roman Is Your Road? project.
- Base map tiles on the page: Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community.

Because the main sources are CC BY-NC-SA, the derived data (`data/`) and the page text are released under CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/). The code is released under the MIT licence (see `LICENSE`).

## Citation

Hotham, T. (2026) *The Villages That Vanished: England's deserted medieval villages, Domesday Book and the record of desertion*. Zenodo. https://doi.org/10.5281/zenodo.23677161

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
