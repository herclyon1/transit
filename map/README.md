# map/ — the one map's basemap (globe → flat) and shell skeleton

`map/index.html` + `globe.css` + `globe.js` + `globe-light.js` (+ `shell.js/css` for the Apple-shaped shell).
MapLibre GL JS 5.6.0 (`vendor/`), globe projection down to z 5, Mercator from z 6; the data session's flat
style (`style-flat-{light,dark}.json`) is appended under ids `flat-*`. The URL hash is the only control.

**Rule since 2026-09-16 evening (CLAUDE.md):** every colour and size is taken from Apple's own decoded files —
`basemap/data/shader/shader-numbers.json` (SHADER-NUMBERS.md, RENDER-PIPELINE.md), the `.styl` sheets
(`pipeline/basemap/styl/`), `groundSettings.json`, `stars.bin` — and screenshot sampling only verifies. What is
still sampled is listed in `meta-ui.json → pending` and at the end of this file.

## Views

| hash | what | resulting camera (1280×744) |
|---|---|---|
| `#ll=30,125&spn=50,60` | MapKit-style region, fitted like `MKMapSnapshotter` (whole region visible, limiting axis decides) | center 125, 33.48 · zoom 3.12 · globe radius 536 px |
| `#3.12/33.48/125` | the same, in MapLibre's own hash | |
| `#2.3/20/140` | whole globe | |
| `#3.12/30.14/124.45` | **globe acceptance view**: the App's camera for `~/Money/styl-work/native-nosidebar.png` (globefit on 10 city markers, rms 4.9 px @2x: lat0 30.14, lng0 124.45, D 2.894). The page uses the App's perspective — vertical fov 26.7° (= 2·atan(372/1569.5) from the fitted focal length at 744 pt) — so the silhouette (r 573 vs 578 @1x) and the centre scale match at once; `&fov=36.87` restores MapLibre's default | cmp-accept (diff>40): 24.5 % → 7.7 % (fitted lighting/haze, 2026-09-16 day) → **3.86 %** with the decoded lighting + rim (evening) |
| `#ll=36,138&spn=12,16` | **Japan acceptance view** (z 5.1, the overlay band) vs `snap-japan{,-dark}.png` | see the numbers table below |
| `#ll=34.69,135.50&spn=0.09,0.15` | **Osaka acceptance view** (flat, z ≈ 12.2) vs `snap-osaka12{,-dark}.png` | 7.08 % light / 7.89 % dark |

Hash extras (after `&`): `pal=flat|globe`, `fov=<deg>`, `padr/padl/padt/padb=<px>`, `over=<z0>,<z1>`, `ui=0` (hide the shell),
`m=<mode>`, `sel=<id>`. Note `native.png` (sidebar open) has its camera centre at lng 116.15 because the App keeps the *visible*
centre at the URL's 125 — a view aligned to it is not aligned to the sidebar-closed screenshot.

Light / dark follow `prefers-color-scheme`.

### Acceptance numbers (`pipeline/basemap/score-views.sh`, `styl-work/cmp-accept.py`, 2026-09-16 evening)

| view | 1e4edca (fitted / calibrated values, flat v5) | 333213b (decoded originals, flat v5) | now (decoded originals, **flat v6** 9a4415a) |
|---|---|---|---|
| globe `#3.12/30.14/124.45` | 4.35 % | 3.86 % | **3.74 %** |
| Japan light z 5.1 | 8.11 % (flat lines/labels at 10 % opacity: they faded in over 5–6) | 10.85 % (flat fully on: v5's 2.25 px purple expressways covered 59 000 px the App leaves plain — RENDER-PIPELINE 7.15) | **8.05 %** (6.95 % with the flat line + symbol layers hidden) |
| Japan dark z 5.1 | 7.69 % | 10.75 % | **7.72 %** (t = 20: 13.93 %) |
| Osaka light z 12.2 | 7.09 % | 7.08 % | **7.30 %** |
| Osaka dark z 12.2 | 7.90 % | 7.89 % | **8.11 %** (t = 20: 18.03 %) |

The dark numbers at threshold 20 come from `pipeline/basemap/cmpdiff.py --t 20` (same recipe as cmp-accept: luminance of |Δ| after
LANCZOS to 1280×744, toolbar column masked, denominator all pixels). Osaka moved with the flat style (v5 → v6: coast glow, rail ticks,
label fonts), not with this page.

## Shell (PLAN-ONE-MAP §4 skeleton, 2026-09-16)

`map/index.html` carries the Apple-shaped shell over the map, built from the Kit-audited components in
`ui/hig.css` (KIT-MAP vocabulary) with motion from `ui/sheet.js`; `map/shell.js` wires it, `map/shell.css` only lays it out.
No data, no functions — rows and the card are placeholder text.

* Mac (1280×744, `#3.12/30.14/124.45&sel=osaka-station`): sidebar 200 full height, XL search 170×36 at (15,47),
  section headers 32 Bold 11 grey, rows Medium 32 two-line, `目录 ›` grey 11 at (16, bottom 13); right column 36 glass buttons at right 8 / top 8 / gap 6
  (modes, locate, ±); place card 320 at 208/8/8: 28 round buttons at 12, title 22 Bold centred 48 from the top, main button 288×45,
  section header 15 Semibold, key-value rows 48 with hairlines, bottom capsule toolbar 36 with 3×28; Map Modes popover 320 r20 at right 58 / top 13
  (`styl-work/native-mapmodes.png`), **no close button — it closes on an outside click** (Maps.app popover behaviour; the iPhone sheet keeps its ×),
  and opening it keeps the place card (Maps.app does).
* **Materials (MATERIALS.md, 2026-09-16 evening; `ui/hig.css` §19):** Maps is a Catalyst app, so its chrome is system material, not a flat
  white alpha. Sidebar = UIKit glass sidebar (§4 "sidebar": blur 10, face 0.4 + 0.63·in, saturation 1.2, white fill 20 %, MaxLuma 0.85);
  Map Modes popover = NSPopover glass (§4 "NSPopover frame": blur 10, face 0.2 + 0.75·in, white fill 10 %, ring shadow 6 %); right-column
  buttons = UIGlassEffect *clear* (§4: blur 10, face 0.2 + 0.75·in, white 10 %, top highlight 0.4, shadow 0 8 24 10 % — regular would give
  52 % white on black where the App reads #2b2b2b; the buttons' `tintColor` is not decoded); search field = glass with the search-field set
  (§4: regular face, blur 5; BlurOpacity 0.4 / bleed / refraction not expressible); place card = `MUBlurView systemMaterial` → AppKit
  `NSVisualEffectMaterial` popover(6) (§3: blur 30, saturate 2.0, rgba(246,246,246,.6), #f1f1f1 darken; §6: menu(5) if
  `EnableThickCardMaterial` is on — default state unknown, popover chosen). The face matrix `out = Black + (White − Black)·in` and the white
  fill are folded into one `contrast(c) brightness(b)` (b·c = slope, b(1−c)/2 = intercept). **The luminance clamp / darken fill only
  composes as `mix-blend-mode` on the element that carries the `backdrop-filter`** — a blended child or pseudo-element is isolated by the
  panel's stacking context and comes out flat grey (Chrome test `raw/score/mattest.html`) — so the sidebar and the card paint their material
  on body-level fixed layers `#matSidebar` / `#matCard` (index.html; `shell.js` mirrors the card's `hidden`) and are themselves transparent.
  Verification (same coordinates, 1280×744, App vs ours): popover over black (1200,150) `#505253` / `#494949`, (1150,150) `#84a2ba` / `#82a3ba`;
  popover over sea (1100,290) `#66a2cb` / `#8cb4ce` — the App leaves the sea almost unchanged where the face matrix lifts it (+38 R): the
  affine reading of FaceColorMatrixWhite/Black holds on black, not on mid-tones — for the data session; sidebar over the dark limb (100,600)
  `#98a2aa` / `#93999e`, over land (100,200) `#cfd3d9` / `#e0e0e0`; search field (140,65) `#d3d5d6` / `#c9cacb`; button interior (1254,26)
  `#2b2b2b` / `#313131`. kit-audit rules check the computed `backdrop-filter` / `background` strings of all five (KIT-OK Mac 47).
* **iPhone materials (`ui/hig.css` §20):** MATERIALS.md §1 records the iOS sheet as `MUBlurView systemMaterial` → CoreMaterial
  `platformContentLight` (§2: blur 30, saturation 1.5, brightness +0.1, luminance remap 0.75 / [0.9, 0.83, 0.925, 0.815] ×
  `luminanceColorMap.png` — the LUT reads 89 → 204 /255, i.e. 0.35 → 0.80, a luminance compression; how the four values and the amount
  apply is not decoded). Verified in the simulator (iPhone 18 Pro Max, iOS 27 Maps, Explore, light, globe + medium sheet,
  `raw/renders/ios-maps-globe-sheet.png` 3x): the sheet over black space reads `#858585` = 0.52 — exactly the §4 *regular glass* value
  (0.4 + 0.2·0.8), while the §2 recipe with the Kit fill standing in gave 0.73; over sea `#98d8fb` vs the regular face's `#80cff7`. So the
  iOS 26 sheet is Liquid Glass regular (§4 baseline: blur 5, face 0.4 + 0.56·in, saturation 1.2, white fill 20 %), the same set as the 44
  round buttons; the search capsule is the §4 search-field set. Open: the App's sheet blur is far stronger than 5 pt (the glass backdrop is
  captured at a reduced scale — 0.5 is noted for the search field — so the radius may apply to scaled pixels); the dark MaxLuma clamps
  (0.35 / 0.6) need body-level material layers, not done on the phone. Sampling (440×956 frame, App / ours, backdrop class matched — our globe
  below z 4.6 is the pastel Mac palette while the iOS App's globe shows the saturated ramp colours, so only the black-backdrop points compare
  cleanly): sheet over space `#858585` / `#858585` (two points); sheet over sea `#98d8fb` / `#b2d5eb`; search capsule on the sheet
  `#acffff` / `#d4e7f3`; buttons: App over sea `#57d6ff`, ours over space `#858585`. Phone kit-audit in the simulator: KIT-OK 36.
  **Side finding for the data session:** the iOS Maps standard globe renders the sea in the ramp's saturated colours (`#0d99ec` deep), not the
  Mac App's pastel — the Mac globe's whitening is Mac-specific (or the atmosphere term), not the ground shader's output.
* iPhone: Kit Sheet three detents (small 96 / medium 44 % / large) with the search capsule 44 in the head, right-top 44 round buttons, stacked card sheet,
  Map Modes as a sheet; `.cb` becomes the 22 multi-select circle (iOS has no square checkbox).
* Hash: `#z/lat/lng&m=<mode>&sel=<id>` (globe.js keeps the extras; `m` and `sel` restore on load).
* kit-audit: `ACCEPT_BASE=http://127.0.0.1:8792 CDP_PORT=9400 python3 pipeline/ui/kit-audit.py --mac map`; the audit opens the card and
  the modes popover first (kitaudit.js exercise). Phone run needs the simulator.

## Zoom bands

| band | what happens |
|---|---|
| **PAL 4.6–5.0** | the globe's *sampled* palette (`palette-globe.json`, `climate-globe.png`, shelf raster — pending, see below) hands over to the decoded colours: ocean ramp (`color-relief`), NE land fill = Forest sheet colour, ground rasters. The whole flat style (fills, lines, `.styl` labels) fades in and the DOM globe labels fade out — the App's flat renderer owns z ≥ 5, so at the z 5.1 view everything flat is fully on |
| **MORPH 5–6** | `projection.type` = `interpolate zoom 5 'vertical-perspective' → 6 'mercator'`; the post-pass (lighting + rim) fades with it. Nothing else changes |
| **OVER 7–8** | the NE / raster drawing (ground rasters, ocean ramp, deep-sea and graticule DOM labels) fades out; asked as 8–9, kept at 7–8 because the 0.1° Köppen tint and the NE coastline stair-step from z ~7; `&over=8,9` overrides |

Layer order bottom→top: globe background · flat background/land fills · NE land fill + ground rasters (+ `climate-globe` below PAL) ·
**hill-shade** · flat water (lakes over the land; OSM ocean under the ramp) · NE isobaths + shelf (below PAL) · **ocean ramp** ·
flat geoline-* · flat lines · flat symbols. The ocean ramp is opaque wherever the terrarium DEM says depth ≥ 1 m, so the hill-shade never
shows on water (RENDER-PIPELINE §3: the ground shader has no relief on the water path).

## Layers — data and where every number comes from

| layer | data | colour / size — source |
|---|---|---|
| `background` | — | below PAL the sampled 0–200 m globe colour (pending); from PAL the ramp's coast colour (0.5 m) — the flat sheet's Water fill rgb(141,220,247) is within 6/255 of it |
| `ocean` (`color-relief` on the terrarium raster-dem) | AWS Terrain Tiles (ETOPO1 in the ocean), the same tiles as the hill-shade | **water-depth ramp**: `t = saturate((log2(depth_m) + 6.643856) × 0.051501)`, colour = `gradient1Texture[t]` (256 linear texels) × light(0,0,1), sRGB-encoded — `shader-numbers.json water_depth_gradient.{light,dark}` (SHADER-NUMBERS 4.3); 35 stops on log-spaced depths 1 m … 11 km, transparent at elevation 0 (ETOPO depths are integer metres, so the sea is opaque from 1 m). Verification: palette-ocean.json (snapshotter) 1000 m band `#33b7f9` vs ramp×light `#31b7f9`, 2000 m `#1daef7` vs `#1daff7`, 7000 m `#0d8de6` vs `#0d8de6` |
| `land` | Natural Earth 10m Land v5.1.1, `data/land.geojson` | `Landcover-Forest-Elevated-{Light,Dark}-Base` fillColor at Apple z6 (rgb(176,222,144) / rgb(0,107,103), `default-56689.styl`) × light(0,0,1) = `#b3e293` / `#00706c` — `ui/basemap/ground.json sheet.colours.Forest` |
| `ground`, `ground-ea` (raster images) | global 4096² Web-Mercator (class from Köppen) and the East-Asia box lat 0–60 / lng 90–160 at GIBS z6 resolution (3200×3456; z7 tiles downsampled 2× — a 6400×6912 image source decodes to 177 MB and stalled the acceptance’s software-GL render; class from **NASA GIBS MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual**, MCD12Q1 500 m, 2024-01-01, 675 tiles, no login) — `pipeline/basemap/ground.py`, `data/ground-{light,dark}.png`, `data/ground-ea-{light,dark}.png` | per pixel: Landcover class base colour (sheet, linearised) → 3×3 climate cells by `groundSettings.json` HSV deltas (z1–6: veryHot V+0.1, arctic S−0.2, veryDry H−35° V+0.1; night file for dark) sampled bilinearly by the temperature/aridity codes → × light(0,0,1) → sRGB. Sources: `shader-numbers.json climate_tinting`, SHADER-NUMBERS 4.4. Tables below |
| `hillshade` | AWS Terrain Tiles raster-dem | light **azimuth 240° / altitude 65°** (`shader-numbers.json lighting`); strength from `groundElevationScale(z)` through the conversion below; MapLibre `standard` method, exaggeration 0.5 (identity slope warp), shadow black / highlight white with alpha(z), no accent |
| post-pass `#light` (`globe-light.js`, WebGL) | MapLibre's canvas read back per frame | **lighting**: pixel_lin × light(n)/light(0,0,1), `light(n) = 0.49683·cube(n) + 0.7085·max(n·L,0)`, L = (−0.366, −0.211, 0.906) view-fixed, cube = the 8×8×6 irradiance texture (SHADER-NUMBERS 3.1/4.1); **rim**: `mix(midColor, black, t2) × (0.7085·0.25·(L·pos+1)² + 0.49683)` over 75 km outside the silhouette, midColor = Sky-Standard-Day rgb(155,196,237) / Night rgb(35,76,122) linearised (SHADER-NUMBERS 3.3, RENDER-PIPELINE 2.2). See "rim geometry" below |
| `flat-geoline-{tropics,equator}` (lines, every zoom, no fade) | `data/graticule.geojson` (globe-data.py: 23.4366°, 0°, 66.5634°) | the flat style's own layers (v6 `to_maplibre.py` from `Geolines-{Tropics,Equator}.Explore-*`, RENDER-PIPELINE 7.13/7.16: rgb(73,88,122) α by zoom, width 1.15 / equator 1 → 1.9, dashes at 0.2 pt per unit); the polar circles take the tropics row (filter lat ≠ 0). This page's own `graticule-*` layers (¼-pt dashes, lum −15) were dropped for them; `ui/basemap/geolines.json` stays as the decoded reference and feeds the DOM label |
| labels (DOM markers, z < 5) | NE 10m admin_0 `LABEL_X/Y`, marine + continent polys → spherical interior point; cities `data/cities.geojson` (`globe_rank` ≤ 4); deeps `data/undersea.geojson` (cls 1 Deep); graticule labels at the App's anchors | **pending**: typography measured on the App globe (`labels-globe.json`, `meta-ui.json labels_app`); the globe sheet rows (`basemap/data/styl/globe-key-numbers.tsv`) are decoded but not wired yet. Graticule label = Geolines textColor rgb(73,88,122), medium, labelInfo.height 7.5→9 (Apple z2–4), 9→10 (4–8), halo rgb(194,219,234) α 0.15 → not drawn (α < 0.2). Continents hidden from Apple z3 (`Continent-PointLabel-Base visible=False`) |
| labels (flat, z ≥ 4.6) | the flat style's symbol layers (`to_maplibre.py` ← `.styl` City-Label-LMZ / Country-Label / State-Label / Ocean-Points) | the sheet's, unchanged here |
| stars (canvas) | `basemap/data/globe/stars.bin` (VectorKit embedded zip, 10 000 × float32[3]) | positions: angle 0 / angle 1 taken as right ascension / declination in the earth-fixed frame, projected through the page camera; alpha = (brightness − 10)/4.1; **pending**: frame (stars-format.md), the GlobeStars point-size/alpha formula (size 1.2 pt is the App measurement) |

### light(0,0,1) — why every painted colour carries a 1.0455 factor

The App's flat renderer lights flat ground with the same formula as the globe: `light = ambientLightColor × cube(+z) +
lightColor × L.z = 0.49683 × 0.8118 + 0.7085 × 0.90625 = 1.0455` (linear). Every sheet colour and ramp texel is an *albedo*;
what the snapshotter shows is albedo × 1.0455. Check: palette-ocean.json (snapshotter, sampled) vs ramp × 1.0455 — 1000 m `#33b7f9`
vs `#31b7f9`, 2000 m `#1daef7` vs `#1daff7`, 4000 m `#0d99ec` vs `#0d9eee`, 7000 m `#0d8de6` vs `#0d8de6`; dark 1000 m `#0d1d4f`
vs `#0d1d4e`. The post-pass divides by the same value, so the disc centre is exactly the painted colour and the limb follows the cube + L.

### Hill-shade: groundElevationScale → MapLibre `hillshade-shadow-color` alpha

Apple lights the terrain normal `n = normalize(−s·∂h/∂x, −s·∂h/∂y, 1)`, `s = groundElevationScale(Apple z)` (`groundSettings.json`:
z1 14, z2 9, z3 7, z4 5, z5 3.25, z6 2.5, z7 1.5, z8 1.4, z9 1.35, z10 1.3, z11–15 1.25, z16 1.15, z17+ 1). For a slope of gradient g
facing away from the light, small g: `1 − light(n)/light(0,0,1) = lightColor·cos(alt)/light(0,0,1) · s·g = 0.2864·s·g` (linear).
MapLibre's `standard` hill-shade (exaggeration 0.5 ⇒ no slope warp) darkens in sRGB by `α · sin(atan(0.625 · g · 2^(0.3·(15 − zT))))`
with zT the DEM tile zoom (`hillshade_prepare`: `deriv = Σ/2^(0.3·(zT−15) + 28.2562 − zT)`, main: `/cos(lat)`, `slope = atan(0.625·|deriv|)`);
for 256-px DEM tiles on a 512-px map zT = map z + 1 = Apple z. Equating the small-slope terms with sRGB ≈ linear^(1/2.2):

`α(z) = (0.2864 / 2.2) · s(z+1) / (0.625 · 2^(0.3·(15 − (z+1))))` → z3 0.106, z4 0.085, z5 0.080, z6 0.059, z7 0.068, z9 0.096, z12 0.172

(`globe.js hillshadeAlpha`). The highlight colour is white with the same alpha: the formula's lit-side gain is ≤ +6 % linear (n·L ≤ 1
vs 0.906 flat), the white overlay is its small-slope approximation. Not modelled: the cube term's +2–8 % on tilted normals and
`normalsSharpnessBias`. The old fitted azimuth 260° and calibrated `{3: 0.047, 5: 0.30, 9: 0.07}` are gone (z9 calibration was
≈ 0.087·slope vs the formula's 0.080·slope; z5 was 5× the formula, the "seafloor relief" the acceptance saw).

### Rim geometry (verification of SHADER-NUMBERS 3.3 on `native-nosidebar.png`)

Far camera: `outerRadius = R + 150 km`, `colorMidPoint = 0.5`, so the corona spans 150 km = 2.36 % of the silhouette radius (13.6 px at
578 px @1x). Measured on the screenshot (`pipeline/basemap/…/rimcheck`): the visible profile is **mid → black over 15 px @2x = 7.5 pt ≈ 75 km**,
i.e. the horizon→mid half lies inside the silhouette on screen (the corona quad is in the centre plane; the perspective silhouette projects
there at D/√(D²−1) = 1.066 R > R). Colours: at the right limb (θ = 0, light = 0.7085·0.25·(−0.366+1)² + 0.4968 = 0.568) the first
outer pixel reads (120,144,172) vs predicted mid_lin × 0.568 × 0.9 = (113,144,175) with the sheet colour **linearised**; the doc's
"treat as sRGB values" reading gives (152,183,218) and does not match. Lit side (θ = −150°: light 0.855) is outside the window in this
screenshot. The inner darkening the earlier "haze" table modelled is the n·L term + this rim (RENDER-PIPELINE §6); the table is not
drawn any more. Residual after the formula on deep ocean at r/limb 0.9–0.95 (θ = 0): R,G +0.066 linear, B +0.03 — a yellow-grey lift
the sky-coloured `atmos` term cannot produce; left for the globe-tile `fogParameters` decode.

### Land-cover class mapping (IGBP → Apple Landcover), `ui/basemap/ground.json igbp_to_apple`

| IGBP (MODIS MCD12Q1) | Apple class | why |
|---|---|---|
| 1–5 Evergreen/Deciduous Needleleaf/Broadleaf, Mixed Forest | Forest | tree canopy > 60 % |
| 8 Woody Savannas | Forest | canopy 30–60 %; Apple has no savanna class, and the App paints Japan's lowland woods Forest |
| 6, 7 Closed / Open Shrublands | Shrubland | |
| 9 Savannas, 10 Grasslands | Herbaceous | herbaceous cover |
| 11 Permanent Wetlands | Wetlands | |
| 12 Croplands, 14 Cropland / Natural Vegetation Mosaic | Cultivated | |
| 13 Urban and Built-up | **Ground** | the App paints the Kanto / Osaka plains in the Ground colour at Apple z6: light (240,241,229) = Ground rgb(239,240,230)×light, dark (60,79,106) = Ground dark rgb(62,79,104)×light; `Landcover-Developed-Elevated-Dark` is lavender rgb(204,170,255), a close-zoom class |
| 15 Permanent Snow and Ice | IceSnow | |
| 16 Barren | Barren | |
| 17 Water, 0 / 255 nodata | transparent | the water layers draw there |

Data difference kept: Apple's own raster reads Japan's lowland paddies + suburbs as Ground and Korea's inland fields as Forest where
MODIS says Croplands (Cultivated). Outside the East-Asia box the class comes from Köppen (`koppen_default_class`: BW → Barren,
BS → Shrubland, ET → Barren, EF → IceSnow, else Forest); the seam at lng 90° is visible in dark mode / `pal=flat` below z 4.6.

### Climate codes (Köppen → temperature / aridity), `ui/basemap/ground.json koppen_climate`

Apple's temperature (0/3/6 = arctic/base/veryHot) and aridity (0/3/5 = veryWet/base/veryDry) rasters are its own (VMP4, not decoded);
Beck 2023 Köppen 0.1° stands in, in cell units 0–2: A f/m (2, 1); Aw, BSh, BWh, Cwa (1.5, ·); BW → aridity 2; BSk, Cs, Cwb/c, Dsc/d,
Dwc/d → 1.5; Dfc/d, Dsc/d, Dwc/d → temperature 0.5; E → 0; everything else (1, 1). **Verification** against the 705 App flat-render land
samples (`palette-land.json`, linear HSV by Köppen class): BWk hue 28° sat 0.25 val 0.965 = Barren (49°, 0.21, 0.87) with −35° / +0.1 ✓;
Af/Am val 0.83–0.84 = Forest (0.73) + 0.1 ✓ (veryHot); Aw 0.88 / Cwa 0.87 / BSh 0.88 on Cultivated (0.83) = +0.05 → half hot; ET hue 50°
sat 0.13 = Barren desaturated (arctic) ✓; Dwc hue 72° sat 0.48 = Forest shifted −27°, −0.14 → half dry / half arctic ✓; Dfb, Cfa, Dwa:
base ✓. Cs (Mediterranean) has no samples — half dry is an assumption.

## Build / run

```
python3 pipeline/basemap/ground.py           # sheet colours + Koppen + GIBS MODIS -> map/data/ground-*.png, ui/basemap/ground.json
python3 pipeline/basemap/geolines.py         # Geolines-* styles -> ui/basemap/geolines.json
python3 pipeline/basemap/globe-data.py       # NE / Koppen -> map/data/* ; --meta rewrites meta.json / meta-ui.json / graticule only
python3 pipeline/rangeserver.py 8792 &       # then open http://127.0.0.1:8792/map/index.html#3.12/30.14/124.45
zsh pipeline/basemap/score-views.sh          # the five acceptance views (cmp-accept + dark t=20)
python3 pipeline/basemap/shot.py <url> 1280 744 out.png [--dark]   # headless screenshot helper
python3 pipeline/basemap/palette.py / labels.py / globefit.py / shading.py / haze.py / calibrate.py   # sampling tools — verification only now
```

## Still sampled / open (2026-09-16 evening)

* **The globe below z 4.6** — `palette-globe.json` ocean bands and land tints, `climate-globe.png`, `shelf-globe.png`: the standard globe runs
  the same ground shader (RENDER-PIPELINE 2.3–2.5), but its pastel output is not reproduced by ramp × light: fitting `globe = (1−a)·flat + a·F`
  over the 11 ocean bands + 4 land tints leaves errors up to 35/255 for any single fog colour F (`scratch fogfit`). Whatever whitens the globe
  tiles (fog term, a globe sheet variant, the S2 texture path) is not decoded → the sampled palette stays for z < 4.6, marked pending.
* Globe DOM label typography (`labels_app`, `labels`) — sampled; the globe sheet rows are decoded (`globe-key-numbers.tsv`) and are the next thing to wire.
  Graticule label size: sheet 9 pt at Apple z4 vs 11 pt measured on the App — the globe sheet's ×1.2 `textSizeScale` would explain it (not applied).
  `labelColorLumAdjustment` −25 on Geolines is not applied (the App's label reads lighter than the sheet colour, not darker).
* Stars: frame and point-size/alpha mapping (RENDER-PIPELINE 2.1); the catalogue through the page camera gives 36 stars in the acceptance
  view against ~300 counted on the App screenshot.
* Inner limb residual (+0.066 linear in R,G at r/limb 0.9–0.95) — the globe-tile `fogParameters` / `atmos` constants were not captured.
* Flat style items for the data session: the expressway width below Apple z8 is resolved in v6 (RENDER-PIPELINE 7.15); prefecture borders
  magenta α 0.25 (inferred prop 12) where the App shows none at Apple z6 — the App's "thin grey lines" there are Ground-class valley floors
  (sampled: rgb(239,240,228) = Ground × light), not lines; shinkansen drawn at z 5 where the App shows none; labels in name:ja vs the App's English.
* No country borders below z 4.6 (the flat `boundary-*` layers start at PAL); the App draws `Border-Country` from Apple z2.
* Undersea names along lines (Japan Trench, basins), physical range labels (Taebaek Mountains) — data exists (`undersea.geojson`, `physical.geojson`), not drawn.
* Materials: popover face over mid-tones (see Shell), glass-button tint, `EnableThickCardMaterial` default, dark search-field MaxLuma 0.6, the
  BlurFill / bleed / refraction / chameleon parts of the glass recipes.
