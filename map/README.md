# map/ — the globe-only page (step 0 of the one-map rebuild)

`map/index.html` + `globe.css` + `globe.js`. MapLibre GL JS 5.6.0 (`vendor/`),
`projection: globe`, no UI, no data layers; the URL hash is the only control.
Nothing from the old pages (`shell.js`, `hig.css`) is loaded.

## Views

| hash | what | resulting camera (1280×744) |
|---|---|---|
| `#ll=30,125&spn=50,60` | MapKit-style region, fitted like `MKMapSnapshotter` (whole region visible, limiting axis decides) | center 125, 33.48 · zoom 3.12 · globe radius 536 px |
| `#3.12/33.48/125` | the same, in MapLibre's own hash | |
| `#2.3/20/140` | whole globe | |
| `#3.12/30.14/124.45` | **acceptance view**: the App's camera for `~/Money/styl-work/native-nosidebar.png` (globefit on 10 city markers, rms 4.9 px @2x: lat0 30.14, lng0 124.45, D 2.894). The page uses the App's perspective — vertical fov 26.7° (= 2·atan(372/1569.5) from the fitted focal length at 744 pt) — so the silhouette (r 573 vs 578 @1x) and the centre scale match at once; `&fov=36.87` restores MapLibre's default | diff>40 vs the App: 24.5 % at the old `#3.285/30.18/116.15` → 11.5 % (camera) → 7.45 % (+ fov 26.7, shelf) → 7.65 % (+ lit sphere: ocean pixels now within ±5 of the App along the centre row) → 7.7 % with cities/deeps/graticule labels (labels differ in placement by nature) |

Hash extras (after `&`): `pal=flat|globe`, `fov=<deg>`, `padr/padl/padt/padb=<px>`. Note `native.png` (sidebar open) has its camera centre at lng 116.15 because the App keeps the *visible* centre at the URL's 125 — a view aligned to it is not aligned to the sidebar-closed screenshot.

| `#ll=34.69,135.50&spn=0.09,0.15` | **Osaka acceptance view** (flat, z ≈ 12.2) vs `~/Money/styl-work/snap-osaka12{,-dark}.png` | diff>40: 18.7 % light, 13.5 % dark (2026-09-16; labels are Japanese here, English in the snapshots) |

Light / dark follow `prefers-color-scheme`.

## Globe → flat hand-over (z 5–6)

One MapLibre style holds both worlds. `projection.type` is the expression `['interpolate', ['linear'], ['zoom'], 5, 'vertical-perspective', 6, 'mercator']` (MapLibre's own `globe` preset does the same at 11→12), so the sphere flattens exactly while the globe layers (bathymetry, shelf, land, climate, graticule, DOM labels, limb/shading canvases) fade out with `interpolate zoom 5→1, 6→0` and the data session's flat style (`map/style-flat-{light,dark}.json`, OpenFreeMap vector tiles, `pipeline/basemap/styl/to_maplibre.py`) fades in with the mirror ramp; its layers get `minzoom ≥ 5` and ids prefixed `flat-`. The hill-shade stays through both (calibrated at z 3 and z 9) and is inserted above the flat fills, below its lines and labels. Flat labels use the style's Noto glyphs (MapLibre symbol layers cannot use the system font); the globe's DOM labels stay `-apple-system`.

## Layers (bottom → top) and where every number comes from

| layer | data | colour / size |
|---|---|---|
| `background` | — | shallowest ocean band (`palette-ocean.json` 0–200 m) so coast gaps between NE land and NE ocean read as shelf |
| `bathy-<depth>` ×12 | Natural Earth 10m Bathymetry v4.1.0 (public domain), one file per level so they parse in parallel and paint progressively; DP 0.02° (<3000 m) / 0.04° (abyssal), `data/bathy-*.geojson` 10 MB total | light: **`palette-globe.json`** band colours (the App's globe style, sampled off its screenshot through the fitted camera, `centre` = r/limb ≤ 0.5); `#…&pal=flat` or dark: `palette-ocean.json` band medians |
| `shelf` (raster image, globe palette only) | AWS terrarium z5 depths (ETOPO1 in the ocean) → `data/shelf-globe.png`, Web-Mercator 4096², pixels −200 m < depth < 0 | `palette-shelf.json`: the App's shelf graded by depth, sampled through the camera (0–10 m `#c5e9fc` … 150–200 m `#bae1f7`), piecewise-linear ramp; drawn above the 0–200 fill and below the deeper NE fills |
| `land` | Natural Earth 10m Land v5.1.1, simplified 0.01°, `data/land.geojson` 2.5 MB | humid tint of the same palette (globe `#e9f6d8`, flat `#bfe98b` / dark `#377b64`) |
| `climate` (raster image) | Beck et al. 2023 Köppen-Geiger 1991–2020 0.1° (CC BY 4.0) → `data/climate-{globe,light,dark}.png`, Web-Mercator 4096², masked to NE land | Köppen class → tint by majority vote of `palette.py`'s 705 samples (BWk/BWh very-dry, BSk/Dwc/Cwb semi-humid, ET/EF high-grey, rest humid); tint colours from the palette in use |
| `hillshade` | AWS Terrain Tiles (terrarium) raster-dem | azimuth 260° (fit on Apple's Alps render, r 0.59); exaggeration **calibrated**: 0.07 @ z8.7 (luminance amplitude 14.2 vs Apple 14.3), 0.047 @ z3.1 (5–95 % shading range 5.8 vs Apple's ≈6 flat-vs-slope drop) — `pipeline/basemap/calibrate.py` |
| lit sphere (canvas) | — | `shading-globe.json`: App brightness = a + b·(n·L), a 0.753, b 0.317, L (−0.436, −0.251, 0.864) (light from screen-left/below), r² 0.85 on 100 714 deep-ocean samples of the App screenshot; painted per pixel (black/white overlay) normalised to 1 at the centre normal |
| limb haze (canvas) | — | `haze-globe.json`: overlay colour + opacity per r/limb bin solved from land and sea pixels on the same limb (`native-limb-land-light.png`): r 0.925 a 0.19 `#484f84` → 0.99 a 0.94 `#94a3b6`; outer 7 pt fall-off from the `native.png` row-800 profile |
| graticule (line) | `data/graticule.geojson`: tropics + equator | dashed `#6b8098` 1 pt, 3/3 pt (darkest dash pixels of the App screenshot); labels at the App's anchors (Tropic of Cancer 23.4°N 135.2°E from `native-nosidebar.png` px 773,462; Equator 64.9°E from `native.png`) |
| labels (DOM markers) | NE 10m admin_0_countries `LABEL_X/Y`, `MIN/MAX_LABEL`; marine polys (ocean/sea/bay/gulf) and continent polys → spherical interior point (cos-lat-weighted mean of grid samples, snapped inside; fixes Arctic Ocean landing in the Yellow Sea); **cities** `data/cities.geojson` (data session; `min_zoom`, `globe_rank` ≤ 3, capitals separate); **deeps** `data/undersea.geojson` cls 1 type Deep (22 points; NE has none) | globe palette → the App-globe measurements (`labels-globe.json` kinds `app-*`, measured on `native-nosidebar.png` @2x): country black 10.5 pt `#c0a0b5` no halo (size follows the .styl Country-Label-Medium height curve anchored at z 3.12), capital heavy 11.7 pt `#505c73` white stroke 1.5 px@2x + ring marker 3.5 pt, city semibold 11.4 pt `#9f9c98`, sea semibold italic 11.0 pt `#5189bd` (+1.1), deep semibold 10.1 pt `#476ba8` ▾, graticule regular 11 pt `#708ca6`. Flat palette → the snapshotter measurements (continent heavy 17.4 pt `#955e8d`; country heavy 11 pt `#8c608a` white stroke; ocean/sea semibold italic 14 / 11 pt `#206aa1`). Font `-apple-system` stack. Zoom visibility = NE's `min_label..max_label`; in-front-of-globe and inside-the-disc checked every frame; greedy collision on projected boxes after `idle` |
| stars (canvas) | — | 8.6 per 100×100 pt, 1.2 pt squares, grey p10/p50/p90 = 53/137/194 from `native.png` |

Two metadata files: `data/meta.json` = **data sources only** (shared with the data session, which adds `sources.physical/undersea/cities`; `globe-data.py` updates only its own keys) and `map/meta-ui.json` = palettes, camera, haze, shading, label styles, hill-shade calibration (UI session; written by `globe-data.py`, calibration by `calibrate.py`). `globe.js` merges the two.

Regression noted 2026-09-16: from ab63014 to f206b1c `globe-data.py` rebuilt `meta.json` wholesale and dropped `hillshade.exaggeration_by_zoom` (the page fell back to `{4: 0.1, 9: 0.5}`); restored from 98c0d1a into `meta-ui.json`, which is now merge-preserving.

## Build / run

```
python3 pipeline/basemap/palette.py          # renders + fits the palettes (needs macOS, network)
python3 pipeline/basemap/labels.py           # label typography + background
python3 pipeline/basemap/globe-data.py       # NE / Köppen -> map/data/*
python3 pipeline/rangeserver.py 8792 &       # then open http://127.0.0.1:8792/map/index.html#ll=30,125&spn=50,60
python3 pipeline/basemap/calibrate.py        # hill-shade exaggeration against the Apple amplitudes (headless Chrome)
python3 pipeline/basemap/shot.py <url> 1280 744 out.png [--dark]   # headless screenshot helper
```

## Known gaps (2026-09-16)

* **Two palettes.** Apple's globe is its own style sheet (`globe-default-*.styl`), not the flat one the
  snapshotter renders (Philippine Sea centre `rgb(121,189,233)` in the App vs `rgb(10,149,233)` flat).
  `pipeline/basemap/globefit.py` fits the App's globe camera on `native.png` — silhouette circle from
  174 rows (rms 0.3 px: centre 1265.0, 743.4, r 1156.3 @2x) plus 11 city markers matched to Natural
  Earth populated places (rms 4.9 px, max 7.7; lat0 30.18, lng0 116.15, D 2.88 earth radii ≈ 11 960 km)
  — and samples the globe colours by NE depth band and Köppen tint (`ui/basemap/palette-globe.json`).
  Light mode uses it by default; `pal=flat` in the hash switches to the flat palette; dark mode has only
  the flat dark palette (the screenshot is light). The data session's `.styl` decode will give a third,
  exact set — keep all of them.
* Camera-model residual: Tokyo/Sapporo sit ~7–10 px (2x) off after the fit while the SE-Asian anchors
  are within 3 px — a pin-hole camera aimed at the sphere centre is not exactly Apple's projection.
  Fine for colour sampling by band, not for pixel-exact registration.
* `HAZE_ALPHA = 0.5` (inner-haze opacity at the limb) is the one constant without a measurement: the
  profile was sampled over ocean only, so haze colour and opacity cannot be separated. Needs a Maps
  screenshot with land at the limb.
* NE 10m has no deep/trench points → deep names (Challenger Deep …) are not drawn.
* Labels are DOM markers with greedy collision, no curved or wrapped country names, constant pt size.
* MapLibre's own atmosphere is off (`atmosphere-blend: 0`) — it is sun-lit on one side, Apple's is uniform.
