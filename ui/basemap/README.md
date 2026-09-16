# Basemap numbers measured off Apple's renderer

**Status 2026-09-16 evening:** the decoded originals (SHADER-NUMBERS.md, RENDER-PIPELINE.md, the `.styl` sheets) now drive
`map/globe.js`; the sampled files below are *verification* only, except where no decoded source exists yet
(the globe's pastel palette below z 4.6, the globe label typography — `map/meta-ui.json → pending`). Two decoded files
live here too: `ground.json` (`pipeline/basemap/ground.py`: Landcover sheet colours, groundSettings HSV cells,
Köppen → climate codes, MODIS IGBP → Apple classes, raster bounds) and `geolines.json` (`pipeline/basemap/geolines.py`:
Geolines-Tropics/Equator/Polar styles).

Apple's map style sheets (`.styl`) are compiled binaries, but Apple's renderer
runs locally (`MKMapSnapshotter` / `MKMapView`, VectorKit). These files treat
it as a measuring instrument: render, sample pixels at coordinates whose
depth / elevation is known from public-domain data, and fit. Nothing here is
hand-tuned; every number carries the image, pixel and render time it came from.
The renders themselves are Apple imagery and stay in the gitignored
`pipeline/basemap/raw/renders/`; re-render with the recorded args to reproduce.

| file | what | generator |
|---|---|---|
| `palette-ocean.json` | depth band (Natural Earth 10m bathymetry levels) → RGB, light + dark, n and residual per band, 200 samples | `pipeline/basemap/palette.py` |
| `palette-land.json` | land tint classes (humid / semi-humid / dry / very-dry / high-grey) × hill-shade class → RGB, light + dark; hill-shade light azimuth; VectorKit `groundSettings.json` exaggeration table | `pipeline/basemap/palette.py` |
| `palette-globe.json` | the App's **globe** style (a different style sheet the snapshotter cannot render): ocean by depth band and land by Köppen tint, sampled from the Maps App screenshot `native.png` through a fitted globe camera (silhouette circle + 11 city markers ↔ NE populated places, rms 4.9 px @2x); `centre` stats = r/limb ≤ 0.5, least hazed; radial haze trend of deep ocean by r/limb | `pipeline/basemap/globefit.py` |
| `labels-globe.json` | globe-scale label typography (continent, country, ocean/sea, deep, undersea feature, graticule): SF weight, size pt, tracking pt, glyph / halo colour light + dark; space background, limb glow and star field from the Maps App screenshot | `pipeline/basemap/labels.py` |

## Run

```
swiftc -O pipeline/basemap/sample.swift      -o pipeline/basemap/raw/sample
swiftc -O pipeline/basemap/textmetrics.swift -o pipeline/basemap/raw/textmetrics
swiftc -O pipeline/basemap/labelshot.swift   -o pipeline/basemap/raw/labelshot   # 2x live capture, needs an unlocked Mac
python3 pipeline/basemap/palette.py                     # renders, downloads NE + terrarium, fits
python3 pipeline/basemap/labels.py --debug              # writes labels-globe.json, crops in raw/labels-debug/
```

## View and sources

* 2x live captures (`labelshot.swift`) must run under `caffeinate -d -u -i`: the display sleeps every few minutes (pmset log 2026-09-16 12:27:59 off / 12:29:01 on / 12:36:42 off) and a sleeping display renders nothing; a *locked* screen (CGSSessionScreenIsLocked) blocks screencapture entirely — the tool exits 3/4/5 instead of writing a blank PNG. Check: `/private/tmp/…/disp` or `pmset -g log | grep "Display is turned"`.
* View: `ll=30,125 spn=50,60 @1280x744` (same as the Maps App window the
  acceptance session screenshots); labels also use `ll=20,150 spn=120,170`
  for continent and ocean names that only appear further out.
* Bathymetry classes: Natural Earth 10m Bathymetry v4.1.0, public domain,
  <https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip>.
* Continuous depth / elevation / slope: AWS Terrain Tiles (terrarium encoding),
  <https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png>,
  sources listed at <https://github.com/tilezen/joerd/blob/master/docs/data-sources.md>.
* Exaggeration: `/System/Library/PrivateFrameworks/VectorKit.framework/Versions/A/Resources/groundSettings.json`.
* Space / limb / stars: `~/Money/styl-work/native.png` (Maps App globe screenshot, 2x).

## Headline numbers (2026-09-16, macOS 27.0 26A428)

Ocean, light → dark (median of the band, n≈23 each; residual is RMS RGB distance inside the band):

| depth m | light | dark |
|---|---|---|
| 0–200 | `#6cc9fa` | `#172b68` |
| 200–1000 | `#4abdfa` | `#0d2255` |
| 1000–2000 | `#33b7f9` | `#0d1d4f` |
| 2000–3000 | `#1daef7` | `#0d1d44` |
| 3000–4000 | `#0da3f0` | `#0d1738` |
| 4000–5000 | `#0d99ec` | `#000d2f` |
| 5000–6000 | `#0a95e9` | `#000d2a` |
| 6000–7000 | `#0d92e7` | `#000d27` |
| ≥7000 | `#0d8de6` (ramp saturates; identical pixels) | `#000d22` |

Land base tints (flat ground), light / dark: humid `#bfe98b` / `#377b64`,
semi-humid `#e1eda7` / `#397361`, dry `#ece8ab` / `#407662`, very dry
`#ffe9e1` / `#7e7f6e`, high plateau grey `#f4f1e6` / `#777966`. At this zoom
hill-shade barely moves the light colour (humid lit/shaded `#b0df8b`/`#aee28b`
vs flat `#bfe98b`; the dark render moves more, `#156c6b` vs `#377b64`); at
country zoom the renderer's light comes from azimuth ≈260° (r = 0.59 on 8188
Alps samples, curve in the json).

Labels (SF; web fallback `-apple-system, system-ui`):

| kind | weight (consensus) | size pt | tracking pt | light | dark | halo |
|---|---|---|---|---|---|---|
| continent (ASIA) | heavy | 17.4 | +2.6 | `#955e8d` | `#a496a5` | none |
| country | heavy | 10.3–12.3 (median 11.0) | ≈0 | `#8c608a` | `#bc99ad` | white `#f0f6e7`, ≈1.2 px @2x |
| ocean / sea, italic | semibold | sea 11.0, ocean 12.6–15.4 | +0.9 | `#206aa1` (semi-transparent over the water) | `#3d73b6` | none |
| deep (Ramapo Deep) | bold | 10.8 | ≈0 | `#476ba8` | `#3a5f9a` | none |
| undersea feature, upper, along path | black | 7.9 | +4.7 | `#3770a5` | `#38609f` | none |
| graticule (Tropic of Cancer) | bold | 8.8 | +0.7 | `#4a5676` | `#7e94c7` | faint |

Background: space is pure `#000000` (99.8 % of gutter pixels), stars are
neutral 1.5 pt dots at ≈8.6 per 100×100 pt, the limb glow falls from
`#7690a8`-ish to black in ≈7 pt (`labels-globe.json` → `background`).

Known limits: the 2x live capture works only while the Mac is unlocked (the
wide view is 1x: ±0.35 pt); weight from stem/ink density is ±1 step; the land
tints are classified by hue from the renderer's own output because no
land-cover raster was sampled.
