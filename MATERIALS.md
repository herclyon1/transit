# macOS 26 system materials: what the Maps chrome is actually made of

Scope (acceptance request 2026-09-16): the sidebar, the Map Modes popover, the right-column glass buttons, the place
card and the search field of the Maps app are not drawn by VectorKit — they are system materials. This document
gives the recipes the system uses, with the file / API they were read from, and what of each recipe can be done in
CSS. Nothing here is sampled from the screen; every number comes from a plist, a binary, or from instantiating the
system view in-process and reading the CoreAnimation tree it builds.

Files (all under `materials/`, produced by `pipeline/materials/`):

| file | what | tool |
|---|---|---|
| `corematerial-recipes.json` / `.tsv` | all 49 `*.materialrecipe` / `*.descendantrecipe` and 22 `*.visualstyleset` / `*.descendantstyleset` of `/System/Library/PrivateFrameworks/CoreMaterial.framework/Versions/A/Resources/` (descendants resolved) | `dump_recipes.py` |
| `appkit-materials.json` | layer trees of every `NSVisualEffectMaterial` (light + dark, behindWindow + withinWindow), `NSGlassEffectView` regular / clear / tinted, `NSPopover`, and the `CASDFGlass*Effect` defaults | `dump_appkit_materials.m` |
| `catalyst-materials.json` | layer trees UIKit-on-Mac builds for every `UIBlurEffect` system style, `UIGlassEffect` regular / clear / tinted / interactive, a `UISplitViewController` sidebar column, `UINavigationBar`, `UIToolbar`, `UISearchBar`, a glass `UIButton`, a popover | `catalyst_probe/` (a 200-line Mac Catalyst app, `build.sh`) |

`pipeline/materials/summarize.py` regenerates the tables below from the two JSON dumps.

## 1. The three material systems, and which one Maps uses

1. **CoreMaterial recipes** (`*.materialrecipe`, MaterialKit `MTMaterialView`) — the iOS/iPadOS material engine:
   backdrop blur + saturation + brightness + a *luminance remap* (`luminanceAmount`, four `luminanceValues`
   against `luminanceColorMap.png`, a 256×1 LUT) + optional 4×5 colour matrix, plus fill/stroke "visual style
   sets" (vibrant colour matrices) for content drawn on top. UIKit maps `UIBlurEffectStyle` to these by name in
   `_convertStyleToRecipe(UIBlurEffectStyle, _UIVisualEffectEnvironment *)` (UIKitCore; the Catalyst copy imports
   exactly `MTCoreMaterialRecipePlatformContent{UltraThin,Thin,,Thick}{Light,Dark}`, `PlatformChrome{Light,Dark}`,
   `Platters`, `PlattersDark`, `Modules`, `ModulesSheer`, `PreviewBackground`).
   **On this Mac that path is not taken** — see 2. The four `platformContentGlass*` recipes, `platformSelected /
   Pinched / Disabled` and `toolbarButtonBackground` are referenced by no dylib in the macOS shared cache except
   CoreMaterial itself (grep of all 4 088 extracted images); they are not the Liquid Glass.
2. **AppKit `NSVisualEffectView` materials** (CoreUI, `NSVisualEffectViewCoreUIImpl`) — `CABackdropLayer` with
   `sdrNormalize → gaussianBlur(30) → colorSaturate(n)` plus tint layers (a translucent fill, an opaque
   darken/lighten-blend fill, a 5 % `CAChameleonLayer`). **Maps is a Mac Catalyst app** (`otool -L Maps`: it links
   `/System/iOSSupport/…/UIKit`, `SwiftUI`, `MapsUI` through `UIKitMacHelper`), and on the Mac a `UIBlurEffect`
   becomes one of these AppKit materials (§3, probed: `<UIBlurEffect material=6 …>` = `NSVisualEffectMaterial` 6 =
   popover, with byte-identical layer trees).
3. **Liquid Glass** (macOS 26 / iOS 26) — a `CABackdropLayer` carrying one CoreAnimation filter `glassBackground`
   (class `DLCAFilter`, 77 inputs) plus `CASDFLayer` / `CASDFElementLayer` shape layers, a `CAChameleonLayer` and
   a vibrant colour-matrix portal for the content. AppKit's `NSGlassEffectView`, UIKit's `UIGlassEffect`,
   `UISplitViewController` sidebar columns, `UISearchBar`, `NSPopover` frames are all this filter with different
   parameter sets (§4). Not a recipe file: the parameters are set in code (AppKit "FlexiGlass", UIKit
   `_UIMaterialDefinitionView`); they were read from the live layer trees.

### Maps controls → material (evidence)

| Maps control | implementation (from the Maps binary / MapsUI) | material on macOS 26 | recipe |
|---|---|---|---|
| sidebar | `UISplitViewController` (class bound by `Maps`; strings `MacSidebarEnabled`, `isHostedInMacSidebar`) | UIKit glass sidebar: `_UISplitViewControllerAdaptiveColumnView` → `UIKit._GlassGroupView` → `_UIMaterialDefinitionView` → `CABackdropLayer` + `glassBackground` | §4 "sidebar" |
| Map Modes popover | UIKit / SwiftUI popover; on Catalyst the popover view is hosted by AppKit (`UIPopoverPresentationController`, view has no `UIWindow`) → `NSPopover` | `NSPopoverFrame` = `NSGlassEffectView` | §4 "NSPopover" |
| right-column glass buttons | `-[MUBlurView initGlassBlurWithTintColor:glassStyle:]`, `_maps_applyGlassBackgroundForButton:buttonBackgroundType:…` → `UIGlassEffect` (`glassStyle` 0 regular / 1 clear); some are SwiftUI `.glassEffect` (`SwiftUI.GlassEffectContainer` bound) | UIKit glass (identical filter values to `NSGlassEffectView`) | §4 baseline (regular) / "clear" |
| search field | `UISearchBar` / `UISearchController` (class bound by `Maps`) | `UISearchBarTextField` background = glass with the search-field parameter set | §4 "searchBar" |
| place card / sheets | `UISheetPresentationController` (bound), `MUBlurView initWithBlurEffectStyle:` fed by a Maps theme object (`type` 2 = material, `blurStyle` = `UIBlurEffectStyle`, `groupName`, `additionalColor`) | on the Mac every `UIBlurEffectStyle` becomes an AppKit `NSVisualEffectMaterial` (§3) | §3 |
| status-bar background | `StatusBarBackgroundViewStyle` → `MUBlurView initWithBlurEffectStyle:` (the one `UIBlurEffect` class reference in `Maps`) | §3 | §3 |

The exact `blurStyle` constants of the Maps theme objects are built in Swift code (`initWithBlurStyle:groupName:
defaultColorProvider:disableBlur:` is only reached from Swift, no ObjC call site with an immediate); which of the
§3 rows a given card uses is therefore not pinned down from the binary — the candidates are the five system
styles, and their Mac equivalents are all in §3.

## 2. CoreMaterial recipes (the full table is `materials/corematerial-recipes.tsv`)

Fields: `blurRadius`, `blurAtEnd`, `backdropScale` (capture downsample), `saturation`, `brightness`,
`luminanceAmount` + `luminanceValues[4]` (with `luminanceColorMap.png` 256×1), `colorMatrix` 4×5, `tinting`
(`tintColor`, `tintAlpha`), `zoom`, `blurInputQuality`, `averageColorEnabled`, `curvesValues`; `styles.fill` /
`styles.stroke` point to a visual style set whose `primary…quaternary / highlight / separator` slots are
`vibrantColorMatrix` filters (4×5) with a tint colour.

| recipe | blur | backdropScale | sat | bright | lum amount / values | fill / stroke set |
|---|---|---|---|---|---|---|
| platformContentUltraThinLight | 22.5 | 0.25 | 1.1 | 0.12 | 0.5 / 0.45 0.55 0.65 0.68 | platformFillLight / platformStrokeThinLight |
| platformContentThinLight | 30 | 0.25 | 1.35 | 0.12 | 0.6 / 0.725 0.825 0.76 0.73 | platformFillLight / platformStrokeThinLight |
| platformContentLight | 30 | 0.25 | 1.5 | 0.1 | 0.75 / 0.9 0.83 0.925 0.815 | platformFillLight / platformStrokeLight |
| platformContentThickLight | 45 | 0.25 | 1.5 | 0.045 | 0.88 / 0.99 0.95 0.98 0.905 | platformFillLight / platformStrokeLight |
| platformChromeLight | 22.5 | 0.25 | 1.1 | 0.1 | 0.75 / 0.8 0.9 1.1 0.825 | platformChromeFillLight / platformStrokeLight |
| platformContentUltraThinDark | 22.5 | 0.25 | 1.1 | 0 | 0.5 / 0.24 0.24 0.3 0.39 | platformFillDark / platformStrokeThinDark |
| platformContentThinDark | 30 | 0.25 | 1.35 | 0 | 0.6 / 0.2 0.21 0.1 0.15 | platformFillDark / platformStrokeThinDark |
| platformContentDark | 30 | 0.25 | 1.5 | 0 | 0.75 / 0.16 0.26 0.1 0.1 | platformFillDark / platformStrokeDark |
| platformContentThickDark | 45 | 0.25 | 1.5 | 0 | 0.88 / 0.14 0.16 0.1 0.03 | platformFillDark / platformStrokeDark |
| platformChromeDark | 22.5 | 0.25 | 2.0 | −0.1 | 0.75 / 0.23 0.52 0.27 0.255 | platformChromeFillDark / platformStrokeDark |
| platformContentGlass / Lighter / Darker / UltraDarker, platformSelected / Pinched / Disabled | 45 | — | — | — | — (colour matrix only: diag 0.921/0.735/0.973, off-diag −0.079/−0.265/−0.027, bias 0.235) | — |
| platters / plattersDark | 30 | 0.25 | 2.4 / 1.4 | — / −0.03 | 0.6 / 0.775 0.85 1.05 0.94 ; 0.4 / 0.41 −0.4 0.3 0 | platterFillLight / platterStrokeLight ; Dark |
| toolbarButtonBackground | 15 | 0.25 | 1.1 | — | 0.5 / 0.24 0.24 0.3 0.39 | — |
| dockLight / dockDark | 30 | 0.25 | 1.8 / 1.6 | 0.08 / — | 0.5 / 0.3 0.5 1.0 0.77 ; 0.5 / 0.29 −0.2 0.375 0.65 | — |
| knowledgeBackground(Dark), knowledgePlatters(Sheer)(Dark), modules(Background)(Sheer), carPlayPlatters(Dark), ambientCompact, previewBackground, tintablePlatters, ReduceTransparency variants, ~appletv variants | see tsv | | | | | |

`UIBlurEffectStyle → recipe` (from the switch in `_convertStyleToRecipe`, UIKitCore for Catalyst, `0x1bc9e2ff8`):
styles 6–10 (`systemUltraThin / Thin / Material / Thick / Chrome`, adaptive) pick the Light or Dark recipe by
`userInterfaceStyle == 2`; 11–15 the Light ones; 16–20 the Dark ones; the 1200-series private styles map to
`platters`, `plattersDark`, `modules`, `modulesSheer`, `previewBackground`. (The GOT slots could not be resolved
symbolically in the extracted image; the assignment follows the enum order and the imported symbol set, which
match one-to-one.)

## 3. AppKit `NSVisualEffectMaterial` — what a Catalyst `UIBlurEffect` becomes on the Mac

Read from `materials/appkit-materials.json` (`NSVisualEffectView`, `blendingMode = behindWindow`, `state =
active`). Structure of every blurred material: `CABackdropLayer(scale 0.125)` with filters
`sdrNormalize → gaussianBlur(radius 30) → colorSaturate(amount)`, then a translucent grey fill, then an opaque
grey fill composited with `darkenBlendMode` (light) / `lightenBlendMode` (dark), then a `CAChameleonLayer`
(window-average-colour tint) at 5 %.

| material | light: saturate / fill / blend fill | dark: saturate / fill / blend fill |
|---|---|---|
| sidebar (= toolTip, underWindowBackground) | 2.2 / rgba(246,246,246,0.84) / #e9e9e9 darken / chameleon 5 % | 2.4 / rgba(40,40,40,0.80) / #242424 lighten / 5 % |
| popover | 2.0 / rgba(246,246,246,0.60) / #f1f1f1 darken | 2.0 / rgba(40,40,40,0.60) / #1c1c1c lighten |
| menu | 2.1 / rgba(246,246,246,0.72) / #ededed darken | 2.2 / rgba(40,40,40,0.70) / #202020 lighten |
| hudWindow (= fullScreenUI) | 1.9 / rgba(246,246,246,0.48) / #f5f5f5 darken | 1.6 / rgba(40,40,40,0.40) / #141414 lighten |
| titlebar | blur only / #fdfdfd ×0.8 | blur only / #3c3c3c ×0.8 |
| headerView | blur only | blur / #1e1e1e ×0.8 / chameleon 8 % |
| thin (private 20, = UIKit systemThinMaterial) | 1.8 / rgba(246,246,246,0.36) ×0.5 / #f9f9f9 darken | 1.6 / rgba(40,40,40,0.40) / #141414 lighten |
| ultraThin (private 26, = UIKit systemUltraThinMaterial) | identical to thin in this dump (both appearances) | |
| selection | `vibrantColorMatrixSourceOver` fill, no blur | same |
| windowBackground / contentBackground / underPageBackground / sheet | no backdrop: flat #f6f6f6 (light) / #1e1e1e, #141414 (dark) + chameleon | |

`UIBlurEffectStyle` → `NSVisualEffectMaterial` on the Mac (`materials/catalyst-materials.json`, the effect's
own description): `systemMaterial → 6 popover`, `systemThickMaterial → 5 menu`, `systemChromeMaterial → 3
titlebar`, `systemThinMaterial → 20 (private, "thin")`, `systemUltraThinMaterial → 26 (private, "ultraThin")`;
the legacy `light / extraLight / dark / regular / prominent` are plain fills without blur (`rgba(255,255,255,0.3)`,
`rgba(247,247,247,0.8)`, `rgba(28,28,28,0.73)`), i.e. deprecated styles get no backdrop on the Mac.

**CSS equivalent (exact for this class of material):**

```css
.material-sidebar-light {                 /* NSVisualEffectMaterialSidebar, light */
  backdrop-filter: blur(30px) saturate(2.2);
  background: rgba(246,246,246,.84);
}
.material-sidebar-light::after {          /* the opaque darken-blend fill */
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: #e9e9e9; mix-blend-mode: darken;
}
/* dark: blur(30px) saturate(2.4); rgba(40,40,40,.80); ::after #242424 with mix-blend-mode: lighten */
```
The 5 % chameleon layer (window average colour) has no CSS equivalent and is visually negligible; `sdrNormalize`
only matters for HDR content. CoreAnimation's `gaussianBlur inputRadius` and CSS `blur()` are both the Gaussian
σ in points.

## 4. Liquid Glass recipes (`glassBackground` filter inputs)

All values from the live layer trees. The AppKit `NSGlassEffectView` regular/light values and the UIKit
`UIGlassEffect(.regular)` values on Catalyst are identical (also tinted and interactive variants: the tint is
applied by a separate layer, not by the filter), so one baseline serves both. Units: points for heights/radii,
radians for angles.

**Baseline — regular glass, light appearance** (`NSGlassEffectView` style 0 = `UIGlassEffect` regular):

| group | parameters |
|---|---|
| blur | BlurRadius 5, BlurOpacity0/1 0.8, BlurOpacity2/3 1, BlurDistance0–3 0, BlurFillBlurRadius 8, BlurFillNormalOpacity 0.5, BlurFillLightenOpacity 0.9, BlurFillDarkenOpacity 0 |
| face (the tint over the blurred backdrop) | FaceOpacity 1, FaceColorMatrixWhite 0.96, FaceColorMatrixBlack 0.4, FaceColorMatrixSaturation 1.2, FaceColorMatrixFillColor rgba(255,255,255,0.2), FaceColorMatrixMaxLuma 1, FaceColorMatrixMaxLumaSDR 0.94 |
| bleed (backdrop colour pulled in from around the edge) | BleedAmount 70, BleedHeight 70, BleedBlurRadius 0, BleedOpacity 0, BleedDistance0/1 1/0, BleedColorMatrixWhite 1, Black 0.9, Saturation 1.2, BleedDarkenBlend true |
| refraction (lens edge) | InnerRefractionAmount −60, InnerRefractionHeight 20, OuterRefractionAmount/Height 0, RefractionDistance0/1 −1/0, RefractionOpacity 0 |
| key highlight (specular rim) | KeyFillHighlightAmount 0.5, Angle π/2, Spread 2π/3 (SDR same), Height 0.5, EffectOffset −0.5, ColorBias −0.1875 |
| ring shadow | RingShadowOpacity 0 (BlurRadius 5, Offset 8, StrokeWidth 4, Mask 1) |
| shadow | ShadowOpacity 0, ShadowAmount 0, ShadowOffset (0,0,0,2.5), ShadowColorMatrixFillColor rgba(0,0,0,0.3) |
| misc | Clamp 1, ClampPreserveHue false, MaxHeadroom 9999, SDRGradientDistance0/1 1/1, SDRHoldingTone off, SourceSublayerName "@0" |

Variants (only the parameters that differ from the baseline):

| variant | deltas |
|---|---|
| **regular, dark** (AppKit + UIKit) | Clamp 1.308; Face: White 1.125, Black 0.08, Saturation 1.3, FillColor rgba(0,0,0,0), MaxLuma 0.35, MaxLumaSDR 0.35; Bleed: White 0.5, Black 0.125, Saturation 1, DarkenBlend false; BlurFillDarkenOpacity 0.9, BlurFillLightenOpacity 0 |
| **clear, light** (`NSGlassEffectView` style 1 = `UIGlassEffect` clear) | BlurRadius 10, BlurOpacity0/1 1, BlurFill*Opacity 0, BlurFillBlurRadius 0; Face: White 0.95, Black 0.2, Saturation 1, FillColor rgba(255,255,255,0.1), MaxLumaSDR 1; Bleed: Amount 0, Height 0, Black 0.75; KeyFillHighlight: Amount 0.4, Spread 1.309 (75°), ColorBias −0.25; ring shadow all 0; ShadowAmount 75, ShadowHeight 80, ShadowColorMatrixFillColor rgba(0,0,0,0.1), ShadowColorMatrixSaturation 1.2 |
| **clear, dark** | as clear/light but Face White 0.8, Black 0.05, FillColor rgba(255,255,255,0.05) |
| **sidebar** (UIKit `UISplitViewController` primary column, light) | BlurRadius 10, BlurOpacity0/1 1; Clamp 1.07; Face: White 1.03, MaxLuma 0.85, MaxLumaSDR 0.85; Bleed: Amount 0, Height 0, White 0.9, Black 0.75, Saturation 1.5; KeyFillHighlightHeight 0; ShadowOffset (0,1.875,0,0) |
| **sidebar, dark** | BlurRadius 10, BlurOpacity0/1 1; Face: White 0.5, Black 0.1, Saturation 0.6, FillColor rgba(0,0,0,0), MaxLumaSDR 1; Bleed: Amount 0, Height 0, White 0.5, Black 0.1, Saturation 1.5, DarkenBlend false; BlurFillDarkenOpacity 0.9, LightenOpacity 0; KeyFillHighlightHeight 0; ShadowOffset (0,1.875,0,0) |
| **NSPopover frame** (light) | BlurRadius 10, BlurOpacity0/1 1; Face: White 0.95, Black 0.2, Saturation 1, FillColor rgba(255,255,255,0.1), MaxLumaSDR 1; Bleed Amount/Height 0; InnerRefractionHeight 5, RefractionOpacity 0.6, RingShadowOpacity 0.06 — plus a `ColorShapeLayer` with `vibrantColorMatrix` (diag 0.3125, bias −0.25) under the content |
| **NSPopover frame, dark** | as above with the dark face/bleed set (White 0.8, Black 0.05, FillColor rgba(255,255,255,0.05); Bleed White 0.5, Black 0.125, Sat 1, DarkenBlend false; BlurFillDarkenOpacity 0.9) |
| **search field** (`UISearchBar` text field, light) | BleedAmount 12.6, BleedHeight 12.6, BlurOpacity0/1 0.4, InnerRefractionAmount −18, InnerRefractionHeight 9 (backdrop scale 0.5) |
| **search field, dark** | as regular/dark plus the four search deltas; FaceColorMatrixMaxLuma/SDR 0.6 |

Around the filter, every glass element also has: a `CASDFElementLayer` (the rounded-rect signed-distance shape
that drives refraction and highlight), a `CAChameleonLayer` at 5 % with `colorBlendMode`, and a hidden
`CASDFLayer` carrying the content vibrancy matrix `vibrantColorMatrix` — regular: rows
`[1.1202 −0.1894 −0.019 0 0.1471]`, `[−0.0563 0.9871 −0.0191 0 0.1471]`, `[−0.0563 −0.1893 1.1574 0 0.1471]`;
clear: `[1.3192 −0.0478 −0.0047 0 0.2]` …. Glass buttons (`UIButtonConfiguration.glass`) on Catalyst are hosted
AppKit buttons (`UIButtonMacVisualElement → _UINSView → CALayerHost`); their bezel is AppKit's regular glass.

QuartzCore's stand-alone SDF effects (`CASDFGlassHighlightEffect`: amount 0.5, angle π/2, spread π, height 20,
curvature 1, white; `CASDFGlassDisplacementEffect`: height 20, curvature 1, angle 0) are the same building blocks
with their class defaults — the `glassBackground` values above are what the views actually set.

### What of the glass can be written in CSS

| part of the recipe | CSS | fidelity |
|---|---|---|
| BlurRadius 5 (regular) / 10 (clear, sidebar, popover) | `backdrop-filter: blur(5px)` / `blur(10px)` | exact (σ) |
| Face colour matrix: out = Black + (White − Black)·in, then Saturation (CSS: `contrast(c) brightness(b)` with c = ½·slope / (½·slope + Black), b = slope / c) | regular light (0.4 + 0.56·in): `contrast(0.41) brightness(1.36) saturate(1.2)`; regular dark (0.08 + 1.045·in): `contrast(0.87) brightness(1.20) saturate(1.3)`; clear / popover light (0.2 + 0.75·in): `contrast(0.65) brightness(1.15)`; clear dark (0.05 + 0.75·in): `contrast(0.88) brightness(0.85)`; sidebar light (0.4 + 0.63·in): `contrast(0.44) brightness(1.43) saturate(1.2)`; sidebar dark (0.1 + 0.4·in): `contrast(0.67) brightness(0.60) saturate(0.6)` | good; the MaxLuma clamp (dark 0.35, sidebar light 0.85, search dark 0.6) is not expressible — approximate with a translucent black overlay |
| FaceColorMatrixFillColor rgba(255,255,255,0.2) (regular) / 0.1 (clear) / 0 (dark) | `background: rgba(255,255,255,.2)` | exact |
| BlurFill layers (a second blur of radius 8 lightened at 0.9 over the face, normal at 0.5) | second element `backdrop-filter: blur(8px)` with `mix-blend-mode: lighten; opacity: .9` | approximate (CA composites them inside one filter) |
| KeyFillHighlight (rim light from the top, 120° spread, amount 0.5) | `box-shadow: inset 0 1px 0 rgba(255,255,255,.5)` plus an inset gradient border `linear-gradient(180deg, rgba(255,255,255,.5), transparent 40%)` masked to a 1 px ring | approximate — the real one follows the SDF of the shape (curvature 1, height 0.5 pt) |
| Bleed (70 pt of backdrop colour pulled into the edge, darken-blended, sat 1.2) | none; nearest is an extra `backdrop-filter: blur(35px)` element clipped to a 70 px inner margin with `mix-blend-mode: darken` | rough |
| InnerRefraction −60 / height 20 (edge lens) | SVG filter `feDisplacementMap` driven by a radial gradient map, or omit | rough / omit |
| Chameleon 5 % | omit | negligible |
| clear style shadow (amount 75, height 80, rgba(0,0,0,.1)) | `box-shadow: 0 8px 24px rgba(0,0,0,.1)` (soft, wide) | approximate |
| popover ring shadow 0.06, refraction opacity 0.6 | `box-shadow: 0 0 0 1px rgba(0,0,0,.06)` | approximate |
| content vibrancy matrix (1.12/0.987/1.157 diag, 0.147 bias) | `filter: contrast(1.1) brightness(1.15)` on the label layer, or plain `color` picked from the matrix applied to the text colour | approximate |

Recommended order for the UI page: (1) blur radius, (2) face levels + saturation + white fill, (3) rim highlight
+ shadow per style, (4) skip bleed / refraction / chameleon. Verify by sampling only after that is built.

## 5. Sources

- Recipes: `/System/Library/PrivateFrameworks/CoreMaterial.framework/Versions/A/Resources/*.materialrecipe`,
  `*.descendantrecipe`, `*.visualstyleset`, `*.descendantstyleset`, `luminanceColorMap.png` (256×1).
- Style→recipe switch: `UIKitCore` (Catalyst copy from the dyld shared cache `dyld_shared_cache_arm64e`,
  `/System/iOSSupport/System/Library/PrivateFrameworks/UIKitCore.framework`), `__convertStyleToRecipe`.
- Which frameworks Maps links: `otool -L /System/Applications/Maps.app/Contents/MacOS/Maps`; class bindings:
  `dyld_info -fixups` (`UISplitViewController`, `UISearchBar`, `UISearchController`, `UISheetPresentationController`,
  `UINavigationBar`, `UIToolbar`, `UIVisualEffectView`, `UIBlurEffect`, SwiftUI `GlassEffectContainer` /
  `glassEffect(_:in:)`); MapsUI `MUBlurView` selectors (`initWithBlurEffectStyle:`, `initGlassBlurWithTintColor:
  glassStyle:`, `initWithGaussianBlurWithRadius:`, `initWithVariableBlurWithRadius:maskImage:`); Maps
  `StatusBarBackgroundViewStyle` (`type`, `blurStyle`, `groupName`, `additionalColor`).
- Layer trees: `pipeline/materials/dump_appkit_materials.m` (AppKit) and `pipeline/materials/catalyst_probe`
  (UIKit on Mac), run on this machine (macOS 27 / build of 2026-09).
- Glass filter input names: enumerated from the `DLCAFilter` instance AppKit attaches (`inputKeysForFilterType:`).

## 6. Not resolved

- The `blurStyle` constants inside the Maps theme objects (Swift code; no ObjC call site with an immediate) —
  which §3 row each card / sheet uses. Partial answer from MapsUI itself (cache-optimised `objc_msgSend$` stubs
  resolved through the dyld cache, `pipeline/materials/catalyst_probe/selofs.m` + scratch `cachecalls.py`): the
  effects MapsUI builds directly are `UIBlurEffectStyle` 10 systemChromeMaterial (`MUPlacePhotoGalleryAttributionView`),
  9 systemThickMaterial (`MUScrollableSegmentedPickerContentView`), 16 systemUltraThinMaterialDark
  (`MUCardButton _updateButtonAppearance`), 7 systemThinMaterial (a Swift view) and the private 1100
  (`+[UIButtonConfiguration(MUPlaceHeaderButtonExtras) _setupDirectionsButtonConfiguration:]`, → the Chrome recipe
  pair in `_convertStyleToRecipe`); `-[MUBlurView initWithBlurEffectStyle:]` has no caller inside MapsUI — the
  card/sheet containers get their style from the Maps app's Swift theme, which also carries the feature flag
  `EnableThickCardMaterial` ("Enable Thick Card Material") — i.e. the place card is systemMaterial (8) by default
  and systemThickMaterial (9) with the flag, which on the Mac are `NSVisualEffectMaterial` popover (6) / menu (5)
  (§3). The remaining unknown is the default-off/on state of that flag on this build.
- The CoreMaterial luminance remap algorithm (`luminanceAmount` × LUT) is not needed on the Mac (recipes unused
  there) and was not reverse-engineered.
- `glassBackground` inputs that stayed at 0 in every variant (Aberration*, OuterRefraction*, SDRShadow*) are
  listed but their behaviour is unknown.
- The vibrancy applied to *text* inside glass (`_UIMaterialDefinitionView` portal + `vibrantColorMatrix`) is
  captured as a matrix; the resulting text colours were not computed.
