#!/usr/bin/env python3
"""Build the data files for map/ (the globe-only page) from public-domain sources.

    python3 pipeline/basemap/globe-data.py        # run from the repo root

Inputs (pipeline/basemap/raw/, gitignored; downloaded by palette.py / by hand):
    ne_bathy/                Natural Earth 10m bathymetry, 12 depth levels
    ne_land/                 Natural Earth 10m land
    ne_countries/            Natural Earth 10m admin_0 countries (LABEL_X/Y, LABELRANK, MIN/MAX_LABEL)
    ne_marine/               Natural Earth 10m marine polys (oceans, seas, bays, gulfs)
    ne_regions_polys/        Natural Earth 10m geography regions polys (continents)
    koppen/1991_2020/        Beck et al. 2023 Koppen-Geiger 0.1 deg raster + legend.txt
Outputs (map/data/, committed — all sources are public domain / CC-BY):
    bathy-<depth>.geojson    one MultiPolygon per depth level (parallel load), DP 0.02/0.04 deg, 3/2 decimals
    land.geojson             land MultiPolygon, same simplification
    climate-light.png, climate-dark.png   Web-Mercator raster of land tint (palette-land.json),
                             Koppen class -> tint by the majority mapping fitted on palette.py's samples,
                             masked to Natural Earth land, ocean transparent
    labels.geojson           points: continents, countries, oceans/seas with NE zoom ranges
    meta.json                colours + sources + numbers used by map/globe.js
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "pipeline", "basemap", "raw")
OUT = os.path.join(ROOT, "map", "data")
os.makedirs(OUT, exist_ok=True)

TOL = 0.01          # deg, Douglas-Peucker tolerance (~1 km; a z5 pixel is ~5 km)
MIN_AREA = 0.0005   # deg^2, drop rings smaller than this after simplification (~2x2 km)
DECIMALS = 3

NE_LEVELS = [("L", 0), ("K", 200), ("J", 1000), ("I", 2000), ("H", 3000), ("G", 4000),
             ("F", 5000), ("E", 6000), ("D", 7000), ("C", 8000), ("B", 9000), ("A", 10000)]

# Koppen class -> tint, majority vote of the 705 palette.py land samples cross-tabulated with the
# 0.1 deg raster (2026-09-16): BWk 105/147 very_dry, BSk 73/111 semi_humid, Dwc 31/57 semi_humid,
# ET 30/51 high_grey, Cwb 5/6 semi_humid, BSh 18/18 humid, everything else humid. EF (no samples)
# is grouped with ET; BWh (1 sample) with BWk.
KOPPEN_TINT = {4: "very_dry", 5: "very_dry", 7: "semi_humid", 23: "semi_humid", 12: "semi_humid",
               29: "high_grey", 30: "high_grey"}
DEFAULT_TINT = "humid"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def version(base):
    return open(base + ".VERSION.txt").read().strip()


def polygons_geojson(base, props_fn=None, tol=TOL, min_area=MIN_AREA, decimals=DECIMALS):
    feats = []
    for kind, rings, rec in nelib.read_layer(base):
        if kind != "polygon":
            continue
        s = nelib.simplify_polygon(rings, tol, min_area)
        if not s:
            continue
        coords = nelib.rings_to_geojson_polygons(s, decimals)
        feats.append({"type": "Feature", "properties": props_fn(rec) if props_fn else {},
                      "geometry": {"type": "MultiPolygon", "coordinates": coords}})
    return feats


def build_bathy():
    """One GeoJSON per depth level (bathy-<depth>.geojson) so the 12 sources parse in parallel
    workers and paint progressively (a single 12 MB file took ~8 s before anything showed)."""
    for old in ("bathy.geojson",):
        if os.path.exists(os.path.join(OUT, old)):
            os.remove(os.path.join(OUT, old))
    for letter, depth in NE_LEVELS:
        base = os.path.join(RAW, "ne_bathy", f"ne_10m_bathymetry_{letter}_{depth}")
        # level 0 is the coastline (keep 3 decimals, 0.02 deg); deeper contours are smooth GEBCO
        # isobaths: 2 decimals (~1 km) and drop speckle rings < 0.01 deg^2 (~10x10 km) from 4000 m down
        dec = 3 if depth == 0 else 2
        min_area = 4 * MIN_AREA if depth < 4000 else 0.01
        tol = 2 * TOL if depth < 3000 else 4 * TOL      # 0.02 deg near the coast, 0.04 deg (~4 km) for abyssal contours
        f = polygons_geojson(base, lambda r, d=depth: {"depth": d}, tol=tol, min_area=min_area, decimals=dec)
        coords = [c for ft in f for c in ft["geometry"]["coordinates"]]
        fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"depth": depth},
                                                          "geometry": {"type": "MultiPolygon", "coordinates": coords}}]}
        p = os.path.join(OUT, f"bathy-{depth}.geojson")
        json.dump(fc, open(p, "w"), separators=(",", ":"))
        log(f"bathy {depth}: {sum(len(pp[0]) for pp in coords)} outer vertices, {len(coords)} polygons, {os.path.getsize(p) / 1e6:.2f} MB")
    return version(os.path.join(RAW, "ne_bathy", "ne_10m_bathymetry_L_0"))


def build_land():
    base = os.path.join(RAW, "ne_land", "ne_10m_land")
    f = polygons_geojson(base)
    coords = [c for ft in f for c in ft["geometry"]["coordinates"]]
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                                                      "geometry": {"type": "MultiPolygon", "coordinates": coords}}]}
    json.dump(fc, open(os.path.join(OUT, "land.geojson"), "w"), separators=(",", ":"))
    log(f"land: {len(coords)} polygons, {sum(len(p[0]) for p in coords)} outer vertices")
    return version(base)


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def build_climate(tints):
    """Web-Mercator PNG (N x N) of land tint from the 0.1 deg Koppen raster, masked to NE land."""
    kg = np.asarray(Image.open(os.path.join(RAW, "koppen", "1991_2020", "koppen_geiger_0p1.tif")))
    H0, W0 = kg.shape  # 1800 x 3600, 0.1 deg, lat 90..-90, lng -180..180
    N = 4096
    # Mercator rows -> latitude
    ys = (0.5 - (np.arange(N) + 0.5) / N) * 2 * math.pi  # +pi .. -pi
    lats = np.degrees(2 * np.arctan(np.exp(ys)) - math.pi / 2)
    rows = np.clip(((90 - lats) / 180 * H0).astype(int), 0, H0 - 1)
    cols = np.clip((np.arange(N) / N * W0).astype(int), 0, W0 - 1)
    cls = kg[rows][:, cols]
    # NE land mask rasterised on the same Mercator grid (even-odd, so lakes stay out)
    land = np.zeros((N, N), dtype=np.uint8)
    for kind, rings, _ in nelib.read_layer(os.path.join(RAW, "ne_land", "ne_10m_land")):
        if kind != "polygon":
            continue
        for r in rings:
            x = (r[:, 0] + 180) / 360 * N
            lat = np.clip(r[:, 1], -85.05, 85.05)
            y = (0.5 - np.array([merc_y(v) for v in lat]) / (2 * math.pi)) * N
            x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 2, N)
            y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 2, N)
            if x1 <= x0 or y1 <= y0:
                continue
            im = Image.new("1", (x1 - x0, y1 - y0), 0)
            ImageDraw.Draw(im).polygon(list(zip((x - x0).tolist(), (y - y0).tolist())), fill=1)
            land[y0:y1, x0:x1] ^= np.asarray(im, dtype=np.uint8)
    gp = globe_palette()
    modes = {"light": {t: v["light"] for t, v in tints.items()}, "dark": {t: v["dark"] for t, v in tints.items()}}
    if gp:
        # the App's globe land tints (light only); tints the screenshot did not contain fall back to the flat palette
        modes["globe"] = {t: [int(gp["land_tints"].get(t, tints[t]["light_hex"])[i:i + 2], 16) for i in (1, 3, 5)] for t in tints}
    for mode, tint_rgb in modes.items():
        rgba = np.zeros((N, N, 4), dtype=np.uint8)
        for k in range(1, 31):
            tint = KOPPEN_TINT.get(k, DEFAULT_TINT)
            rgb = tint_rgb[tint]
            m = cls == k
            rgba[m, 0], rgba[m, 1], rgba[m, 2] = rgb
            rgba[m, 3] = 255
        # Koppen has no class where the raster says ocean but NE says land (coasts): leave the NE
        # land fill (humid) showing through; where Koppen says land but NE says sea, hide it
        rgba[land == 0, 3] = 0
        Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, f"climate-{mode}.png"), optimize=True)
        log(f"climate-{mode}.png written, {int((rgba[:, :, 3] > 0).sum())} land px")
    return {"size_px": N, "bounds": [[-180, 85.0511], [180, 85.0511], [180, -85.0511], [-180, -85.0511]]}


def label_point(rings):
    """Interior label point on the sphere: sample each outer ring's interior on a lat/lng grid,
    average the unit vectors weighted by cos(lat) (= spherical area), and if the mean falls
    outside the polygon (crescent seas) snap to the nearest sampled interior point. Works for
    polar polygons (Arctic Ocean) and antimeridian splits (Pacific), where a planar lng/lat
    centroid lands thousands of km off (2026-09-16: 'Arctic Ocean' drawn in the Yellow Sea)."""
    outers = [r for r in rings if nelib.ring_area(r) < 0] or rings   # shapefile outer = clockwise
    vecs, pts = [], []
    for r in outers:
        x0, x1, y0, y1 = r[:, 0].min(), r[:, 0].max(), r[:, 1].min(), r[:, 1].max()
        step = max(0.1, max(x1 - x0, y1 - y0) / 120)
        xs = np.arange(x0 + step / 2, x1, step); ys = np.arange(y0 + step / 2, y1, step)
        for lat in ys:
            for lng in xs:
                if nelib.point_in_ring((lng, lat), r):
                    la, lo = math.radians(lat), math.radians(lng)
                    v = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
                    vecs.append(v * math.cos(la)); pts.append((v, lng, lat))
    if not pts:
        r = max(rings, key=len); return float(r[:, 0].mean()), float(r[:, 1].mean())
    m = np.sum(vecs, axis=0); m /= np.linalg.norm(m) + 1e-12
    lat = math.degrees(math.asin(max(-1, min(1, m[2])))); lng = math.degrees(math.atan2(m[1], m[0]))
    if any(nelib.point_in_ring((lng, lat), r) for r in outers):
        return lng, lat
    v, lng, lat = max(pts, key=lambda p: float(p[0] @ m))
    return lng, lat


def build_labels():
    feats = []
    # continents
    base = os.path.join(RAW, "ne_regions_polys", "ne_10m_geography_regions_polys")
    for kind, rings, rec in nelib.read_layer(base):
        if kind != "polygon" or rec["FEATURECLA"] != "Continent":
            continue
        cx, cy = label_point(rings)
        feats.append({"type": "Feature", "properties": {"kind": "continent", "name": rec["NAME"],
                                                        "min_label": rec["MIN_LABEL"], "max_label": rec["MAX_LABEL"], "rank": rec["SCALERANK"]},
                      "geometry": {"type": "Point", "coordinates": [round(cx, 3), round(cy, 3)]}})
    v_regions = version(base)
    # countries: NE's own label points and zoom ranges
    base = os.path.join(RAW, "ne_countries", "ne_10m_admin_0_countries")
    for kind, rings, rec in nelib.read_layer(base):
        if rec is None or rec.get("LABEL_X") is None:
            continue
        feats.append({"type": "Feature", "properties": {"kind": "country", "name": rec["NAME"],
                                                        "min_label": rec["MIN_LABEL"], "max_label": rec["MAX_LABEL"], "rank": rec["LABELRANK"]},
                      "geometry": {"type": "Point", "coordinates": [round(rec["LABEL_X"], 3), round(rec["LABEL_Y"], 3)]}})
    v_countries = version(base)
    # oceans and seas: centroid of the largest polygon ring (NE marine polys have no label point)
    base = os.path.join(RAW, "ne_marine", "ne_10m_geography_marine_polys")
    for kind, rings, rec in nelib.read_layer(base):
        if kind != "polygon" or not rec.get("name") or rec["featurecla"] not in ("ocean", "sea", "bay", "gulf"):
            continue
        cx, cy = label_point(rings)
        feats.append({"type": "Feature", "properties": {"kind": "ocean" if rec["featurecla"] == "ocean" else "sea",
                                                        "name": rec["name"], "min_label": rec["min_label"], "max_label": rec["max_label"],
                                                        "rank": rec["scalerank"]},
                      "geometry": {"type": "Point", "coordinates": [round(cx, 3), round(cy, 3)]}})
    v_marine = version(base)
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(OUT, "labels.geojson"), "w"),
              separators=(",", ":"), ensure_ascii=False)
    log(f"labels: {len(feats)}")
    return {"regions": v_regions, "countries": v_countries, "marine": v_marine}


def globe_palette():
    p = os.path.join(ROOT, "ui", "basemap", "palette-globe.json")
    if not os.path.exists(p):
        return None
    g = json.load(open(p))
    pick = lambda s: (s.get("centre") or s)["hex"]   # noqa: E731
    return {
        "source": "ui/basemap/palette-globe.json (pipeline/basemap/globefit.py on the Maps App globe screenshot)",
        "camera": {k: g["camera"][k] for k in ("lat0", "lng0", "D_earth_radii", "limb_radius_px", "rms_px", "camera_altitude_km")},
        "ocean_bands": [{"depth_min_m": b["depth_min_m"], "light": pick(b), "n": (b.get("centre") or b)["n"]} for b in g["ocean_bands"]],
        "land_tints": {t: pick(v) for t, v in g["land_tints"].items()},
        "haze_by_r_over_limb_deep_ocean": g["haze_by_r_over_limb_deep_ocean"],
    }


def shelf_meta():
    p = os.path.join(ROOT, "ui", "basemap", "palette-shelf.json")
    if not os.path.exists(p):
        return None
    s = json.load(open(p))
    return {"source": "ui/basemap/palette-shelf.json (pipeline/basemap/shelf.py)", "bounds": s["raster"]["bounds"],
            "ramp_depth_m": s["raster"]["ramp_depth_m"], "ramp_rgb": s["raster"]["ramp_rgb"],
            "bins": [{"depth_min_m": b["depth_min_m"], "depth_max_m": b["depth_max_m"], "hex": (b.get("centre") or b)["hex"], "n": b["n"]} for b in s["bins"]]}


def main():
    ocean = json.load(open(os.path.join(ROOT, "ui", "basemap", "palette-ocean.json")))
    land = json.load(open(os.path.join(ROOT, "ui", "basemap", "palette-land.json")))
    labels = json.load(open(os.path.join(ROOT, "ui", "basemap", "labels-globe.json")))
    tints = {}
    for t in land["tints"]:
        base = t["by_shading"].get("flat") or t["by_shading"].get("lit")
        tints[t["tint"]] = {"light": base["light"]["rgb"], "dark": base["dark"]["rgb"],
                            "light_hex": base["light"]["hex"], "dark_hex": base["dark"]["hex"], "n": base["light"]["n"]}
    v_bathy = build_bathy()
    v_land = build_land()
    climate = build_climate(tints)
    v_labels = build_labels()
    meta = {
        "generated_by": "pipeline/basemap/globe-data.py",
        "sources": {
            "bathymetry": {"name": f"Natural Earth 10m Bathymetry v{v_bathy}", "url": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip", "license": "public domain"},
            "land": {"name": f"Natural Earth 10m Land v{v_land}", "url": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip", "license": "public domain"},
            "labels": {"name": f"Natural Earth 10m admin_0_countries v{v_labels['countries']} (LABEL_X/Y, LABELRANK, MIN/MAX_LABEL), "
                               f"geography_marine_polys v{v_labels['marine']}, geography_regions_polys v{v_labels['regions']}",
                       "urls": ["https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
                                "https://naciscdn.org/naturalearth/10m/physical/ne_10m_geography_marine_polys.zip",
                                "https://naciscdn.org/naturalearth/10m/physical/ne_10m_geography_regions_polys.zip"],
                       "license": "public domain",
                       "note": "marine and continent label points are the area centroid of the largest polygon ring; NE has no deep/trench points, so deep names are not drawn"},
            "climate": {"name": "Beck et al. 2023, High-resolution (1 km) Koppen-Geiger maps for 1901-2099, 1991-2020 present-day map, 0.1 deg",
                        "url": "https://figshare.com/articles/dataset/21789074 (koppen_geiger_tif.zip, 1991_2020/koppen_geiger_0p1.tif)",
                        "license": "CC BY 4.0", "koppen_to_tint": {str(k): v for k, v in KOPPEN_TINT.items()}, "default_tint": DEFAULT_TINT,
                        "mapping_basis": "majority vote of palette.py's 705 land samples per Koppen class (see globe-data.py header)"},
            "hillshade": {"name": "AWS Terrain Tiles, terrarium encoding", "url": "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"},
            "colours": "ui/basemap/palette-ocean.json, palette-land.json, labels-globe.json (Apple renderer sampled 2026-09-16)",
        },
        "simplification": {"douglas_peucker_deg": TOL, "min_ring_area_deg2": MIN_AREA, "decimals": DECIMALS},
        "ocean_bands": [{"depth_min_m": b["depth_min_m"], "light": b["light"]["hex"], "dark": b["dark"]["hex"], "n": b["light"]["n"]} for b in ocean["bands"]],
        "land_tints": tints,
        # the App's GLOBE style, sampled from its screenshot through the fitted camera (palette-globe.json);
        # light only (the screenshot is light); 'centre' = r/limb <= 0.5, least hazed
        "globe_palette": globe_palette(),
        "shelf": shelf_meta(),
        "climate_image": climate,
        "hillshade": {
            "illumination_direction_deg": land["hillshade"]["probe_japan_alps"]["fit"]["azimuth_deg"],
            "fit_r": land["hillshade"]["probe_japan_alps"]["fit"]["pearson_r"],
            "ground_elevation_scale_by_zoom": land["ground_settings"]["day"]["groundElevationScale_by_zoom"],
            "alps_probe_luma_amplitude": 14.3,
            "note": "amplitude = luminance change over the 5-95% hill-shade range in the z~9 Alps render (regression slope 24.2 per unit hill-shade)",
        },
        "labels": {k: {"weight": v["weight_consensus"], "size_pt": v["size_pt_median"], "tracking_pt": v["tracking_pt_median"],
                       "italic": v["italic"], "case": v["case"], "light": v["glyph_hex_median"],
                       "dark": "#%02x%02x%02x" % tuple(v["dark_glyph_rgb_median"]) if v["dark_glyph_rgb_median"] else None,
                       "halo": ("#%02x%02x%02x" % tuple(v["halo_rgb_median"])) if v["halo_rgb_median"] else None,
                       "halo_width_px_2x": v["halo_width_px_median"]}
                   for k, v in labels["summary_by_kind"].items()},
        "ocean_sizes_pt": {"ocean": [e["fit"]["size_pt"] for e in labels["labels"] if e.get("id", "").startswith("ocean-")],
                           "sea": [e["fit"]["size_pt"] for e in labels["labels"] if e.get("id", "").startswith("sea-")]},
        "background": {"space": labels["background"]["space_hex"],
                       "stars_per_100x100_pt": labels["background"]["stars"]["per_100x100_pt"],
                       "star_size_pt": labels["background"]["stars"]["size_px_2x_median"] and round(math.sqrt(labels["background"]["stars"]["size_px_2x_median"]) / 2, 2),
                       "star_gray_p10_p50_p90": labels["background"]["stars"]["peak_gray_p10_p50_p90"],
                       "limb_profile_2x": labels["background"]["limb_glow"]["profiles"][1]["rgb_inward_to_outward"],
                       "limb_inner_haze_every_2px_2x": labels["background"]["limb_glow"]["profiles"][1]["inner_haze_rgb_every_2px_2x"],
                       "limb_source": "native.png row 800 (2x), Maps App globe screenshot"},
    }
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1, ensure_ascii=False)
    for f in sorted(os.listdir(OUT)):
        log(f"{f:20s} {os.path.getsize(os.path.join(OUT, f)) / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
