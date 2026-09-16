# How Apple Maps (macOS 26) turns map data into the picture — and what of it we rebuild

Rule of this document (user, 2026-09-16): **decode the files first, sample only to verify**. Every number in the
"our rebuild" column names the file and item it comes from; numbers that still come from screenshot fitting are
collected in §6 with a verdict on whether they can be decoded and from where.

Delivered in parts: **Part 1 (§1–6): the globe. Part 2 (§7): the flat map.**

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
| graticule dash `#6b8098` 3/3 | `Geolines-Tropics` / `-Equator` / `-Polar` in the **flat** sheet `default-56689.styl` | **decoded** (§7.13): `#49587a` α0.45–0.7, width 1.15, dash [12,12]…[32,32] ¼-pt units |
| material α (MATERIALS.md) | AppKit / glass recipes | **decoded** (MATERIALS.md) |
| Apple's depth raster, land-cover raster, climate raster | VMP4 chapters 154 / 155 | **not decoded by decision** (VMP4 rasters); all replacements are public data |

## 7. Part 2 — the flat map

Same renderer, same SPR tiles, same ground pass; what changes with zoom is which sheet rows apply (Apple z =
MapLibre z + 1; all zooms below are **Apple z**) and what the tiles carry. Sheet = `default-56689.styl` (iOS;
the Mac sheet `default-iosmac-*` has the same colours and bands, sizes ×1.2987 drawn at 77 % — pixel output equals
the iOS values, `basemap/data/styl/README.md`), leaf variant `.Light-Elevated` / `.Dark-Elevated` (what the Mac
App and `MKMapSnapshotter(.realistic)` draw). Values read with `pipeline/basemap/styl/resolve.py`
(`value_at(style, prop, z)`); our style = `map/style-flat-{light,dark}.json` generated by
`pipeline/basemap/styl/to_maplibre.py` from the same rows, layer ↔ style in `map/style-flat-mapping.tsv`.

### 7.1 Ground colour

| | |
|---|---|
| Apple data | SPR chapter 154 land-cover index raster (class per pixel), chapter 100 mesh [vmp4]. |
| look | ground pass (§3): class "Ground" → `Landcover-Ground.Light-Elevated` fillColor by zoom: z5 `#ebeddf`, z6 `#eff0e6`, z8 `#f5f5eb`, z10 `#f5f4ec`, z12+ `#f7f6f2` [styl]; lit by the same light (0.4968 ambient + 0.7085·n·L) — on flat terrain n·L = 0.906 ⇒ multiplier 0.4968·cube + 0.642 ≈ 1.06 (linear), i.e. the sheet colour comes out ≈ 2 % brighter than written; dark `.Dark-Elevated`. |
| our rebuild | MapLibre `background` = `Landcover-Ground.Light-Elevated` stepped by zoom [`to_maplibre.py` ← styl]. |
| gap | the ≈1.06 lighting multiplier is not applied (2 % — below the acceptance metric's resolution); relief shading of the ground (§7.4) is separate. |

### 7.2 Water (sea, lakes, rivers)

| | |
|---|---|
| Apple data | sea: class Water in chapter 154 + depth in chapter 155 → ramp (§2.3), the same at z12 (Osaka Bay shows the ramp's 0–100 m colours `#91daf3…#6dc7f4`); inland water polygons: `VECTOR_SPR_STANDARD` chapter 31/145 lines and polygons (`WaterPolygon-*`, `Rivers-*` styles) [vmp4, styl]. |
| look | ramp × light for the sea; polygons `WaterPolygon-Day-Base` / `Landcover-Water.Light-Elevated` fill `#8ddcf7` (all zooms) [styl]; rivers `Rivers-Light-Elevated-Base` width 1.5 (≤ z10) → 2.1 (z12) → 2.5 (z14) → 2.75 (z16), colour `#8ddcf7`, hidden from z16 as lines (polygons take over) [styl]; coastline glow `Coastline-Glow-Light-Base`: width 0 at z ≤ 8, 5 px z8–10, 7 z10–12, 8 z12–14, 9 z14+, colour `#87ddfb` → `#82daf7` (z8) → `#8adaf4` (z10+) [styl] — a glow drawn along the coast on the water side (`CoastlineRenderLayer`). |
| our rebuild | `water` fill = `Landcover-Water.Light-Explore` `#8ddcf7`; `waterway` = `Rivers-Light-Elevated-Base` widths [`to_maplibre.py` ← styl]; the sea is one flat colour (OpenMapTiles has no depth). `palette-ocean.json` (sampled, 0–200 m `#6cc9fa` … ≥ 7 km `#0d8de6`) is what the UI used for the sea bands. |
| gap | sea: use the ramp (§2.3) with a depth source (terrarium/NE) instead of `palette-ocean.json` — the sampled bands are the ramp seen through the snapshotter, decoded now; coastline glow not drawn (8 px `#8adaf4` inner glow at z12 is visible in the acceptance side-by-side as the lighter rim along the coast) → a `line` layer on the coastline with blur; rivers at z12 use the sheet width (done). |

### 7.3 Vegetation and land-use fills

| | |
|---|---|
| Apple data | vegetation is **not a polygon**: it is the land-cover raster class (chapter 154) tinted by climate (§2.4/2.5b), lit with relief. Parks, cemeteries, hospitals, campuses, airports, stadiums are polygons in `VECTOR_SPR_STANDARD` [vmp4]. |
| look | raster classes: `Landcover-Forest.Light-Elevated` z5 `#b0de90`, z8 `#b4e095`, z12 `#b0e08d`, z13+ `#ace087`; Herbaceous z5 `#bce697`, z12 `#bde897`; Cultivated z5 `#c7eb98`, z12 `#d4eda1` [styl] — then the climate HSV delta of the tile's zoom band (`groundSettings.json`: z7–8 dry H−24° V+0.06, z8–9 dry H−12° V+0.03, none from z9) [res]; polygons: `ParkPolygon.Elevated-Light` `#cef0b1` (≤ z10) → `#c6eba7` (z12) → `#c0e89e` (z14), `CommercialPolygon`, `HospitalPolygon`, `UniversityPolygon`, `CemeteryPolygon`, `StadiumPolygon`, `AirportPolygon` [styl]. |
| our rebuild | OpenMapTiles `landcover` (wood/grass/sand) and `landuse` polygons with the sheet colours [`to_maplibre.py` ← styl]; the UI's `palette-land.json` (sampled: humid `#bfe98b`, semi-humid `#e1eda7`, dry `#ece8ab`, very-dry `#ffe9e1`, high-grey `#f4f1e6`) drives the globe→flat hand-over. |
| gap | z5–8: Apple's green is the raster (every land pixel has a class) — OpenMapTiles `landcover` at z5–8 is sparse polygons, so our land reads as Ground colour where Apple shows Forest/Herbaceous: needs a land-cover raster (ESA WorldCover) coloured with the sheet classes + the HSV delta (the same fix as §2.4); z12: OSM wood/grass polygons are close to the raster and the accepted 6.9 % diff already includes them. The `palette-land.json` tints are decoded now (class colour + HSV delta), no longer needed. |

### 7.4 Relief (hill-shade) on the flat map

| | |
|---|---|
| Apple data | chapter 100 mesh normals, chapter 101 elevation [vmp4]. |
| look | ground pass with `groundElevationScale` by zoom [res `groundSettings.json`]: **z5 3.25, z6 2.5, z7 1.5, z8 1.4, z9 1.35, z10 1.3, z11–15 1.25, z16 1.15, z17+ 1**, `normalsSharpnessBias` 0.94 (z5) → 0.85 (z9) → 0.78 (z12) → 0.73 (z15+); light azimuth 240°, altitude 65°, `0.4968·cube(n) + 0.7085·n·L` [cap] — the same light at z12 as on the globe (`tileLightDirection` identical in the span-1° capture). At z12 with 1.25× exaggeration the Rokko range still reads as relief; over water none (§3). |
| our rebuild | MapLibre `hillshade` from AWS terrarium, azimuth **260° (fitted)**, exaggeration **`{3: 0.047, 5: 0.30, 9: 0.07}` (calibrated)** [ui]. |
| gap | replace by 240°/65° and `groundElevationScale(z)` applied to the DEM (or its equivalent in MapLibre's exaggeration once the amplitude mapping is written down once); `normalsSharpnessBias` — its use in the mesh normal computation is not decoded (VectorKit `DaVinciGround*` normal builder), so the *softness* of the relief at z12 is still by eye. |

### 7.5 Roads

| | |
|---|---|
| Apple data | `VECTOR_SPR_ROADS` (66) chapter 31 lines + 51 + 152 (traffic skeleton) and `VECTOR_ROAD_NETWORK` (53) chapter 135 [vmp4]; road class, name, shield ref per feature; Japan classes → `-JPN` styles; national routes → `ClassOne`. |
| look (widths in px, fill / stroke colour, `.Light-JPN-Elevated` unless noted) [styl] | **FreewayControlled** (expressway): z5 2.25 `#96a2b3`/`#f9fbff` (grey), **z6–7 2.25 + 0.4 stroke, fill `#c2b3e0` stroke `#9e8dbf` (purple)**, z8 2.3 `#bcadd9`, z10 3.25 `#b5a7d1`, z12 3.75 `#b9aed1`/`#897ba6`, z14 5.5 `#aaacb3`. **MajorHighway**: hidden ≤ z7, z8–9 0.5 px `#dfe6e6`, z10 1.0 `#d7dbdb`, z12 2.55 `#edf0f5`/`#a1b0d1` + 0.5, z13 3.25. **Highway** (primary): hidden ≤ z9, z10 1.0, z12 2.55, z13 3.25 (same colours as MajorHighway). **Highway ClassOne** (国道): hidden ≤ z9, z10 1.0 `#b5a7d1`/`#897ba6`, z12 2.55 `#b9aed1`/`#897ba6`, z13 3.25 — the purple national-route line appears at z10, not at z5–8 (the z6–8 purple is the expressway). **ConnectorRoad** (secondary): hidden ≤ z9, z10 1.0, z12 2.55. **LocalMajorRoad** (tertiary): 0.65 px ≤ z10 (visible from z8), z12 1.5 `#d5dbdb`/`#d1c7bb`, z13 2.5 `#ffffff`/`#c1c3c7` + 0.33, z14 3.75. **LocalRoad-MinorRoad**: hidden ≤ z11, z12 1.5 `#e1e6e6`/`#dadada` + 0.25, z14 1.75 `#ffffff`. **ServiceRoad**: hidden ≤ z13, z14 2.2 `#ebe8e6`. Road names: `labelInfo.height` 7.5 (≤ z12) → 8.5 (z13), `%$default,medium,width=100` → `semibold-G3` at z13, colour `#4d4d4d` (≤ z10) → `#43516b` (z12) → `#323d54` (z13), halo white α0.7 → `#f8f8f6`. |
| our rebuild | OpenMapTiles `transportation` classes mapped in `map/style-flat-mapping.tsv` (motorway→FreewayControlled, trunk→MajorHighway, primary→Highway, secondary→ConnectorRoad, tertiary→LocalMajorRoad, minor→LocalRoad-MinorRoad, service→ServiceRoad, path→PrivatePath; "inferred" where OSM and Apple classes are not the same thing), widths/colours/visibility bands stepped from the rows above [`to_maplibre.py`]; 国道 from `transportation_name` by name prefix (OpenFreeMap has no `ref`/network on `transportation`). |
| gap | z5–8: OpenFreeMap z ≤ 8 tiles carry motorway/trunk/primary only — matches Apple's visibility (MajorHighway from z8, Highway from z10) except that Apple's expressway is purple from z6 and 2.25 px + stroke while the acceptance side-by-side shows ≈ 1 px faint purple (unresolved: a 'LowZoom' variant or the `Line-LowZoom-Connection-Base` rows may apply; not found); z12: `minor` absent from OpenFreeMap z11 tiles (data limit, `basemap/data/styl/README.md`); shields, ramps (`Ramp-*`), tunnels/bridges (`brunnel`) not drawn. |

### 7.6 Railways

| | |
|---|---|
| Apple data | `VECTOR_SPR_STANDARD`/`ROADS` lines with rail class; Japan → `Railway-Japan*` [vmp4, styl]. |
| look [styl] | `Railway-Japan.Light`: colour `#71a7ff`, width 1.0 at every zoom, stroke 0.25 (≤ z8) → 0.375 (z10–13) → 0.5 (z14+); **tick pattern (prop 280, inherited `Railway-Base`) by zoom: [4,8] ≤ z10, [4,12] z10–12, [4,16] z12–14, [4,20] z14–16, [4,24] z16–17, [4,32] z17+** (the base row's [4,48] is only the fallback); `Railway-Japan.Bullet-Light` (新幹線): white core 1.0–1.25 px with `#006fff` stroke 0.5, dash (prop 279, `Japan-Railway-Bullet-Base`) [28,28] z6–8, [36,36] z8–13, [48,48] z13–15, [84,84] z15–16, [108,108] z16–17, [128,128] z17+. Dash unit: the tropics' [12,12] measured 3/3 pt by the UI ⇒ **¼ pt per unit** (so z12 rail ticks = 1 pt on, 4 pt off). |
| our rebuild | N02 centre lines from `tiles/transit.pmtiles` (`rail`, `cls`); `rail-casing` dash `[2.29, 9.14]` = base [4,48] ÷ width [`to_maplibre.py`]; shinkansen dash `[48,48]` in MapLibre line-width units. |
| gap | dashes use the base row and the wrong unit: at z12 the sheet says ticks 1 pt / gap 4 pt (`[4,16]` × ¼ pt), shinkansen 9 pt / 9 pt; `to_maplibre.py` should take the zoom rows of 279/280 and convert ¼-pt → px ÷ line-width for `line-dasharray`. Colours and widths are already the sheet's. |

### 7.7 Buildings

| | |
|---|---|
| Apple data | `VECTOR_BUILDINGS_V2` (73) chapters 142 / 167 (footprints + heights), 147 landmarks; 3D landmark models from `VECTOR_SPR_MODELS` (`DVas`) [vmp4]. |
| look | `BuildingFootprint.Light-Explore`: fill = `buildingFlatColor` (86) `#eeeee7`, outline `#cccbc8` (≤ z15) → `#e9e9e2` / `#d9d7d4` (z16+) [styl]; extruded in the elevated map with the ground light and `DaVinci::Shadow` (shadow buffer unbound in the capture ⇒ no cast shadows in the plain map). |
| our rebuild | OpenMapTiles `building` fill-extrusion with the sheet colours [`to_maplibre.py`]. |
| gap | Apple's footprints are its own data; landmark models not drawn; fine at z12 (part of the accepted diff). |

### 7.8 Borders

| | |
|---|---|
| Apple data | `VECTOR_SPR_STANDARD` lines with admin level [vmp4]. |
| look [styl] | country `Border-Country.Non-Disputed-Light`: fill `#b3009e` α0.8 (≤ z7) → α0.7 (z8+), stroke `#b3009e` α0.2–0.3, width 1.45 (z5) → 1.55 (z6–7) → 1.75 (z8–9) → 1.95 (z10–11) → 2.1 (z12–13) → 2.25 (z14+), stroke width 0.25 → 1.35 → 1.95 → 2.1 → 2.75 → 3.25, dash [48,12,48,12,12,12] z6–12 → [64,16,64,16,16,16] z12+; **prefecture** `Border-State.Explore-Light`: fill `#b3009e` α0.7 (z5) / α0.8 (z6–7) / α0.65 (z8–9) / α0.7 (z10+), stroke α0.2 → 0.35, width **0.9 (z5) → 1.05 (z6–7) → 1.25 (z8–11) → 1.75 (z12+)**, stroke width 0.25 → 0.5 → 1.1 → 2.25, dash [18,4,10,4,4,4] z6–12 → [24,6,12,6,6,6] z12–16; prop 12 (opacity, inferred 0.25). Tropics/equator (also on the flat map): `Geolines-*`, §7.13. |
| our rebuild | OpenMapTiles `boundary` admin_level 2 / 4 with the rows above, `line-opacity` 0.25 (inferred prop 12), dash from the *base* row [`to_maplibre.py`]. |
| gap | dash rows by zoom + ¼-pt unit (same fix as rail); the meaning of prop 12 (0.25) is still inferred. |

### 7.9 Labels

| | |
|---|---|
| Apple data | chapters 10/11/13 labels + 20 strings + 141 placement in `SPR_STANDARD` / `SPR_ROADS`; POIs in `VECTOR_POI_V2` (68) chapter 30 + 144 + 160 [vmp4]. |
| look [styl] | **cities** `City-Label-LMZ-05` (largest): height 10.5→12.5 (z5–7), 14→16 (z8–9), 16→28 (z10+), font medium-G1 (z5) → semibold (z6–7) → bold (z8–11) → semibold (z12+), width=90, colour `#1c1c1c` (≤ z11) → `#5a5e5e` (z12+), halo `#f8f8f6` α0.8; `LMZ-07`: 10.5 (z5), 9.5→10.5 (z6–7), 10.5→12.5 (z8–9), 15→27 (z10+), medium-G1 → semibold (z10–13), colour `#4c4c4c` → `#1c1c1c` (z8) → `#5a5e5e` (z12); `LMZ-09`: 12.5→14.5 (z10), 17→23 (z12), medium-G3 at z12; `LMZ-12`: 13→15 (z12), 15→17.5 (z13), 17.5 (z14). **Prefectures** `State-Label-Small`: visible z7–10 only, 13→16 pt, semibold width=90, `#7c365f`, halo `#f8f8f6` α0.8. **Wards** `SubMuni-Ward`: visible z10–14, 10.5→12.5 (z10), 14→16 (z12), 16→18 (z13), `%$default,semibold,width=60` (a 60 %-width face), `#5a5e5e`, no halo, `textSizeScale` 0.45–0.5. **Countries** `Country-Label-Medium`. **Road names** §7.5. **Water names** `Lake-Label.Zoom9-*`, `Ocean-Points.Large-*` (`basemap/data/styl/README.md`). `labelColorLumAdjustment` (463/464) is applied after the colour. |
| our rebuild | OpenMapTiles `place` classes → `City-Label-LMZ-05/07/09/12` by rank, `suburb` → `SubMuni-Ward` (uppercase, letter-spacing 0.1), `State-Label-Small` for prefectures, `Country-Label-Medium`; fonts Noto Sans Regular/Bold/Italic only [`to_maplibre.py`, mapping tsv]. |
| gap | z5–8: OpenFreeMap has `place` city ranks but Apple's LMZ classes are its own ranking — the rank→LMZ mapping is inferred; `width=60/90` faces and `medium-G1/G3` weights do not exist in Noto → nearest weight; `suburb` (ward) only from z12 tiles; which labels win is Apple's collision solver. |

### 7.10 POIs, shields, station icons

| | |
|---|---|
| Apple data | POIs: `VECTOR_POI_V2` (68) chapter 30 (+144 addendum, 160 annotation labels, 151 MZR overrides), `VECTOR_STREET_POI` (56) storefronts; stations: transit POIs in the same chapters + `VECTOR_TRANSIT` (37) chapters 128/129 (systems / network) for lines; shields: the road feature's route ref in chapter 31 [vmp4]. |
| look | icons from the icon packs in `~/Library/Caches/GeoServices/Resources`: `Default_Icons-30641.icondatapack` + `-30644.iconconfigpack` (1×), `-19105@2x` / `-19109@2x` (2×), shields `Default_Shields-2100/2102` (+`@2x`), `Railroad_Crossing-*`, fonts `SFShields*.otf` for shield text; category → icon id in `POITypeMapping-9.json` (`GEOPOICategory*` → feature type ids); POI label styles `POI-*` in the sheet (globe variants in `globe-key-numbers.tsv`) [res, styl]. The packs are `ICONCONFIGPACK` / icon data containers (compressed; format not decoded). |
| our rebuild | none yet (no POI, shield or station icon layer in the flat style). |
| gap | data: OpenMapTiles `poi` (class/subclass) and `transportation_name` refs exist; icons: SF Symbols on the web are not available — the pack decode would give Apple's exact glyphs (not done, format unknown); until then: the station icon as the Kit component the UI already has, POIs off (Apple's POI density is its own ranking anyway). |

### 7.11 Glow, fog, shadow, sky

| | |
|---|---|
| glow | coastline glow (§7.2) and label halos (`labelHaloColor`, e.g. `#f8f8f6` α0.8 for cities, none for wards) [styl]; road casings are the `strokeWidth` outlines, not glows. |
| fog / sky | `Fog::fog_*` and `Sky::sky_*` [air] with `GroundAtmosphere.skyTop/Bottom` = `Sky-Standard-Day` colours [cap, styl] only draw when the camera is pitched (horizon visible); top-down views have neither, and the ground fog term is 0 (`fogParameters.w = −inf`) [cap]. |
| shadow | `DaVinci::Shadow` / shadow map unbound, `shadowsEnabled` off in the plain map [cap]; building extrusion has no cast shadow; SSAO off. |
| our rebuild | no fog/sky (correct for top-down); halos from the sheet; no coastline glow (gap, §7.2). |

### 7.12 z5–8 vs z12 — the differences in one list

| item | z5–8 (Apple) | z12 (Apple) | source |
|---|---|---|---|
| ground | `#ebeddf`–`#f5f5eb` | `#f7f6f2` | styl `Landcover-Ground.Light-Elevated` |
| vegetation | raster classes, dry-tint delta H−24°/−12° (z7–9) | raster classes, no climate delta from z9; OSM-like polygons on top | styl + `groundSettings.json` |
| relief | exaggeration 3.25 → 1.4, sharpness 0.94 → 0.9 | 1.25, sharpness 0.78 | `groundSettings.json` |
| expressway | 2.25 px purple `#c2b3e0`/`#9e8dbf` from z6 (grey at z5) | 3.75 px `#b9aed1`/`#897ba6` | styl `Line-FreewayControlled.Light-JPN-Elevated` |
| 国道 purple | not drawn (hidden ≤ z9) | 2.55 px `#b9aed1`/`#897ba6` (from z10) | styl `…ClassOne-Elevated` |
| trunk / primary / secondary | 0.5 px from z8 (trunk) / hidden | 2.55 px `#edf0f5`/`#a1b0d1` | styl |
| minor roads | hidden | 1.5 px `#e1e6e6`/`#dadada` | styl |
| prefecture border | 0.9–1.25 px, dash [18,4,10,4,4,4] | 1.75 px, dash [24,6,12,6,6,6] | styl `Border-State.Explore-Light` |
| rail | 1 px `#71a7ff`, ticks [4,8]–[4,12] | 1 px, ticks [4,16]; shinkansen dash [36,36] | styl `Railway-Base` 280 / `Japan-Railway-Bullet-Base` 279 |
| city names | LMZ-05 10.5–16 pt bold `#1c1c1c` | LMZ-05 16–28 pt semibold `#5a5e5e`; LMZ-09/12 appear (17 / 13 pt) | styl |
| prefecture names | `State-Label-Small` 13–16 pt `#7c365f` (z7–10) | hidden | styl |
| ward names | hidden | `SubMuni-Ward` 14–16 pt width=60 `#5a5e5e` (z10–14) | styl |
| coastline glow | none (≤ z8) | 8 px `#8adaf4` | styl `Coastline-Glow-*` |
| sea | ramp by depth (deep bands visible) | ramp by depth (0–100 m colours) | cap |
| POI / stations / shields | none | POI icons + station icons + shields from the icon packs | res |

### 7.13 Tropics / equator lines — resolved

`Geolines-Tropics.Explore-Light-Elevated` / `Geolines-Equator.*` / `Geolines-Polar.*` in `default-56689.styl` (not in
the globe sheet — the globe draws them from the flat sheet): fill `#49587a` (rgb 73,88,122) α 0.45 (z0–2) → 0.5
(z2–4) → 0.6 (z4–8) → 0.7 (z8+), `fillColorLumAdjustment` −15, width 1.15 (tropics; equator 1 → 1.5 → 1.9),
dash [12,12] (< z4) → [16,16] (z4–8) → [24,24] (z8–12) → [32,32] (z12+) in ¼-pt units = 3/3 pt at globe zoom (the
UI measured 3/3 pt `#6b8098`: the colour is `#49587a` at α0.5 over land after the −15 luminance step); labels
"Tropic of Cancer" from the same style: `%$default,medium-G3,width=90`, 6.5 → 7.5 (z2) → 9 (z4) → 10 (z8) → 12 pt,
colour `#49587a`, halo `#c2dbea` α0.15, spacing 500–1200. Dark: `#839bce` α0.3, text `#7e95c7`. §6's "not
located" row is closed by this.

### 7.14 Still sampled or fitted on the flat map

| value (UI file) | verdict |
|---|---|
| `palette-ocean.json` depth bands (snapshotter) | **decoded**: ramp(§2.3) — the flat sea is the same ramp; bands are its samples |
| `palette-land.json` tints + hill-shade classes | **decoded**: land-cover class colours by zoom [styl] + climate delta [res]; the hill-shade "lit/shaded" split is the n·L term with the sheet colour as albedo |
| hill-shade azimuth 260°, exaggeration calibration | **decoded**: 240°/65°, `groundElevationScale(z)`; `normalsSharpnessBias` use not decoded |
| the ≈ 1 px faint expressway at z6–8 vs the sheet's 2.25 px | **open** — no low-zoom row found; candidates `Line-LowZoom-Connection-Base`, a `*-LowZoom` variant, or the `Elevated` variant's `strokeRenderOrder`; next: dump every style whose name contains `Freeway` at z6 |
| road density / label density | not a number: Apple's placement and collision; accepted difference |
| dash unit (¼ pt) | **inferred from two measurements** (tropics 12 ↔ 3 pt, rail ticks) — confirm on one more (border [18,4,…] ↔ 4.5/1 pt) |
| icon glyphs (POI, shields, stations) | **not decoded** (icon packs); Kit components meanwhile |
