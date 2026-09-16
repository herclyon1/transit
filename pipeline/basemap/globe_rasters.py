#!/usr/bin/env python3
"""Globe ground rasters from THIRD-PARTY data only (user's rule 2026-09-17: copy Apple's logic, never its tile content):
the class-index, climate-code and height rasters the UI recolours with the decoded DvMt material tables, in the same
files / formats as before so `map/globe.js` needs no change.

    python3 pipeline/basemap/globe_rasters.py            # from the repo root; downloads are cached in pipeline/basemap/raw/
    python3 pipeline/basemap/globe_rasters.py --calibrate # also print the mapping tables' per-pixel hit rates against the
                                                          # Apple rasters kept OUTSIDE the repo (~/Money/styl-work/apple-data)

Sources (all public, none from Apple's tiles):
  land cover   NASA GIBS WMTS MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual (MCD12 IGBP, 500 m; z4 tiles = the 4096^2
               world canvas, z5 tiles = the 2048^2 East-Asia box) — the IGBP colour legend is GIBS's own colormap
  climate      Beck et al. 2023 Koppen-Geiger 1991-2020, 0.1 deg (figshare 21789074, CC BY 4.0)
  height       AWS terrarium DEM (Mapzen / Tilezen), z3 tiles = 2048^2 world, z4 tiles = 1024^2 East Asia; sea clamped to 0
               (the App's globe mesh carries no bathymetry — RENDER-PIPELINE 2.4b)
Rules (decoded, kept): the Landcover class list and material -> class table (spr-materials.json, from the DvMt /
material palettes), ClimateTemperature 0 Arctic … 6 VeryHot and ClimatePrecipitation 0 VeryWet … 5 VeryDry codes
(VectorKit gss enums, chapter 154), the code -> HSV-cell formula (ground-globe.json "climate"), the DvMt colours.
Mapping tables (this file, IGBP_APPLE and KOPPEN_CODES): IGBP class -> Apple Landcover class and Koppen class ->
(temperature, precipitation) code.  They were CALIBRATED once against Apple's own rasters (majority vote per source
class over every pixel where Apple has a tile; `--calibrate` recomputes the confusion and prints the hit rate; the
numbers are in ui/basemap/ground-globe.json "calibration" and map/README.md).  The Apple rasters themselves stay
outside the repo.
Outputs (map/data/): spr-class-globe.png 4096^2 (index into CLASSES, 255 = no data), climate-temp-globe.png /
climate-arid-globe.png 1024^2, height-globe.png 2048^2 terrarium; the East-Asia set spr-class-globe-ea.png 2048^2,
climate-*-globe-ea.png 256^2, height-globe-ea.png 1024^2; ui/basemap/ground-globe.json (bounds, sources, tables).
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(ROOT, "map", "data")
META = os.path.join(ROOT, "ui", "basemap", "ground-globe.json")
MATERIALS = os.path.join(ROOT, "basemap", "data", "globe", "spr-materials.json")
APPLE = os.path.expanduser("~/Money/styl-work/apple-data/map-data")       # calibration only, never read at build time
UA = "transit-basemap/1.0 (github herclyon; globe class raster)"
GIBS_LAYER = "MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual"
GIBS_TIME = "2024-01-01"
GIBS_URL = f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{GIBS_LAYER}/default/{GIBS_TIME}/GoogleMapsCompatible_Level8/{{z}}/{{y}}/{{x}}.png"
TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
EA = {"x": (6, 8), "y": (2, 4)}          # z3 tiles: lng 90..180, lat 0..66.51326 (tile-aligned, as ground-globe-ea)
N_WORLD, N_EA = 4096, 2048
# GIBS colormap rgb -> IGBP code (GIBS MODIS_IGBP_Land_Cover_Type colormap, 2026-09-16); 0 / 17 share the water colour
IGBP_RGB = {(33, 138, 33): 1, (49, 204, 49): 2, (152, 204, 49): 3, (150, 250, 150): 4, (141, 186, 141): 5,
            (186, 141, 141): 6, (245, 222, 179): 7, (218, 235, 157): 8, (255, 213, 0): 9, (240, 185, 103): 10,
            (71, 131, 181): 11, (250, 239, 115): 12, (255, 0, 0): 13, (153, 147, 86): 14, (255, 255, 255): 15,
            (191, 191, 189): 16, (134, 202, 227): 17, (100, 100, 100): 255}
IGBP_NAME = {1: "Evergreen needleleaf", 2: "Evergreen broadleaf", 3: "Deciduous needleleaf", 4: "Deciduous broadleaf", 5: "Mixed forest",
             6: "Closed shrubland", 7: "Open shrubland", 8: "Woody savanna", 9: "Savanna", 10: "Grassland", 11: "Wetland", 12: "Cropland",
             13: "Urban", 14: "Crop/natural mosaic", 15: "Snow and ice", 16: "Barren", 17: "Water"}
KOPPEN_NAME = {1: "Af", 2: "Am", 3: "Aw", 4: "BWh", 5: "BWk", 6: "BSh", 7: "BSk", 8: "Csa", 9: "Csb", 10: "Csc", 11: "Cwa", 12: "Cwb", 13: "Cwc",
               14: "Cfa", 15: "Cfb", 16: "Cfc", 17: "Dsa", 18: "Dsb", 19: "Dsc", 20: "Dsd", 21: "Dwa", 22: "Dwb", 23: "Dwc", 24: "Dwd",
               25: "Dfa", 26: "Dfb", 27: "Dfc", 28: "Dfd", 29: "ET", 30: "EF"}
# ---- the mapping tables: CALIBRATED 2026-09-17 against Apple's z2-3 rasters (majority vote; --calibrate recomputes and prints hit rates)
# IGBP code -> Apple Landcover class (comment = Apple's class distribution under that IGBP code in the calibration set)
IGBP_APPLE = {
    0: "Water",             # (no class):  {}
    1: "Forest",            # Evergreen needleleaf: 0.816 {'Forest': 67017, 'Shrubland': 10196, 'Water': 2893, 'Herbaceous': 844}
    2: "Forest",            # Evergreen broadleaf: 0.884 {'Forest': 76741, 'Shrubland': 5999, 'Water': 2343, 'Cultivated': 734}
    3: "Forest",            # Deciduous needleleaf: 0.548 {'Forest': 7081, 'Shrubland': 5598, 'Water': 123, 'Herbaceous': 76}
    4: "Forest",            # Deciduous broadleaf: 0.725 {'Forest': 35147, 'Shrubland': 7986, 'Cultivated': 4039, 'Water': 591}
    5: "Forest",            # Mixed forest: 0.78 {'Forest': 110616, 'Shrubland': 20921, 'Cultivated': 6427, 'Water': 1987}
    6: "Shrubland",         # Closed shrubland: 0.573 {'Shrubland': 3991, 'Forest': 2046, 'Herbaceous': 732, 'Water': 75}
    7: "Shrubland",         # Open shrubland: 0.609 {'Shrubland': 257279, 'Herbaceous': 97090, 'Forest': 37727, 'Barren': 17488}
    8: "Forest",            # Woody savanna: 0.668 {'Forest': 192184, 'Shrubland': 73331, 'Herbaceous': 7808, 'Cultivated': 6784}
    9: "Shrubland",         # Savanna: 0.449 {'Shrubland': 144370, 'Forest': 125460, 'Herbaceous': 23524, 'Cultivated': 15852}
    10: "Shrubland",        # Grassland: 0.382 {'Shrubland': 260101, 'Herbaceous': 227966, 'Barren': 68177, 'Forest': 48407}
    11: "Shrubland",        # Wetland: 0.317 {'Shrubland': 16135, 'Forest': 11548, 'Water': 10424, 'Herbaceous': 8519}
    12: "Cultivated",       # Cropland: 0.711 {'Cultivated': 140994, 'Shrubland': 28298, 'Herbaceous': 10717, 'Forest': 9527}
    13: "Cultivated",       # Urban: 0.366 {'Cultivated': 5191, 'Ground': 3068, 'Forest': 2260, 'Shrubland': 1535}
    14: "Cultivated",       # Crop/natural mosaic: 0.469 {'Cultivated': 10004, 'Shrubland': 5749, 'Forest': 3364, 'Herbaceous': 871}
    15: "IceSnow",          # Snow and ice: 0.832 {'IceSnow': 340179, 'Barren': 34331, 'Herbaceous': 21967, 'Water': 6828}
    16: "Barren",           # Barren: 0.66 {'Barren': 257735, 'Herbaceous': 62614, 'Shrubland': 25719, 'Water': 14506}
    17: "Water",            # Water: 0.994 {'Water': 8437709, 'Herbaceous': 13614, 'Shrubland': 9964, 'Forest': 9786}
}
# (IGBP code, Koppen group letter) -> class where the majority differs from IGBP_APPLE (>= 2000 calibration pixels)
IGBP_KOPPEN_APPLE = {(4, "A"): "Shrubland", (5, "A"): "Shrubland", (9, "C"): "Forest", (9, "D"): "Forest", (10, "E"): "Herbaceous", (11, "A"): "Water", (11, "E"): "Water", (14, "A"): "Shrubland", (16, "E"): "Herbaceous"}
# Koppen class -> (ClimateTemperature 0 Arctic..6 VeryHot, ClimatePrecipitation 0 VeryWet..5 VeryDry)
KOPPEN_CODES = {
    1: (6, 0), 2: (6, 0), 3: (6, 1), 4: (6, 4), 5: (3, 4), 6: (6, 3),   # Af Am Aw BWh BWk BSh
    7: (3, 3), 8: (4, 3), 9: (4, 1), 11: (5, 1), 12: (4, 1), 14: (4, 1),   # BSk Csa Csb Cwa Cwb Cfa
    15: (3, 1), 16: (2, 0), 17: (3, 3), 18: (3, 3), 19: (1, 1), 20: (1, 2),   # Cfb Cfc Dsa Dsb Dsc Dsd
    21: (3, 1), 22: (3, 1), 23: (2, 1), 24: (1, 1), 25: (3, 1), 26: (2, 1),   # Dwa Dwb Dwc Dwd Dfa Dfb
    27: (1, 1), 28: (1, 2), 29: (1, 1), 30: (1, 0),   # Dfc Dfd ET EF
}
KOPPEN_CODES.setdefault(10, KOPPEN_CODES[9]); KOPPEN_CODES.setdefault(13, KOPPEN_CODES[12])   # Csc / Cwc: no calibration pixels, take the -b class
# class where GIBS has no tile at all (only a few polar z4 tiles): Koppen alone — E -> ice / barren, B -> shrubland, else forest
KOPPEN_FALLBACK = {**{k: "Forest" for k in range(1, 31)}, **{k: "Shrubland" for k in (4, 5, 6, 7)}, 29: "Barren", 30: "IceSnow"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def lat_of(fy):
    return math.degrees(2 * math.atan(math.exp((0.5 - fy) * 2 * math.pi)) - math.pi / 2)


def get(url, path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                open(path, "wb").write(r.read())
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # GIBS stores no tile where there is nothing to draw (open ocean / poles)
                open(path, "wb").close()
                return
            log(f"  {url}: {e} (attempt {attempt + 1})")
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            log(f"  {url}: {e} (attempt {attempt + 1})")
            time.sleep(3)
    raise SystemExit(f"download failed: {url}")


def gibs_igbp(z, x0, x1, y0, y1):
    """IGBP code raster of z tiles [x0,x1) x [y0,y1): nearest legend colour (palette PNGs -> exact), 255 = no data."""
    keys = np.array(list(IGBP_RGB.keys()), int)
    vals = np.array(list(IGBP_RGB.values()), int)
    out = np.full(((y1 - y0) * 256, (x1 - x0) * 256), 255, np.uint8)
    for ty in range(y0, y1):
        for tx in range(x0, x1):
            p = os.path.join(RAW, "gibs", GIBS_LAYER, GIBS_TIME, str(z), f"{ty}_{tx}.png")
            get(GIBS_URL.format(z=z, y=ty, x=tx), p)
            if os.path.getsize(p) == 0:
                continue
            rgba = np.asarray(Image.open(p).convert("RGBA")).astype(int)
            d = ((rgba[:, :, None, :3] - keys[None, None, :, :]) ** 2).sum(-1)
            code = vals[d.argmin(-1)].astype(np.uint8)
            code[rgba[..., 3] < 128] = 255
            out[(ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = code
    return out


def koppen_grid(x0, x1, y0, y1, W, H):
    """Koppen codes (0 = none/ocean) on a Web-Mercator window: x/y in world fraction (0 = left/top)."""
    kg = np.asarray(Image.open(os.path.join(RAW, "koppen", "1991_2020", "koppen_geiger_0p1.tif")))
    H0, W0 = kg.shape
    fy = y0 + (np.arange(H) + 0.5) / H * (y1 - y0)
    lats = np.array([lat_of(v) for v in fy])
    rows = np.clip(((90 - lats) / 180 * H0).astype(int), 0, H0 - 1)
    fx = x0 + (np.arange(W) + 0.5) / W * (x1 - x0)
    cols = np.clip((fx * W0).astype(int), 0, W0 - 1)
    return kg[rows][:, cols]


def terrarium(z, x0, x1, y0, y1):
    out = np.zeros(((y1 - y0) * 256, (x1 - x0) * 256), np.float32)
    for ty in range(y0, y1):
        for tx in range(x0, x1):
            p = os.path.join(RAW, "terrarium", f"{z}-{tx}-{ty}.png")
            get(TERRARIUM.format(z=z, x=tx, y=ty), p)
            if os.path.getsize(p) == 0:
                continue
            im = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
            out[(ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768
    return out


def encode_terrarium(h):
    v = np.clip(h, 0, None) + 32768.0          # sea and below-sea land -> 0: the App's globe mesh has no bathymetry
    r = np.floor(v / 256); g = np.floor(v - r * 256); b = np.floor((v - r * 256 - g) * 256)
    return np.stack([r, g, b], -1).astype(np.uint8)


def koppen_group(k):
    return "A" if 1 <= k <= 3 else "B" if 4 <= k <= 7 else "C" if 8 <= k <= 16 else "D" if 17 <= k <= 28 else "E" if k >= 29 else "-"


def classify(igbp, kop, classes):
    """IGBP + Koppen -> class index raster (255 = no data)."""
    out = np.full(igbp.shape, 255, np.uint8)
    groups = np.vectorize(koppen_group)(kop) if IGBP_KOPPEN_APPLE else None
    for code, cls in IGBP_APPLE.items():
        m = igbp == code
        out[m] = classes.index(cls)
    for (code, grp), cls in IGBP_KOPPEN_APPLE.items():
        out[(igbp == code) & (groups == grp)] = classes.index(cls)
    # GIBS serves no tile for a few all-ice / all-ocean z4 tiles (404): fill from Koppen alone
    miss = out == 255
    if miss.any():
        for k, cls in KOPPEN_FALLBACK.items():
            out[miss & (kop == k)] = classes.index(cls)
        out[miss & (kop == 0)] = classes.index("Water")
    return out


def climate(kop):
    T = np.full(kop.shape, 255, np.uint8); A = np.full(kop.shape, 255, np.uint8)
    for k, (t, a) in KOPPEN_CODES.items():
        m = kop == k
        T[m] = t; A[m] = a
    return T, A


def calibrate(igbp_w, kop_w, kop_c, classes):
    """Majority-vote tables against Apple's rasters (outside the repo) + hit rates.  Returns the tables and a report."""
    rep = {}
    a_cls = np.asarray(Image.open(os.path.join(APPLE, "spr-class-globe.png")))
    ok = (a_cls != 255) & (igbp_w != 255)
    # IGBP -> class
    conf = defaultdict(Counter)
    for code in np.unique(igbp_w[ok]):
        m = ok & (igbp_w == code)
        conf[int(code)] = Counter({classes[i]: int(c) for i, c in enumerate(np.bincount(a_cls[m], minlength=len(classes))) if c})
    table = {code: cnt.most_common(1)[0][0] for code, cnt in conf.items() if cnt}
    # IGBP x Koppen group -> class (only where it beats the IGBP-only choice)
    groups = np.vectorize(koppen_group)(kop_w)
    refine = {}
    for code in table:
        for grp in "ABCDE-":
            m = ok & (igbp_w == code) & (groups == grp)
            if m.sum() < 2000:
                continue
            cnt = Counter({classes[i]: int(c) for i, c in enumerate(np.bincount(a_cls[m], minlength=len(classes))) if c})
            best = cnt.most_common(1)[0][0]
            if best != table[code]:
                refine[(code, grp)] = best
    pred = np.full(igbp_w.shape, 255, np.uint8)
    for code, cls in table.items():
        pred[igbp_w == code] = classes.index(cls)
    hit_plain = float((pred[ok] == a_cls[ok]).mean())
    for (code, grp), cls in refine.items():
        pred[(igbp_w == code) & (groups == grp)] = classes.index(cls)
    hit_ref = float((pred[ok] == a_cls[ok]).mean())
    land = ok & (a_cls != classes.index("Water")) & (igbp_w != 17) & (igbp_w != 0)
    hit_land = float((pred[land] == a_cls[land]).mean())
    rep["class"] = {"pixels_compared": int(ok.sum()), "hit_rate_igbp_only": round(hit_plain, 4), "hit_rate_igbp_koppen": round(hit_ref, 4),
                    "land_pixels_compared": int(land.sum()), "hit_rate_land_only": round(hit_land, 4),
                    "per_igbp": {f"{c} {IGBP_NAME.get(c, '')}": {"apple_majority": table[c], "hit": round(conf[c][table[c]] / sum(conf[c].values()), 3), "n": sum(conf[c].values()),
                                                                  "apple_distribution": dict(conf[c].most_common(4))} for c in sorted(table)},
                    "refinements": {f"{c}|{g}": cls for (c, g), cls in sorted(refine.items())}}
    # Koppen -> climate codes (1024^2 grid)
    a_t = np.asarray(Image.open(os.path.join(APPLE, "climate-temp-globe.png")))
    a_a = np.asarray(Image.open(os.path.join(APPLE, "climate-arid-globe.png")))
    okc = (a_t != 255) & (kop_c != 0)
    codes = {}
    per = {}
    for k in np.unique(kop_c[okc]):
        m = okc & (kop_c == k)
        t = Counter(a_t[m].tolist()).most_common(1)[0][0]
        a = Counter(a_a[m].tolist()).most_common(1)[0][0]
        codes[int(k)] = (int(t), int(a))
        per[f"{int(k)} {KOPPEN_NAME[int(k)]}"] = {"temp": int(t), "precip": int(a), "n": int(m.sum()),
                                                 "hit_temp": round(float((a_t[m] == t).mean()), 3), "hit_precip": round(float((a_a[m] == a).mean()), 3),
                                                 "temp_distribution": dict(Counter(a_t[m].tolist()).most_common(3)), "precip_distribution": dict(Counter(a_a[m].tolist()).most_common(3))}
    T, A = np.full(kop_c.shape, 255, np.uint8), np.full(kop_c.shape, 255, np.uint8)
    for k, (t, a) in codes.items():
        T[kop_c == k] = t; A[kop_c == k] = a
    rep["climate"] = {"pixels_compared": int(okc.sum()), "hit_rate_temp": round(float((T[okc] == a_t[okc]).mean()), 4),
                      "hit_rate_precip": round(float((A[okc] == a_a[okc]).mean()), 4),
                      "within_one_temp": round(float((np.abs(T[okc].astype(int) - a_t[okc].astype(int)) <= 1).mean()), 4),
                      "within_one_precip": round(float((np.abs(A[okc].astype(int) - a_a[okc].astype(int)) <= 1).mean()), 4), "per_koppen": per}
    return table, refine, codes, rep


def albedo(cls_w, T_w, A_w, cls_ea, T_ea, A_ea, classes):
    """ground-globe-{light,dark}(-ea).png: the class rasters painted with the DvMt globe colours (client:69 = 0, Apple z4 band)
    x climate HSV cells x light(0,0,1) — the same maths map/globe.js runs in the browser; kept as files for the UI's stand-in
    source.  Colours: ui/basemap/dvmt-materials.json; cells: shader-numbers.json groundSettings; nothing from Apple's tiles."""
    import spr_globe as G
    G.DVMT_STYLE = 0
    G.APPLE_ZOOM = 4.0
    table = json.load(open(MATERIALS))
    extra_lin = table.get("class_colour_lin_captured", {})
    sheet = G.ground.sheet_colours()
    R = G.ground.Resolver(G.ground.STYL)
    for cls in classes:
        if cls not in sheet and cls not in extra_lin:
            for mode in ("Light", "Dark"):
                name = f"Landcover-{cls}-Elevated-{mode}-Base"
                bands = [{"zmin": a, "zmax": b, "rgb": v["rgba"][:3], "a": v["rgba"][3]} for a, b, v in R.bands(name, 1) if isinstance(v, dict) and "rgba" in v]
                if bands:
                    sheet.setdefault(cls, {})[mode.lower()] = bands
    sh = json.load(open(G.ground.SHADER))
    L = sh["lighting"]
    cube_z = sh["ambient_irradiance_cube"]["face_mean"][sh["ambient_irradiance_cube"]["faces_order"].index("+z")]
    light = L["ambientLightColor_linear"][0] * cube_z + L["lightColor_linear"][0] * L["tileLightDirection"][2]
    adj = {"light": sh["climate_tinting"]["groundSettings.json"]["1-6"], "dark": sh["climate_tinting"]["groundSettingsNight.json"]["1-9"]}
    water = classes.index("Water")
    for tag, cls, T, A, rep in (("", cls_w, T_w, A_w, 4), ("-ea", cls_ea, T_ea, A_ea, 8)):
        Tb = np.repeat(np.repeat(T, rep, 0), rep, 1); Ab = np.repeat(np.repeat(A, rep, 0), rep, 1)
        for mode in ("light", "dark"):
            rgba = G.paint(np.where(cls == 255, 0, cls), Tb, Ab, sheet, adj[mode], mode, light, classes, extra_lin)
            rgba[(cls == 255) | (cls == water), 3] = 0
            Image.fromarray(rgba).save(os.path.join(OUT, f"ground-globe{tag}-{mode}.png"), optimize=True)
            log(f"ground-globe{tag}-{mode}.png written")


def main():
    classes = json.load(open(MATERIALS))["classes"]
    log("GIBS world z4 (256 tiles) …")
    igbp_w = gibs_igbp(4, 0, 16, 0, 16)
    log("GIBS East Asia z5 (64 tiles) …")
    igbp_ea = gibs_igbp(5, EA["x"][0] * 4, EA["x"][1] * 4, EA["y"][0] * 4, EA["y"][1] * 4)
    kop_w = koppen_grid(0, 1, 0, 1, N_WORLD, N_WORLD)
    kop_c = koppen_grid(0, 1, 0, 1, N_WORLD // 4, N_WORLD // 4)
    ea_box = (EA["x"][0] / 8, EA["x"][1] / 8, EA["y"][0] / 8, EA["y"][1] / 8)
    kop_ea = koppen_grid(*ea_box, N_EA, N_EA)
    kop_ea_c = koppen_grid(*ea_box, N_EA // 8, N_EA // 8)
    global IGBP_APPLE, IGBP_KOPPEN_APPLE, KOPPEN_CODES
    report = None
    if "--calibrate" in sys.argv:
        if not os.path.exists(os.path.join(APPLE, "spr-class-globe.png")):
            raise SystemExit("calibration rasters not found outside the repo and KOPPEN_CODES is empty")
        table, refine, codes, report = calibrate(igbp_w, kop_w, kop_c, classes)
        IGBP_APPLE = {**IGBP_APPLE, **table}
        IGBP_KOPPEN_APPLE = refine
        KOPPEN_CODES = codes
        log(json.dumps({k: v for k, v in report["class"].items() if k != "per_igbp"}, indent=1))
        log(json.dumps({k: v for k, v in report["climate"].items() if k != "per_koppen"}, indent=1))
    cls_w = classify(igbp_w, kop_w, classes)
    cls_ea = classify(igbp_ea, kop_ea, classes)
    T_w, A_w = climate(kop_c)
    T_ea, A_ea = climate(kop_ea_c)
    log("terrarium world z3 (64 tiles) + East Asia z4 (16 tiles) …")
    h_w = terrarium(3, 0, 8, 0, 8)
    h_ea = terrarium(4, EA["x"][0] * 2, EA["x"][1] * 2, EA["y"][0] * 2, EA["y"][1] * 2)
    Image.fromarray(cls_w).save(os.path.join(OUT, "spr-class-globe.png"), optimize=True)
    Image.fromarray(cls_ea).save(os.path.join(OUT, "spr-class-globe-ea.png"), optimize=True)
    Image.fromarray(T_w).save(os.path.join(OUT, "climate-temp-globe.png"), optimize=True)
    Image.fromarray(A_w).save(os.path.join(OUT, "climate-arid-globe.png"), optimize=True)
    Image.fromarray(T_ea).save(os.path.join(OUT, "climate-temp-globe-ea.png"), optimize=True)
    Image.fromarray(A_ea).save(os.path.join(OUT, "climate-arid-globe-ea.png"), optimize=True)
    Image.fromarray(encode_terrarium(h_w)).save(os.path.join(OUT, "height-globe.png"), optimize=True)
    Image.fromarray(encode_terrarium(h_ea)).save(os.path.join(OUT, "height-globe-ea.png"), optimize=True)
    albedo(cls_w, T_w, A_w, cls_ea, T_ea, A_ea, classes)
    height_check = None
    if report is not None:
        a_h = np.asarray(Image.open(os.path.join(APPLE, "height-globe.png")).convert("RGB")).astype(np.float32)
        a_h = a_h[..., 0] * 256 + a_h[..., 1] + a_h[..., 2] / 256 - 32768
        a_c = np.asarray(Image.open(os.path.join(APPLE, "spr-class-globe.png")))[::2, ::2]
        m = (a_c != 255) & (a_c != classes.index("Water")) & (a_h > 0)
        d = np.clip(h_w, 0, None)[m] - a_h[m]
        height_check = {"land_pixels_compared": int(m.sum()), "mean_diff_m": round(float(d.mean()), 1), "rmse_m": round(float(np.sqrt((d ** 2).mean())), 1),
                        "note": "Apple's mesh is ~25 km vertex spacing; terrarium z3 is 20 km/px at the equator — same order"}
        log(json.dumps(height_check))
    meta = {
        "what": "globe ground rasters from third-party data mapped to Apple's decoded classes / codes (RENDER-PIPELINE 2.4b); no Apple tile content",
        "generator": "pipeline/basemap/globe_rasters.py",
        "sources": {"land_cover": f"NASA GIBS {GIBS_LAYER} {GIBS_TIME} (MODIS MCD12 IGBP, 500 m; z4 world / z5 East Asia tiles)",
                    "climate": "Beck et al. 2023 Koppen-Geiger 1991-2020 0.1 deg (figshare 21789074, CC BY 4.0)",
                    "height": "AWS terrarium DEM (z3 world / z4 East Asia), sea clamped to 0"},
        "world": {"crs": "EPSG:3857 whole world", "size": N_WORLD, "coordinates": [[-180, 85.0511], [180, 85.0511], [180, -85.0511], [-180, -85.0511]],
                  "files": ["spr-class-globe.png (4096, class index, 255 = no data)", "climate-temp-globe.png (1024)", "climate-arid-globe.png (1024)", "height-globe.png (2048, terrarium)",
                            "ground-globe-light.png / ground-globe-dark.png (class raster painted with the DvMt globe colours, the UI's stand-in)"]},
        "east_asia": {"lng": [90, 180], "lat": [0, 66.51326], "size": N_EA, "coordinates": [[90, 66.51326], [180, 66.51326], [180, 0], [90, 0]],
                      "files": ["spr-class-globe-ea.png (2048, class index)", "climate-temp-globe-ea.png (256)", "climate-arid-globe-ea.png (256)", "height-globe-ea.png (1024, terrarium)",
                                "ground-globe-ea-light.png / ground-globe-ea-dark.png (painted, as the world set)"]},
        "classes": classes, "class_index_255": "no data",
        "mapping": {"igbp_to_class": {f"{c} {IGBP_NAME.get(c, '')}": v for c, v in sorted(IGBP_APPLE.items())},
                    "igbp_koppen_group_to_class": {f"{c}|{g}": v for (c, g), v in sorted(IGBP_KOPPEN_APPLE.items())},
                    "koppen_to_codes": {f"{k} {KOPPEN_NAME[k]}": {"temp": t, "precip": a} for k, (t, a) in sorted(KOPPEN_CODES.items())}},
        "climate": {"temp_codes": "0 Arctic 1 VeryCold 2 Cold 3 Cool 4 Warm 5 Hot 6 VeryHot (VectorKit gss enum strings); cell = 1 + (T-3)/3",
                    "arid_codes": "0 VeryWet 1 Wet 2 Moist 3 SemiDry 4 Dry 5 VeryDry; cell = 1 + (A-3)/3 for A<3, 1 + (A-3)/2 for A>=3 (SHADER-NUMBERS 3.2)"},
        "height": {"source": "terrarium (see sources); the App's z1-4 groundElevationScale 14 / 9 / 7 / 5 applies as before (RENDER-PIPELINE 2.5)"},
        "colour_source": "DvMt material tables, client:69 = 0 (ui/basemap/dvmt-materials.json); the UI paints classes in the browser",
    }
    old = json.load(open(META)) if os.path.exists(META) else {}
    for k in ("light_flat", "climate"):
        if k in old and k not in meta:
            meta[k] = old[k]
    if "climate" in old and "hsv_deltas" in old["climate"]:
        meta["climate"]["hsv_deltas"] = old["climate"]["hsv_deltas"]
    if "height" in old and "exaggeration_by_apple_zoom" in old["height"]:
        meta["height"]["exaggeration_by_apple_zoom"] = old["height"]["exaggeration_by_apple_zoom"]
    if report is not None:
        meta["calibration"] = {"against": "Apple's z2-3 globe rasters decoded from its tile cache, kept outside the repo (~/Money/styl-work/apple-data/map-data)",
                               "class": {k: v for k, v in report["class"].items() if k != "per_igbp"}, "class_per_igbp": report["class"]["per_igbp"],
                               "climate": {k: v for k, v in report["climate"].items() if k != "per_koppen"}, "climate_per_koppen": report["climate"]["per_koppen"],
                               "height": height_check}
    elif "calibration" in old:
        meta["calibration"] = old["calibration"]
    json.dump(meta, open(META, "w"), indent=1, ensure_ascii=False)
    log("done")


if __name__ == "__main__":
    main()
