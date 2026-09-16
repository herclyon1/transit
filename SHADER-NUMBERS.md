# Apple Maps ground / globe shading: the shader formulas and the numbers they run on

Recovered 2026-09-16 from macOS 27 `VectorKit.framework/Resources/default.metallib` (AIR bitcode inside the MTLB
container, read with `xcrun clang -x ir -S -emit-llvm`; no Metal Toolchain installed) plus the constants VectorKit
binds at run time, captured in-process from an `MKMapView` (realistic elevation) by hooking the Metal encoder.
The point of the exercise: replace the values the UI session *fitted* from screenshots
(`ui/basemap/shading-globe.json`: `factor = 0.7526 + 0.3167·(n·L)`, `L = (−0.436, −0.251, 0.864)`) with what the
renderer actually computes.

Everything numeric lives in [basemap/data/shader/shader-numbers.json](basemap/data/shader/shader-numbers.json)
(captured buffers/textures, linear RGB with sRGB companions). Tools in `pipeline/basemap/shader/`:

| tool | does |
|---|---|
| `metallib_dump.py` | parses the MTLB container (`--list`, `--extract NAME out.bc`, `--strings NAME`) |
| `ir2pseudo.py` | LLVM IR → readable pseudo-code, uniform members named from `air.struct_type_info` |
| `structs.py` | prints every uniform struct of a shader with byte offsets; with a `capture.json` decodes the captured bytes field by field |
| `capture.m` | the capture harness: hooks `newRenderPipelineState…` and the encoder's `set{Fragment,Vertex}{Bytes,Buffer(s),Texture(s)}`, dumps buffers + textures of the DaVinci / globe shaders |
| `probe_settings.m` | prints the `VKDebugSettings` defaults the atmosphere code reads |
| `numbers.py` | capture directories → `shader-numbers.json` |

Reproduce: `clang -fobjc-arc -framework AppKit -framework MapKit -framework Metal -framework CoreGraphics -framework CoreLocation -o /tmp/capture pipeline/basemap/shader/capture.m`, then
`/tmp/capture 35 135 20 30 out 15 [pitch heading dark]` and `numbers.py --light out …`.

Sources per number: **[cap]** = captured uniform/texture, **[air]** = shader bitcode, **[vk]** = VectorKit
decompile (`~/Money/styl-work/vk/VectorKit_NN.mm`, iOS 26.1) confirmed against the macOS binary where noted,
**[styl]** = `default-iosmac-11358.styl` decoded with `pipeline/basemap/styl`, **[json]** = `groundSettings.json`.

## 1. Which shaders draw what

| pass | vertex / fragment | what |
|---|---|---|
| ground tiles (flat map and the globe's cube faces) | `DaVinci::ground_base_vertex` / `DaVinci::ground_fragment` | terrain mesh, land-cover albedo, water-depth gradient, lighting, fog |
| globe surface | `DaVinci::globe_texture_vertex` / `globe_texture_fragment` | draws the S2 cube-face textures the ground pass rendered; fragment is only `sRGB→linear(texel)` — no lighting here |
| globe halo | `GlobeAtmosphere::globe_atmosphere_vertex` / `_fragment` | the blue rim around the globe |
| flat-map sky / fog | `Sky::sky_*`, `Fog::fog_*` | sky quad above the horizon, fog strip |
| stars | `GlobeStars::*`, `Stars::*` | white points with alpha |

Function constants that pick code paths (all `[air]`): `globeLightingEnabled`, `ecefCoordinates`, `needsAtmosphere`,
`landCoverEnabled`, `climateTintingEnabled`, `waterDepthEnabled`, `waterDepthBlendEnabled`, `specularEnabled`,
`shadowsEnabled`, `ssaoEnabled`, `tileClippingEnabled`, `splineEnabled`. In the captured configuration the
specular, shadow, SSAO, emissive, material, colour-correction and route-mask buffers are never bound, i.e. those
paths are off for the plain map.

## 2. Uniform structures (byte offsets from `air.struct_type_info`)

`Lighting::LightConfigurationVertex` (16 B, vertex slot 5): `half4 lightColor` @0, `half4 ambientLightColor` @8.
`Lighting::LightConfiguration` (32 B, globe atmosphere slot 1): `half4 lightDirection` @0, `lightSpecularColor` @8, `lightColor` @16, `ambientLightColor` @24.
`DaVinci::Style` (8 B, vertex slot 7): `half4 tileLightDirection`.  `DaVinci::StyleSunMatrix` (4 B, slot 8): `half2 sunMatrixCosSin`.
`DaVinci::StyleTransitionToFlat` (2 B, slot 9): `half transitionToFlatLighting`.
`DaVinci::GroundAtmosphere` (32 B, slot 10 both stages): `half4 skyBottomColor` @0, `half4 skyTopColor` @8, `half4 fogParameters` @16, `half2 horizonGlowParameters` @24.
`DaVinci::StyleCameraLighting` (16 B, slot 12): `float3 cameraPositionInTileSpace`.
`DaVinci::LandCoverSettings` (4 B, fragment slot 6): `float maxIndex`.
`DaVinci::GradientParameters` (32 B, fragment slots 14/15): `float depthGradientScale` @0, `depthGradientOffset` @4, `blendFactor` @8, `float4 blendColor` @16.
`DaVinci::StyleBlend` (2 B, slot 16): `half blendFactor`.  `DaVinci::StyleGroundOcclusion` (4 B, slot 11): `half2 params`.
`DaVinci::MaterialStyle` (4 B, slot 13): `half2 specularityAndShininess`.  `Lighting::LightSpecularConfiguration` (16 B, fragment slot 0): `half4 lightDirection`, `half4 lightSpecularColor`.
`Lighting::StylizedShadingSettings` (8 B, slot 26): four halves `chromaPreservedShadowThreshold, steepnessDarkeningFactor, steepnessDarkeningThresholdMin/Max`.
`Tile::Transform` (368 B, vertex slot 2) carries `earthCenterLocal` @288, `boundsScale` @304, `distanceScale` @320, `worldZScale` @344, `groundZScale` @348.
`GlobeAtmosphere::AtmosphereConstants` (240 B): `projection` @0, `earthCoronaModelview` @64, `float4 primaryLightDirection` @128, `horizonDistance` @144, `outerRadius` @148, `innerRadius` @152, `colorMidPoint` @156, `lightingEnabled` @160, `horizonScreenY` @164, `screenHeight` @168, `float4 horizonColor` @176, `midColor` @192, `endColor` @208, `nightLightFade` @224.
`Sky::Style` (64 B): `skyStartOffset` @0, `float4 horizon` @16, `float4 color` @32, `screenHeight` @48.  `Fog::Skyfog` (64 B): `float4 fogSlope`, `fogOffset` @16, `screenHeight` @20, `skyOffset` @24, `float4 skyBottomColor` @32, `skyTopColor` @48.
`FlyoverCommon::Shared` (128 B, globe texture pass): `projection`, `float3 atmospherecolor` @64, `float2 horizonvalues` @80, `float3 lightdirection` @96, `nightlightfade` @112.

Fragment textures of `ground_fragment`: 1 shadow, 2 tex, 3 occlusion, 4 routeMask, 5 emissive, 6 overlay,
7 `styleIndexTexture` (R8, 1024², land-cover class index per tile), 8 `styleTexture` (RGBA8, 3 × 3·classes, the
climate-tinted palette), 9 `aridityTexture`, 10 `temperatureTexture` (R8 128², climate codes), 11 `gradient1Texture`
(RGBA8 256×1, water-depth ramp), 12 `gradient2Texture`. Vertex texture 0 `ambient` = irradiance cube (RGBA8 8² × 6).

## 3. Formulas `[air]`

### 3.1 ground_base_vertex — lighting per vertex
```
n        = normalize(normal from the Normals buffer (half2, xy; z rebuilt), tile space)
           globe path (globeLightingEnabled && ecefCoordinates): n re-expressed in the tangent basis of the
           curved tile (rows built from Tile::Transform, earthCenterLocal), so L below is a *view-fixed* light
direct   = clamp(dot(normalize(style.tileLightDirection.xyz), n), 0, 1) * lightColor.rgb      (× (1 − transitionToFlatLighting))
indirect = ambient_cube.sample(n).rgb * ambientLightColor.rgb            (mix(indirect, 1, transitionToFlatLighting))
atmos    = needsAtmosphere ? clamp(((1 − hg.x) + hg.x * clamp((1 − dot(viewDir, n)) / fogParameters.w, 0, 1)) * hg.y, 0, 1)
                             * ambientLightColor.rgb * skyBottomColor.rgb : 0        (hg = horizonGlowParameters)
```
### 3.2 ground_fragment
```
occlusion = mix(1, clamp(n.z + dist / groundOcclusion.params.x) * 0.5 + 0.5, groundOcclusion.params.y)   (buffer unbound → 1)
light     = occlusion * indirect + shadow * direct  (+ specular: ((spec*0.0398)*(shininess+8)) * pow(max(0,R·V),shininess) * lightSpecularColor, off)
index     = rint(styleIndexTexture.r * landCoverSettings.maxIndex)                     (maxIndex = 255 [cap])
albedo    = climateTintingEnabled
            ? styleTexture.sample(u = ((temperatureTexture.r − 3/255)·85 + 1.5) / W,
                                  v = (index·3 + 1.5 + (aridityTexture.r ≥ 3/255 ? 127.5 : 85)·(aridityTexture.r − 3/255)) / H)
            : styleTexture.read(1, index·3 + 1)                                           (row H ≤ index → white)
water     = waterDepthEnabled && albedo.a < 0.999:
            t = saturate((log2(waterDepth) + depthGradientOffset) * depthGradientScale)
            albedo = gradient1Texture[t]   (waterDepthBlendEnabled: mix with gradient2Texture[t2] by styleBlend.blendFactor)
colour    = albedo.rgb * light (+ emissive) + atmos ;  fog: mix(colour, mix(skyTopColor, skyBottomColor, f(ndc.y, fogParameters)))
out       = linear rgb (render target is sRGB, encoded on write)
```
Temperature codes in the R8 texture: 0 / 3 / 6 (·1/255) select palette columns 0 / 1 / 2 (arctic / base / veryHot);
aridity codes 0 / 3 / 5 select the class's rows 0 / 1 / 2 (veryWet / base / veryDry); in-between codes interpolate
(the sampler is linear). `[cap]` shows real tiles carry codes 0…6, so most pixels are blends.

### 3.3 globe_atmosphere (the rim) — fragment, `outsideAtmosphere` branch
```
t1 = clamp((distance − innerRadius) / ((outerRadius − innerRadius) * colorMidPoint), 0, 1)
c  = mix(horizonColor, midColor, t1)
t2 = clamp((distance − (innerRadius + (outerRadius − innerRadius) * colorMidPoint)) / ((outerRadius − innerRadius) * (1 − colorMidPoint)), 0, 1)
c  = mix(c, endColor, t2)
c *= mix(1, lightIntensity, nightLightFade)
light = lightColor * lightIntensity + ambientLightColor * (1 − nightLightFade)
c *= mix(1, light, lightingEnabled)
inside branch: mix(midColor, horizonColor, clamp(position.y / ((1 − horizonScreenY) * screenHeight), 0, 1))
vertex: lightIntensity = night ? clamp(0.7 * (L·z)^8 + max(1 − dot(pos, −3L), 0), 1 − nightLightFade, 1)
                              : 0.25 * (dot(primaryLightDirection, pos) + 1)^2
```
CPU side `[vk]` `md::GlobeSkyRenderLayer::layout` (VectorKit_44.mm:7582; constants re-read from the macOS binary at
`__ZN2md19GlobeSkyRenderLayer6layoutERKNS_13LayoutContextE`):
```
R  = 6356752.31 m (WGS84 polar radius; innerRadius stored as float 6356752.5)
h  = max(|camera| − R, 100)
horizonDistance = sqrt(h·(h + 2R)) / R                       (1.57313035e-7 = 1/R)
outerRadius     = R + h + horizonDistance · 1.1R · tan(fov/2) (6992427.55 = 1.1R)
near (h < maxHeight):   colorMidPoint = 1, lightingEnabled = (zoom < 4 ? 1 : 0), horizonScreenY = camera value, screenHeight = view height px
far  (h ≥ maxHeight):   t = clamp((h − maxHeight)/maxHeight, 0, 1); colorMidPoint = 1 − t·colorMidpointSetting;
                        lightingEnabled = t; outerRadius = outerRadius + t·((maxHeight + R) − outerRadius)
maxHeight = 150000 m, colorMidpointSetting = 0.5        (VKDebugSettings daVinciAtmosphereMaxHeight / …ColorMidpoint, [probe_settings.m])
midColor     = SkyLogicContext fill    = style "Sky-Standard-Day" fillColor   rgb(155,196,237)  [styl]  (night: "Sky-Standard-Night" rgb(35,76,122))
horizonColor = SkyLogicContext horizon = same style, stream prop 202           rgb(212,226,240)  [styl]  (night: rgb(86,109,165))
endColor     = (0, 0, 0, 1)  constant                                                             [vk, macOS binary 0x1c3545b80]
primaryLightDirection = normalize(modelview · LightingLogicContext.lightDirection)
nightLightFade        = LightingLogicContext + 456 (0 in daytime style)
defaults when no style: kSkyDayDefaultFillColor (0.71, 0.87, 0.93), kSkyDayDefaultHorizonColor (0.93, 0.93, 0.93)
```
`SkyLogic` copies the sheet colour as u16/65535 without linearising (VectorKit_37.mm:3216); the ground pass receives
the same two colours *linearised* (§4.2), so treat the rim colours as sRGB values.

### 3.4 Sky / Fog (flat map)
`Fog::fog_vertex`: `colour = mix(skyBottomColor, skyTopColor, clamp(((ndc.y·0.5 + 0.5) − skyOffset)·10, 0, 1))`;
`Sky::sky_fragment` returns the interpolated `skyColor`. `Stars`: white, alpha from the vertex.

### 3.5 Light direction on the CPU `[vk]` `md::LightingLogic::writeLogicContext` (VectorKit_36.mm:1493)
```
L = (sin(az)·cos(alt), cos(az)·cos(alt), sin(alt))       az, alt in radians
az  = base + sceneStyle.azimuth°          base: mode 0 → real sun azimuth (NSDate + location), mode 2 → π − camera heading, else 0
alt = max(v + sceneStyle.altitudeOffset°, sceneStyle.altitudeFloor°)   v: mode 0 → real sun altitude, 1 → 0, 2 → π/2 − pitch, else π/2
lightColor / ambientLightColor / specular: scene-style colour props 15 / 16 / 19 (defaults 0.85083 grey, …)
```
The scene-sheet property ids (`gss::ScenePropertyID`) have no decoder table yet, so the sheet-side numbers are not
named; the *result* is captured below.

## 4. Values

### 4.1 Lighting `[cap]` — identical at spans 1°/20°/120°, pitch 0/45°, heading 0/30°, light and dark
| | value |
|---|---|
| `tileLightDirection` | (−0.36597, −0.21130, 0.90625) — azimuth **240°** clockwise from north (+y), altitude **65.0°**; view-fixed (x right, y up/north, z toward viewer) |
| `sunMatrixCosSin` | (−0.5, −0.86621) = cos/sin 240° |
| `lightColor` | 0.7085 grey (linear) |
| `ambientLightColor` | 0.49683 grey (linear) |
| `transitionToFlatLighting` | 0 |
| `tileLightDirection.w` | 0.117 / 0.209 / 0.712 at span 120° / 20° / 1° — zoom-dependent, meaning unresolved |
| irradiance cube | 8×8×6 RGBA8, face means (+x −x +y −y +z −z) = 0.875 0.836 0.856 0.859 0.812 0.840; full texels in the JSON |

So the per-vertex light is `light(n) = 0.4968 · cube(n) + 0.7085 · max(n·L, 0)` (linear; cube ≈ 0.81–0.88), the
same numbers in dark mode.

### 4.2 Ground atmosphere (sky colours, fog) `[cap]`
| | light | dark |
|---|---|---|
| `skyTopColor` (linear → sRGB) | (0.328, 0.552, 0.847) → `#9bc4ed` = Sky-Standard-Day fill rgb(155,196,237) `[styl]` | (0.017, 0.072, 0.195) → `#224b7a` = Sky-Standard-Night fill rgb(35,76,122) |
| `skyBottomColor` | (0.658, 0.761, 0.872) → `#d4e2f0` = Sky-Standard-Day prop 202 rgb(212,226,240) | (0.093, 0.153, 0.376) → `#566da5` = Sky-Standard-Night prop 202 rgb(86,109,165) |
| `fogParameters` | (0, 1, 462.5, −inf) | same |
| `horizonGlowParameters` | (2.0, 0.5) | same |

`fogParameters.w = −inf` makes the horizon-glow term `clamp((1−hg.x) + hg.x·0)·hg.y = clamp(−0.5) = 0`: the atmosphere
contribution is off on the plain map.

### 4.3 Water-depth gradient (ocean colour) `[cap]`
`depthGradientScale = 0.051501`, `depthGradientOffset = 6.643856`, `blendFactor = 0`, gradient2 unbound → single ramp.
`t = saturate((log2(depth_m) + 6.6439) · 0.0515)`: depth 0.01 m → 0, 1 m → 0.34, 10 m → 0.51, 100 m → 0.68, 1000 m → 0.86, 7 km → 1.
Ramp (RGBA8 linear, 256 texels, sRGB companions in the JSON): light `#91daf3` (t=0) → `#5abdf5` (0.75) → `#0d8ae2` (1);
dark `#1c3b86` → `#16265a` → `#000d22`. Same ramp at every zoom/place tested. The ramp is a material colour ramp
(`md::ColorRampData` via `MaterialTextureManager`), not a `.styl` colour — its source file is not decoded here.

### 4.4 Land-cover palette `[cap] [styl] [json]`
The palette texture is built per tile: 3 columns × 3 rows per class present in the tile, RGBA8 **linear**.
The base cell (column 1, row 1) is the sheet colour of the class's `Landcover-<Class>.Light-Elevated` /
`.Dark-Elevated` style (`fillColor` at the tile zoom) linearised — e.g. Forest z5 rgb(176,222,144) → linear
(111,186,71) ≈ captured `#6dba47`; Wetlands rgb(175,230,168) → `#6bc963`; Cultivated rgb(199,235,152) → `#90d34e`;
Herbaceous rgb(188,230,151) → `#7ec94d`; Shrubland rgb(228,235,192) → `#c1d37b`; Barren rgb(240,236,216) → `#dcd3ad`;
IceSnow rgb(245,245,245) → `#e8e8e8`; Ground rgb(235,237,223) → `#d3d5bc`; Water → alpha 0 (depth ramp instead).
The other 8 cells are HSV adjustments of the base in linear RGB, additive per axis, from `groundSettings.json`
(band by tile zoom):

| band | veryHot (col 2) | arctic (col 0) | veryDry (row 2) | veryWet (row 0) |
|---|---|---|---|---|
| z1–6 | V +0.1 | S −0.2 | H −35°, V +0.1 | 0 |
| z6–7 | V +0.1 | S −0.2 | H −35°, V +0.1 | 0 |
| z7–8 | V +0.1 | S −0.1 | H −24°, V +0.06 | 0 |
| z8–9 | 0 | 0 | H −12°, V +0.03 | 0 |
| night z1–9 | S +0.1, V +0.01 | H +3°, S −0.1 | H −4°, V +0.02 | H +6°, S −0.05 |

Checked against every tinted cell of the z5 captures: max error 2/255. Ground, Developed, IceSnow-like classes are
untinted (all 9 cells equal). `groundSettings.json` also gives `groundElevationScale` (14 at z1 … 1.25 at z11–15 … 1
from z17) and `normalsSharpnessBias` (0.95 → 0.73). All observed class palettes (light z5, dark z5, light z8) are in
the JSON under `landcover_palettes`.

### 4.5 Globe rim (`AtmosphereConstants`) — not bindable in-process
`MKMapView` never leaves the flat/curved-tile path (no `GlobeAtmosphere` pipeline even at a 120° span), so these come
from §3.3 `[vk]` + `[styl]` + `[probe]`: colours Sky-Standard-Day/Night, `endColor` black, `R`, `maxHeight = 150 km`,
`colorMidpoint = 0.5`, lighting on only for zoom < 4 (near) or faded in by `t` (far); `LightConfiguration` for the
rim is the same `LightingLogicContext` as the ground pass → same L, 0.7085 / 0.4968 colours.

## 5. Against the UI fit (`ui/basemap/shading-globe.json`)

| | UI fit (from screenshot, sRGB G channel) | renderer |
|---|---|---|
| model | `factor(n) = (0.7526 + 0.3167·n·L) / (0.7526 + 0.3167·Lz)` applied to the sRGB pixel | `rgb_lin = albedo_lin · (0.4968·cube(n) + 0.7085·max(n·L,0))`, then sRGB-encode |
| L | (−0.436, −0.251, 0.864): az 240.1°, alt 59.8° | (−0.366, −0.211, 0.906): az **240°** ✓, alt **65°** |
| frame | camera space, x right, y up, z toward camera | same (view-fixed light, does not rotate with the globe) ✓ |
| terminator | never dark: factor ≥ 0.733 (n·L = 0) | ambient floor 0.4968·cube ≈ 0.42 linear ≈ 0.66 of the centre after sRGB |

Equivalent sRGB-space factor of the real formula (relative to n·L = Lz, cube ≈ 0.84, gamma ≈ 2.2):
n·L = 0 → 0.66, 0.25 → 0.77, 0.5 → 0.87, 0.75 → 0.95, 1 → 1.03; the fit gives 0.73 / 0.81 / 0.89 / 0.96 / 1.04 —
close over the fitted range (r ≤ 0.8 of the limb, where n·L ≳ 0.3), too flat near the limb. Replace the fit by the
linear formula with albedo = the ramp/palette colour, or keep the fitted form with `a = 0.42`, `b = 0.7085` applied in
linear light and the altitude corrected to 65°.

## 6. Unresolved
- Scene-sheet lighting properties (`scene-1148.styl`, `gss::ScenePropertyID`) cannot be named: no decoder/remap
  table for that enum yet. The 240° / 65° / 0.7085 / 0.4968 are the run-time results, the sheet-side encoding
  (which 9-bit values, which `client:81` variant) is not mapped. Mode flags (real-sun vs fixed) were not
  exercised: the capture shows the fixed light.
- `tileLightDirection.w` (0.12–0.71, zoom dependent) — role not identified.
- The Maps app's globe view could not be captured in-process; rim constants are from the decompile only, and
  the globe's own texel content (S2 faces rendered from VMP4 globe tiles) is out of scope (VMP4 not decoded).
- Water-depth ramp and `GradientParameters` come from `ColorRampData` (material resources), not the `.styl`;
  the file that defines them is not decoded — the captured ramp is the ground truth.
- Palette rows are tile-local class indices; class names were assigned by matching linearised sheet colours,
  not by reading the land-cover index texture against a class list (the VMP4 land-cover legend is not decoded).
  Two untinted vegetation-green bases ((104,188,46), (157,220,110), z2–3 tiles) did not match a sheet colour.
- Shadow, SSAO, specular, stylised-shading, colour-correction buffers were never bound (function constants
  off in the plain map) — their values are unknown, not needed for the flat/globe look.
