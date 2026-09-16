# How Apple Maps (macOS 26) turns map data into the picture — and what of it we rebuild

Rule of this document (user, 2026-09-16): **decode the files first, sample only to verify**. Every number in the
"our rebuild" column names the file and item it comes from; numbers that still come from screenshot fitting are
collected in §6 with a verdict on whether they can be decoded and from where.

Delivered in parts. **Part 1 (this revision): the globe.** Part 2 (flat map) follows after acceptance.

Source tags used below: **[tiles]** live tile-set table read through GeoServices' own API
(`pipeline/basemap/tilesets.m`), **[vmp4]** VMP4 container headers of the tiles cached on this Mac
(`~/Library/Containers/com.apple.geod/…/MapTiles.sqlitedb`; chapter tags only, no chapter decoded) mapped to their
reader functions (`geo::codec::_read*` in GeoServices, tag immediates from the disassembly), **[styl]** style sheets
decoded with `pipeline/basemap/styl` (format in `STYL-FORMAT.md`), **[air]** shader bitcode from `default.metallib`,
**[cap]** uniforms/textures captured in-process from VectorKit (`pipeline/basemap/shader/capture.m`), **[vk]**
VectorKit decompile / macOS binary, **[res]** files under `VectorKit.framework/Resources` or
`~/Library/Caches/GeoServices/Resources`, **[zip]** the zip embedded in the VectorKit binary (§2.1, `basemap/data/globe/stars-format.md`), **[ui]** the
UI session's fitted files (`ui/basemap/*.json`, `map/README.md`).

## 1. The pipeline in one table

| stage | what happens | where it is defined |
|---|---|---|
| tile request | GeoServices asks `gspe19-ssl.ls.apple.com/tile.vf` (vector) / `gspe11-ssl.ls.apple.com/tile` (raster) / `asset/v3/{material,model}` with a style id; the id→URL table comes from the resource manifest | [tiles] `materials`-style table below; `pipeline/basemap/tilesets.m` prints it |
| tile decode | a VMP4 container (`VMP4` + u16 version + u16 count, then {u16 tag, u32 offset, u32 length} entries) is split into chapters; each tag has one reader in GeoServices | [vmp4] |
| style | the compiled GeoCSS sheet for the mode (`default-*.styl` flat, `globe-default-*.styl` globe, `scene-*.styl` lighting/scene) gives colours, widths, fonts, zoom bands per style name; features are matched to style names by the sheet's chapter 30 tree | [styl] |
| resources | `groundSettings.json` (elevation exaggeration, climate HSV tints), textures (`LandCoverGradient*.png`, `RealisticRoad*.png`, `clut-night-2.png`, …), `default.metallib` (all shaders), `NonTiledAssets.json` (puck) | [res] |
| render layers | `md::DaVinciGroundRenderLayer` (terrain + land cover + water for `MapDataType::DaVinciGround` and `DaVinciGroundGlobe`), `md::GlobeSkyRenderLayer` (rim + stars), `md::CoastlineRenderLayer`, `GlobeRasterRenderLayer` (satellite globe only), label / polygon / line layers | [vk] |
| shaders | `DaVinci::ground_*`, `GlobeAtmosphere::*`, `GlobeStars::*`, `Fog::*`, `Sky::*`, line / polygon / glyph shaders | [air] |
| output | linear-light compositing into an sRGB drawable; the App window then puts the Catalyst chrome on top (`MATERIALS.md`) | |

Tile sets the standard map on this Mac actually fetches (rows from the live manifest [tiles]; counts = tiles in
the local cache after today's globe and flat sessions [vmp4]):

| id | name | URL | chapters found in the cached tiles (tag → reader) | used for |
|---|---|---|---|---|
| 58 | `VECTOR_SPR_MERCATOR` | `tile.vf` | 1 tile metadata; **100 DaVinci 3D data** (terrain mesh, 20.5 MB / 155 tiles); **101 elevation raster**; **154 style attribute rasters ×2** (land-cover class index 1024², climate codes 128²); **155 material rasters + materials** (water depth, material refs) | the ground of the standard map at every zoom, flat *and* globe (`DaVinciGround`, `DaVinciGroundGlobe`) |
| 79 | `VECTOR_SPR_POLAR` | `tile.vf` | same four chapters, 8 tiles | the two polar caps of the globe |
| 60 | `VECTOR_SPR_MATERIALS` | `asset/v3/material` | not VMP4: `DVMt` material assets (125 cached) | material definitions incl. the water-depth colour ramp (`md::ColorRampData`) |
| 59 | `VECTOR_SPR_MODELS` | `asset/v3/model` | `DVas` model assets | 3D landmarks |
| 67 | `VECTOR_SPR_STANDARD` | `tile.vf?flags=32` | 10/11/13 labels, 20 string tables, 30 POIs, 31 lines, 145 lines extended, 141 label placement | borders, physical lines, labels of the standard map (globe and flat) |
| 66 | `VECTOR_SPR_ROADS` | `tile.vf?flags=32` | 31 lines, 51, 152 traffic skeleton, labels | roads |
| 61 / 78 | `VECTOR_SPR_METADATA` / `SPR_ASSET_METADATA` | `tile.vf` | 1 | availability metadata |
| 68 / 84 | `VECTOR_POI_V2` / `_UPDATE` | | 30 POIs, 144 addendum, 160 annotation labels | POIs |
| 73 | `VECTOR_BUILDINGS_V2` | | 142, 147 DaVinci landmarks, 167 | buildings |
| 83 | `VECTOR_TOPOGRAPHIC` | | **158 hillshade raster** (2 MB / 93 tiles) | the Topographic map mode only — the standard map has no hillshade raster; its relief is lit geometry (§3) |
| 1 / 20 / 37 / 30 | `VECTOR_STANDARD` / `ROADS` / `TRANSIT` / `VENUES` | | classic vector chapters | fallbacks / transit / venues |
| 18 | `VECTOR_REALISTIC` | | — (not in the cache) | not fetched on this Mac |
| 92 | `VMAP4_ELEVATION` | `gspe11 tile` | — (not in the cache) | not fetched: elevation rides inside SPR chapter 101 |
| 7 / 33 / 91 / 95 | `RASTER_SATELLITE(_NIGHT/_POLAR/_POLAR_NIGHT)` | `gspe11 tile` (JPEG) | | satellite / hybrid globe (`GlobeRasterRenderLayer`, `DaVinci::globe_texture_*`) |

"SPR" is Apple's name for the current DaVinci standard-map tile family (`EnableSPR`, `SuppressInSpr` flags in
VectorKit). `VECTOR_LAND_COVER` (54) is not requested; land cover comes as the 154 rasters inside SPR tiles.

## 2. The globe, element by element

Standard map, zoomed out to the sphere (`MapDataType::DaVinciGroundGlobe` + `GlobeSkyRenderLayer`). Camera
altitude in the acceptance view ≈ 12 000 km (h ≫ 150 km ⇒ the atmosphere code's *far* branch, §2.2).

### 2.1 Space, stars

| | |
|---|---|
| Apple data | stars: `sky/stars.bin` in the zip embedded in the VectorKit binary [zip] — 10 000 records × (float, float, float) = (angle 0–2π, angle −1.52…1.54 rad, brightness 14.08 → 10.02, sorted bright-first); loaded by `karo::media::SkyLoader` from `md::GlobeSkyRenderResources::loadStarsModel` [vk VectorKit_108.mm:9506]. Space itself: the clear colour of the pass (black). |
| look | `GlobeStars::stars_vertex/fragment` [air]: white, alpha per star; point size from the vertex. Stars are drawn when the camera is in the far branch (h ≥ 150 km) or zoom < 4 (`v11` in `GlobeSkyRenderLayer::layout`). |
| our rebuild | canvas star field [ui `map/README.md`]: 8.6 per 100×100 pt, 1.2 pt squares, grey p10/p50/p90 = 53/137/194 — **sampled** (`native.png`). |
| gap / fix | replace by the catalogue: draw `stars.bin` (extracted to `basemap/data/globe/stars.bin`) with brightness→alpha; the density then follows the sky, not a Poisson guess. The two angles' frame (equatorial vs galactic) and whether the sky is fixed to the earth or to the camera are unresolved (`basemap/data/globe/stars-format.md`). |

### 2.2 Rim (atmosphere halo outside the disc)

| | |
|---|---|
| Apple data | none — a corona mesh (`ggl::GlobeAtmosphere::AtmosphereMesh`, `buildAtmosphereModel`) from `innerRadius` to `outerRadius`. |
| look | `GlobeAtmosphere::globe_atmosphere_vertex/fragment` [air] + constants filled in `md::GlobeSkyRenderLayer::layout` [vk VectorKit_44.mm:7582, values checked in the macOS binary]: R = 6 356 752.31 m; h = max(\|camera\| − R, 100); horizonDistance = √(h(h+2R))/R; outerRadius = R + h + horizonDistance·1.1R·tan(fov/2); far branch (h ≥ 150 000 m [res VKDebugSettings `daVinciAtmosphereMaxHeight`]): t = clamp((h−150 000)/150 000, 0, 1) = 1 at globe distance, colorMidPoint = 1 − t·0.5 (`daVinciAtmosphereColorMidpoint` 0.5) = 0.5, lightingEnabled = t = 1, outerRadius → 150 000 + R. Colours [styl `default-iosmac-11358.styl` → `Sky-Standard-Day`]: midColor = fillColor rgb(155,196,237), horizonColor = prop 202 rgb(212,226,240); endColor = (0,0,0,1) [vk constant]; night: `Sky-Standard-Night` rgb(35,76,122) / rgb(86,109,165). Fragment: c = mix(horizon, mid, t1) then mix(c, end, t2) over the radial distance with the mid point at 0.5 of the corona; c *= light where light = lightColor·lightIntensity + ambient·(1−nightLightFade), lightIntensity = 0.25·(dot(primaryLightDirection, pos)+1)², primaryLightDirection = the §2.5 light in view space; nightLightFade = 0 by day. |
| our rebuild | canvas "limb haze" [ui `haze-globe.json`]: per r/limb bin a colour + opacity solved from pixels (r 0.925 a 0.19 `#484f84` → 0.99 a 0.94 `#94a3b6`) and "outer 7 pt fall-off from the `native.png` row-800 profile" — **sampled/fitted**. MapLibre's own atmosphere is off. |
| gap / fix | the outside glow is fully specified above: at the acceptance camera (D = 2.89 earth radii ⇒ h = 1.89 R ≫ 150 km) the far branch sets the corona's outer edge to R + 150 km = 1.0236 R, i.e. **2.4 % of the silhouette radius ≈ 14 px at the 578 px (1×) silhouette** — the 14 px outer glow the UI measured on `native.png`; colours rgb(212,226,240) at the surface → rgb(155,196,237) at half the thickness (colorMidPoint 0.5) → black at the edge, multiplied by the sun term (brighter on the lit side, `lightingEnabled` = 1 in the far branch). Replace the fitted haze table by this; keep the table only to verify. The *inside* darkening the UI folded into "haze" is not this pass — it is the lighting term (§2.5) plus, if enabled for globe tiles, the ground atmosphere term (unresolved, §6). |

### 2.3 Ocean

| | |
|---|---|
| Apple data | water depth per pixel from SPR chapter **155 material rasters** [vmp4] (float depth raster; positive metres — the shader takes `log2(depth)`), water/land mask = land-cover class "Water" (palette alpha 0) in chapter 154; the colour ramp = a material from `VECTOR_SPR_MATERIALS` (`DVMt`, `md::ColorRampData` → `MaterialTextureManager`), 256 texels. |
| look | `DaVinci::ground_fragment` [air]: t = saturate((log2(depth_m) + 6.6439)·0.0515) [cap `gradient1Parameters`]; albedo = ramp[t] — ramp captured [cap `gradient1Texture`, `basemap/data/shader/shader-numbers.json` → `water_depth_gradient.light/dark.texels_srgb_hex`]: light `#91daf3` (t=0, ≤ 1 cm) → `#8dd7f3` (t=0.375, 1.6 m) → `#6dc7f4` (0.625, 47 m) → `#32b4f4` (0.875, 1.4 km) → `#0d8ae2` (1, ≥ 7 km); dark `#1c3b86` → `#000d22`. Then × light (§2.5) in linear RGB; water normals are flat (+z), so the sea has no relief shading and its brightness is the pure n·L of the sphere. No specular (buffer unbound), no fog on the globe (fogParameters.w = −inf ⇒ ground atmosphere term 0 [cap]). |
| our rebuild | NE 10m bathymetry polygons per depth band [ui `map/README.md` `bathy-*`] coloured from **`palette-globe.json` (sampled)** and a 0–200 m shelf raster from AWS terrarium coloured by **`palette-shelf.json` (sampled)**; the `lit sphere` canvas multiplies by the **fitted** `shading-globe.json`. |
| gap / fix | colour: use the captured ramp with the captured depth mapping — depth → t → 256-entry ramp (`shader-numbers.json`), so the NE band colour = ramp at the band's representative depth, and the terrarium shelf raster = ramp(depth) directly (both light and dark now have a decoded source; the UI's dark globe had none). Acceptance already checked the deep bands: 4–5 km `#0d94e6` vs sampled `#0d99ec`, ≥ 7 km `#0d8ae2` vs `#0d8de6` (Δ ≤ 6). Light: replace `a + b·n·L` by `albedo_lin · (0.4968·cube(n) + 0.7085·max(n·L,0))`, then sRGB-encode (§2.5). Remaining source difference: Apple's depth raster is its own (in chapter 155, not decoded); we use terrarium/ETOPO1 + NE bands — a data difference, not a style one. |

### 2.4 Land base colour (land-cover classes)

| | |
|---|---|
| Apple data | land-cover class index raster per tile, SPR chapter **154** (R8 1024², 0…N−1 tile-local, `landCoverSettings.maxIndex` = 255) [vmp4, cap]; class → style name is the tile's material list (chapter 155). |
| look | per tile VectorKit builds the palette texture (`styleTexture`, 3 × 3·classes RGBA8) from **`Landcover-<Class>.Light-Elevated` / `.Dark-Elevated` `fillColor` at the tile zoom** [styl `default-iosmac-11358.styl`], linearised: Forest z5 rgb(176,222,144) → `#6dba47` lin, Wetlands rgb(175,230,168) → `#6bc963`, Cultivated rgb(199,235,152) → `#90d34e`, Herbaceous rgb(188,230,151) → `#7ec94d`, Shrubland rgb(228,235,192) → `#c1d37b`, Barren rgb(240,236,216) → `#dcd3ad`, IceSnow rgb(245,245,245) → `#e8e8e8`, Ground rgb(235,237,223) → `#d3d5bc`, Water → alpha 0 (§2.3). The sheet colours step by zoom band (`Landcover-Forest.Light-Elevated`: z1 rgb(146,213,98), z3 rgb(163,217,125), z5 rgb(176,222,144), z8 rgb(180,224,149) …) — the globe is z ≈ 2–4, so the z1–z4 rows apply. |
| our rebuild | NE 10m land polygon in one "humid" tint + a Köppen raster recoloured into 5 tints, colours from **`palette-globe.json` (sampled)**, class assignment by "majority vote of `palette.py`'s 705 samples" [ui]. |
| gap / fix | colours: take the `Landcover-*.Light-Elevated` / `.Dark-Elevated` rows at Apple z2–z4 from the sheet (decoded; `pipeline/basemap/styl/resolve.py value_at(name, 1, z)`), no sampling needed. Classes: Apple's raster is its own land-cover product (not decoded, VMP4 raster); a public stand-in with the same eight classes is ESA WorldCover / Copernicus GLC (tree cover → Forest, shrubs → Shrubland, grassland → Herbaceous, cropland → Cultivated, wetland → Wetlands, bare → Barren, snow/ice → IceSnow, built-up → Ground) — Köppen is the wrong axis for the *base* colour; it is the axis for the tint (§2.5b). |

### 2.5 Lighting (the "lit sphere") and 2.5b climate tint

| | |
|---|---|
| Apple data | normals from the terrain mesh (chapter 100, per-vertex `half2` normals) with vertical exaggeration `groundElevationScale` by zoom [res `groundSettings.json`: z1 14, z2 9, z3 7, z4 5, z5 3.25, z6 2.5, z7 1.5, z8 1.4 … z17+ 1] and `normalsSharpnessBias` (0.95 at z1–4 → 0.73 at z15+); climate codes from the second 154 raster (temperature 0/3/6 = arctic/base/veryHot, aridity 0/3/5 = veryWet/base/veryDry). |
| look | `ground_base_vertex` / `ground_fragment` [air], values [cap] (identical at spans 1°–120°, pitch, heading, light and dark): light direction view-fixed **azimuth 240° from north clockwise, altitude 65°** = (−0.366, −0.211, 0.906) in (x right, y up, z toward viewer); `lightColor` 0.7085 grey, `ambientLightColor` 0.4968 grey, ambient irradiance cube 8×8×6 (0.81–0.88) — all linear. `light(n) = 0.4968·cube(n) + 0.7085·max(n·L, 0)`; colour = albedo_lin · light, sRGB-encoded on write. The CPU side (`md::LightingLogic::writeLogicContext` [vk VectorKit_36.mm:1493]) computes L = (sin az·cos alt, cos az·cos alt, sin alt) from scene-sheet properties (`scene-1148.styl`, ids unnamed). Tint: palette cell = HSV(base) + temperature + aridity deltas from `groundSettings.json` (z1–6: veryHot V+0.1, arctic S−0.2, veryDry H−35° V+0.1; night file separate); verified against every captured palette cell within 2/255 [cap]. |
| our rebuild | `shading-globe.json` **fitted**: `a + b·(n·L)` with a 0.753, b 0.317, L (−0.436, −0.251, 0.864) in sRGB; hill-shade layer from AWS terrarium with azimuth 260° (**fitted** on an Alps render) and exaggeration `{3: 0.047, 5: 0.30, 9: 0.07}` **calibrated** by texture amplitude [ui `calibrate.py`]; climate tints from `palette-globe.json` **sampled**. |
| gap / fix | direction: 240° ✓ (fit 240.1°), altitude 65° (fit 59.8°) — decoded; intensity: use the linear formula; exaggeration: use `groundElevationScale(z)` directly on the DEM before computing normals (z3 = 7×), which replaces the calibrated k; the hill-shade *azimuth* for the flat map (260° fitted) is the same 240°/65° light — the 20° difference is the fit's error or the flat-map `sunMatrixCosSin` handling, to be checked on the flat part; tints: apply the HSV deltas to the sheet base colours, keyed by a public temperature/aridity classification (the App's codes are its own raster; Köppen groups → arctic = E, veryHot = A/BWh, veryDry = BW, veryWet = Af — an approximation of an undecoded raster, flagged in §6). |

### 2.6 Polar caps

| | |
|---|---|
| Apple data | `VECTOR_SPR_POLAR` tiles (8 cached) [tiles, vmp4] with the same four chapters; fallback meshes `poles/{north,south}pole/0/0/map_0_0_0.c3b/.c3h` in the embedded zip [zip] and in the GeoServices cache (`northpole-1.c3b`, `southpole-1.c3b`) [res]. |
| look | same ground shader; ice = `Landcover-IceSnow` colour. |
| our rebuild | NE land polygon only (Antarctica in the humid tint unless Köppen EF turns it high-grey). |
| gap / fix | colour from `Landcover-IceSnow.Light-Elevated` rgb(245,245,245) / dark rgb(102,142,178) at z1 [styl]; geometry NE is fine. |

### 2.7 Coastline, borders, graticule

| | |
|---|---|
| Apple data | coastline: land/water boundary of the land-cover raster (no line geometry at globe zoom: `Coastline-Glow-Base` width = 0 for z0–8 [styl globe sheet]); borders: `VECTOR_SPR_STANDARD` chapter 31 lines [vmp4]; tropics/equator: a physical-feature line in the same chapter (style not located, see §6). |
| look | borders [styl `globe-default-*.styl`, `basemap/data/styl/README.md`]: `Border-Country-NonDisputed-Base` width z0–2 0.9 → z4–5 1.1 → z5–6 1.45 px, colour z0–2 rgb(188,188,188) → z2–4 rgb(196,196,196) → z4–6 rgb(200,200,200), stroke α 0.4→0.8, **hidden at z0–2**; state borders `Border-State-Globe-Colors-Base`. |
| our rebuild | NE admin-0 lines with the sheet's widths/colours (data session's earlier unit); graticule dashed `#6b8098` 1 pt 3/3 **sampled**. |
| gap / fix | borders decoded; graticule line style still to be located in the sheet (§6). |

### 2.8 Labels on the globe

| | |
|---|---|
| Apple data | `VECTOR_SPR_STANDARD` chapters 10/11/13 (labels), 20 (strings), 141 (placement) [vmp4]. |
| look | globe sheet [styl `globe-default-20207.styl` → `basemap/data/styl/globe-key-numbers.tsv`]: continent `Continent-PointLabel-*` 9→14 pt, `%$default,semibold,width=80`, rgb(237,232,235) α0.98, halo rgb(22,0,8) α0.85, hidden from z3; country `Country-Label-*` bold-G3 width=80, 9–20 pt by zoom, halo rgb(248,248,246) α0.8, hidden z0–3; ocean `Ocean-Label-Base` bold italic 12 pt, globe colour rgb(170,224,235); undersea `PhysicalFeature-Undersea-*`; `labelColorLumAdjustment` (463/464/470/471) applied after. |
| our rebuild | DOM markers with **`labels-globe.json` (sampled typography)** [ui]. |
| gap / fix | typography and colours are decoded (the tsv); the sampled file remains only as a check. Placement (which labels win) is the App's collision solver, not a sheet number — an accepted difference. |

### 2.9 Dark mode of the globe

Everything above has a dark twin decoded: rim `Sky-Standard-Night`, ramp `#1c3b86 → #000d22` [cap], land colours
`Landcover-*.Dark-Elevated` [styl], tints `groundSettingsNight.json` [res], light/ambient unchanged [cap]. The UI
page had no dark globe palette at all ("dark mode has only the flat dark palette").

## 3. Which shader does what to water and land (asked by acceptance)

One pass, `DaVinci::ground_base_vertex` → `DaVinci::ground_fragment`, draws both. The differences are inputs,
not shaders:

| | land | water (land-cover class Water, palette alpha < 0.999) |
|---|---|---|
| albedo | land-cover palette cell (sheet colour + climate HSV) | depth ramp[t(depth)] |
| normal | terrain mesh normal (exaggerated DEM) → relief shading via n·L | flat (+z): n·L = constant on the flat map, = sphere normal on the globe |
| ambient | 0.4968 · irradiance cube(n) | same |
| direct | 0.7085 · max(n·L, 0) | same, with the flat normal |
| specular / shadow / SSAO / emissive / colour correction | function constants off, buffers unbound [cap] | same |
| atmosphere/fog | `needsAtmosphere` term = 0 on the flat map (`fogParameters.w = −inf`) [cap]; globe tiles unverified (§6) | same |

So: **no hillshade over water** (nothing modulates the ramp except the sphere's own n·L on the globe), and no
bathymetric shading — the sea's only depth signal is the ramp. The topographic `RASTER_HILLSHADE` chapter (158)
belongs to the Topographic map mode and is not part of the standard map.

## 4. Shader stage — formulas and numbers

The full derivation, struct layouts, capture tooling and the comparison with the UI fit are in
[SHADER-NUMBERS.md](SHADER-NUMBERS.md); the numbers are in `basemap/data/shader/shader-numbers.json`. The parts
the globe needs, in one place:

```
n·L lighting      light(n) = 0.4968·cube(n) + 0.7085·max(dot(n, L), 0),  L = (−0.366, −0.211, 0.906) view space   [cap]
land albedo       styleTexture[col = temperature code, row = class·3 + aridity code]  = HSV(sheet colour, linear) + groundSettings deltas   [styl, res, cap]
water albedo      gradient1Texture[saturate((log2(depth_m) + 6.6439)·0.0515)]   [cap]
pixel             sRGB(albedo_lin · light(n))                                    [air]
rim               GlobeAtmosphere: mix(horizon rgb(212,226,240), mid rgb(155,196,237), t1) → mix(·, black, t2), × (0.25·(dot(L,pos)+1)² · 0.7085 + 0.4968)   [air, vk, styl]
stars             stars.bin (10 000), white × alpha                              [zip, air]
```

## 5. Files this part produced

`pipeline/basemap/tilesets.m` (tile-set table), `basemap/data/globe/tilesets.tsv` (its output),
`basemap/data/globe/vmp4-chapters.tsv` (chapter tags per tile set from the cache, `pipeline/basemap/vmp4_chapters.py`), `basemap/data/globe/stars.bin`
(+ `stars-format.md`), the corrections to `SHADER-NUMBERS.md` §1 (standard globe = `DaVinciGroundGlobe` through the
ground shader; `globe_texture_*` is the satellite globe).

## 6. Still sampled or fitted — can it be decoded?

| value (UI file) | what it stands for in the renderer | verdict |
|---|---|---|
| `palette-globe.json` ocean bands | ramp[t(depth)] × light | **decoded** — ramp + depth mapping [cap]; only the depth *data* differs (Apple raster vs terrarium/NE) |
| `palette-shelf.json` 0–200 m ramp | same ramp at t 0…0.68 | **decoded** (ramp is continuous from 1 cm) |
| `palette-globe.json` land tints (5 Köppen classes) | land-cover class base colour (sheet) + climate HSV delta | **decoded** for the colours and the deltas [styl, res]; the class and climate *rasters* are Apple's (chapter 154, VMP4 raster, out of scope) → stand-in data needed (ESA WorldCover + a temperature/aridity classification) |
| `shading-globe.json` a, b, L | light(n) | **decoded** [cap]: a → 0.4968·cube, b → 0.7085, L → az 240° alt 65°, applied in linear light |
| `haze-globe.json` inner bins (r 0.5–0.99) | not an effect: the same n·L falloff + rim overlap | **replace by the lighting formula**; the ground `needsAtmosphere` term on globe tiles could add a small skyBottomColor bleed near the limb — value not captured (MKMapView never enters the globe path); decodable only from the decompile of `PrepareStyleConstantDataHandleForGlobeTiles` (not done) |
| `haze-globe.json` outer 7 pt glow | GlobeAtmosphere corona | **decoded** (§2.2 formula + colours); thickness 2.4 % of the radius at the acceptance camera |
| hill-shade exaggeration k `{3: 0.047, 5: 0.30, 9: 0.07}` | `groundElevationScale(z)` on the DEM before normals + n·L with 0.7085 | **decoded** [res]; the mapping from MapLibre's `hillshade-exaggeration` to a DEM scale is the UI's implementation detail, the target amplitude is now a formula, not a calibration |
| hill-shade azimuth 260° | light azimuth | **decoded**: 240° / 65° [cap] (flat and globe alike) |
| `labels-globe.json` typography | globe sheet label styles | **decoded** [styl tsv]; keep the sampled file as verification only |
| star density / grey levels | `stars.bin` | **decoded** [zip]; the sky frame (which star where) unresolved |
| graticule dash `#6b8098` 3/3 | a line style in the globe sheet | **not located yet** — searched by name (Tropic / Graticule / Equator / Latitude) and by colour (±14) in `globe-default-iosmac-6857.styl`; next: match by dash pattern (prop 279/280) |
| material α (MATERIALS.md) | AppKit / glass recipes | **decoded** (MATERIALS.md) |
| Apple's depth raster, land-cover raster, climate raster | VMP4 chapters 154 / 155 | **not decoded by decision** (VMP4 rasters); all replacements are public data |

## Part 2 — the flat map (next delivery)

Ground colour, water, vegetation polygons, road classes, rail, buildings, borders, label classes, halos/glow,
fog, shadows: same table shape, sources already on disk (`map/style-flat-mapping.tsv`, `default-*.styl`,
`RealisticRoad*.png`, chapter 31/51/135 lines and road network, `Coastline-Glow-*`, `Sky::`/`Fog::` shaders).
