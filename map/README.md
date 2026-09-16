# map/ — the globe-only page (step 0 of the one-map rebuild)

`map/index.html` + `globe.css` + `globe.js`. MapLibre GL JS 5.6.0 (`vendor/`),
`projection: globe`, no UI, no data layers; the URL hash is the only control.
Nothing from the old pages (`shell.js`, `hig.css`) is loaded.

## Views

| hash | what | resulting camera (1280×744) |
|---|---|---|
| `#ll=30,125&spn=50,60` | MapKit-style region, fitted like `MKMapSnapshotter` (whole region visible, limiting axis decides) | center 125, 33.48 · zoom 3.12 · globe radius 536 px |
| `#3.12/33.48/125` | the same, in MapLibre's own hash | |
| `#2.3/20/140` | whole globe, radius 321 px | |

Light / dark follow `prefers-color-scheme`.

## Layers (bottom → top) and where every number comes from

| layer | data | colour / size |
|---|---|---|
| `background` | — | shallowest ocean band (`palette-ocean.json` 0–200 m) so coast gaps between NE land and NE ocean read as shelf |
| `bathy-<depth>` ×12 | Natural Earth 10m Bathymetry v4.1.0 (public domain), one file per level so they parse in parallel and paint progressively; DP 0.02° (<3000 m) / 0.04° (abyssal), `data/bathy-*.geojson` 10 MB total | `palette-ocean.json` band medians, light and dark |
| `land` | Natural Earth 10m Land v5.1.1, simplified 0.01°, `data/land.geojson` 2.5 MB | `palette-land.json` humid flat tint |
| `climate` (raster image) | Beck et al. 2023 Köppen-Geiger 1991–2020 0.1° (CC BY 4.0) → `data/climate-{light,dark}.png`, Web-Mercator 4096², masked to NE land | Köppen class → tint by majority vote of `palette.py`'s 705 samples (BWk/BWh very-dry, BSk/Dwc/Cwb semi-humid, ET/EF high-grey, rest humid) |
| `hillshade` | AWS Terrain Tiles (terrarium) raster-dem | azimuth 260° (fit on Apple's Alps render, r 0.59); exaggeration **calibrated**: 0.07 @ z8.7 (luminance amplitude 14.2 vs Apple 14.3), 0.047 @ z3.1 (5–95 % shading range 5.8 vs Apple's ≈6 flat-vs-slope drop) — `pipeline/basemap/calibrate.py` |
| limb glow (canvas) | — | radial profile replayed from `native.png` row 800: 60 pt inner haze + 7 pt outer fall-off to `#000000` |
| labels (DOM markers) | NE 10m admin_0_countries `LABEL_X/Y`, `MIN/MAX_LABEL`; marine polys (ocean/sea/bay/gulf) and continent polys → spherical interior point (cos-lat-weighted mean of grid samples, snapped inside; fixes Arctic Ocean landing in the Yellow Sea) | `labels-globe.json`: continent heavy 17.4 pt +2.6 tracking `#955e8d`; country heavy 11 pt `#8c608a` white stroke 1.2 px; ocean/sea semibold italic 14 / 11 pt `#206aa1` (+0.9); dark colours from the dark render. Font `-apple-system` stack. Zoom visibility = NE's `min_label..max_label`; in-front-of-globe and inside-the-disc checked every frame; greedy collision on projected boxes after `idle` |
| stars (canvas) | — | 8.6 per 100×100 pt, 1.2 pt squares, grey p10/p50/p90 = 53/137/194 from `native.png` |

`data/meta.json` carries all of it (written by `pipeline/basemap/globe-data.py`; calibration by `calibrate.py`).

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

* **Apple's globe is a different style sheet** (`globe-default-*.styl`), not the flat one the snapshotter
  renders: in `native.png` the Philippine Sea centre is `rgb(121,189,233)` where the flat palette says
  `rgb(10,149,233)`, Bay of Bengal `154,210,245` vs `29,174,247`. This page uses the flat palette as
  tasked, so the ocean reads darker/more saturated than the App's globe. Next step: fit the globe camera
  on `native.png` from city-dot positions and sample the globe palette by depth band the same way.
* `HAZE_ALPHA = 0.5` (inner-haze opacity at the limb) is the one constant without a measurement: the
  profile was sampled over ocean only, so haze colour and opacity cannot be separated. Needs a Maps
  screenshot with land at the limb.
* NE 10m has no deep/trench points → deep names (Challenger Deep …) are not drawn.
* Labels are DOM markers with greedy collision, no curved or wrapped country names, constant pt size.
* MapLibre's own atmosphere is off (`atmosphere-blend: 0`) — it is sun-lit on one side, Apple's is uniform.
