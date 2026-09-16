# stars.bin — the star catalogue of the Apple Maps globe

Source: the zip embedded in `/System/Library/PrivateFrameworks/VectorKit.framework/Versions/A/VectorKit` (macOS 27,
extracted from the dyld shared cache; entry `sky/stars.bin`, 120 000 bytes, dated 2025-08-08 in the zip), loaded by
`md::GlobeSkyRenderResources::loadStarsModel` → `karo::media::SkyLoader::loadFromChunk` and drawn by
`GlobeStars::stars_vertex/fragment` (white points, alpha from the vertex).

Layout: 10 000 records × 12 bytes, little-endian `float32 × 3`:

| field | range | meaning (from the values; names not in the binary) |
|---|---|---|
| 0 | 0.0003 … 6.2824 | angle in radians, full circle (right ascension or longitude) |
| 1 | −1.519 … 1.538 | angle in radians, ±87° (declination or latitude) |
| 2 | 14.08 → 10.02, sorted descending | brightness score (first record 14.08, last 10.02) — mapped to point alpha/size in the vertex shader |

The frame of the two angles (equatorial vs galactic) is not established; brightest entry (3.7545, −0.7772).
