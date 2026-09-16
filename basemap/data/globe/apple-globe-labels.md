# What the App names at globe zoom — read from its own tiles (2026-09-16 night)

`~/Money/styl-work/apple-data/apple-globe-labels.tsv` (kept **outside the repo**: it is Apple label data — names, positions, label paths; the acceptance is asking the user how Apple-derived data files may be kept) lists every label feature in the `VECTOR_SPR_STANDARD` (style 67) tiles of the local geod cache
copy at Apple z2–6, decoded by Apple's decoder (`pipeline/basemap/spr_labels.m`: `GEOVectorTile initWithVMP4:…`,
then the `physicalFeatures` / `pois` arrays) and converted by `pipeline/basemap/apple_labels.py`. Coverage = the tiles
the App had fetched on this Mac: z2 11 tiles (all of the northern hemisphere + Africa/Australia), z3 24 (the eastern
hemisphere and the Americas' Pacific side), z4 22 (East Asia), z5–6 Japan and its seas. 2051 rows; 1384 at z2–4.

## Feature structs (GeoServices `GeoCodecsFeature` header, offsets read off the memory)

`physicalFeatures` (176 B each) and `pois` (224 B each) both start with the feature header: VectorTile* @0, control
block @8, name pointer @0x10 (the native name inside the tile), `shared_ptr<FeatureStyleAttributes>` @0x18 (object:
pairs `(u32 attribute, u32 value)` @0, count u8 @0x21), feature id u64 @0x28, label index u32 @0x38 into the tile's
label table (VectorTile+0x420, 24 B entries), label count u8 @0x49. POIs: position float x @0x58, y (from the tile's
bottom) @0x5c, weight float @0x60. Physical features: range index u32 @0x5c into the `physicalFeaturesVertices` pool
(`{u32, float2* verts @8, u32 nverts @0x10, float* @0x18, {u64 start, u64 count}* @0x20, u32 nranges @0x28}`) — the
label **path** (curved baseline the spread text follows), tile units, y up.

## Attributes (ids from the pairs; the meaning from the values, not from the name table — the string table beyond id 6
is unreliable)

| id | meaning | values seen |
|---|---|---|
| 5 | feature type | 3 point (pois), 21 physical line/area |
| 6 | class | pois: 0 continent, 1 country, 2 state / province (abbreviated names: AB, CA, D.C.), 3 city, 130 capital, 180 island, 5 sea / ocean / bay, 411 (one: Saulaine); physical: 140 desert, 170 region, 221 water body (strait, channel, Southern Ocean), 223 plain, 428 undersea area, 430 mountains, 431 undersea ridge |
| 92 | physical subtype | 1 island group, 6 desert, 8 escarpment, 9 upland, 15 range, 17 plateau, 18 land basin, 31 basin, 32 peninsula, 35 ridge, 36 fan, 37 trench / trough, 39 rise, 41 shelf, 42 seascarp, 48/50 plain, 52 lowland, 56 reef |
| 85 | **min zoom = rank**: the tile zoom at which the feature first appears; the sheet's `PhysicalFeature-Rank-1-2` / `-3-5` / `-6` … classes are this number (z2 tiles only carry 0–2, z3 adds 3, z4 adds 4) | 0–4 at z2–4 |
| 10 | rank of seas and cities (oceans 14, seas 1–2; cities 0–14, capitals mostly 3–5) | 0–14 |
| 4 | country of the point | ISO-like numeric (Japan 10, China 4, US 226, Canada 98, South Africa 62) |
| 155 | order of the physical feature inside its tile | 0–12 |
| 167 / 3 | 1 / 17 on water features | — |

Names are the **native** ones (東京, Камчатка, Qazaq Dalasy); the English the App shows comes from the localisation
data it fetches separately (`initWithVMP4:localizationData:` was given nil). Physical features of English-speaking
regions and undersea features are English in the tile.

## What it means for our globe (Apple z ≤ 4.6)

- At z2 the App carries **24 physical line/area labels** worldwide (Sahara, Gobi Desert, Himalaya, Alps, Andes,
  Rocky Mountains, Appalachian Mountains, Great Plains, Mid-Atlantic / East Pacific / Southwest Indian /
  Atlantic-Indian Ridge, Southern Ocean, Taiwan Strait, Strait of Sicily, Polynesia / Melanesia / Micronesia) + 21 seas
  + 5 continents + 41 cities (rank 85 = 2) + 64 US/Canada state abbreviations; z3 adds 164 physical (74 undersea basins,
  29 ridges, 17 mountain ranges, 20 regions, 18 water bodies …) and 580 points; z4 adds 134 physical (in East Asia).
- **Deeps** (Ramapo Deep, Vityaz Depth) are *not* in these tiles at z2–6 — they come with another tile set (the
  elevation-point class `PhysicalFeature-Undersea-Points-Globe-Base`, blue rgb(29,104,241) semibold width=100 in the
  globe sheet); our `map/data/undersea.geojson` (GEBCO gazetteer, cls 1 Deep) already has them.
- `apple_labels.py` stamps `apple_minzoom` / `apple_type` / `apple_rank` / `apple_name` on the features of
  `map/data/physical.geojson` (41 matched), `undersea.geojson` (38) and `cities.geojson` (191) whose name matches
  (normalised, generic words stripped, position within 25°): the UI can select **exactly Apple's set** by
  `apple_minzoom ≤ zoom`. 58 Apple physical names have no counterpart in our public layers
  (`apple-globe-labels-unmatched.json`: seas that live in the marine layer, native-language names, island groups,
  a few basins / fans / fracture zones) — they can be taken from the tsv, which is Apple's own label data.
- Styles (`globe-label-styles.tsv`, Mac globe sheet resolved, heights in Mac pt = iOS × 1.2987): physical
  `PhysicalFeature-Rank-1-2-Globe` / `-3-5-Globe`: `%$default,bold-G3,width=140`, colour rgb(221,208,188), halo
  rgb(28,38,50) α0.78, height 9.09 (z2–3) → 11.69 (z3–4) → 16.88 (z4–5) → 22.08 (z5–6), textSizeScale 1.2, spread along
  the path (`labelMeshPositioningMode` 2, prop 20 true = the uppercase spread text); undersea points semibold width=100
  rgb(29,104,241); seas `Ocean-Label-Point-*` semibold italic; cities `City-Style-NN` by rank (medium-G1 width=90,
  `SettlementDot-Ring-City` dot).
