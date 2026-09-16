#!/usr/bin/env python3
"""Ground colour rasters for map/ (z 5-8 overlay band): Apple's land-cover palette + climate tint, from
the decoded originals — no sampled colours.

    python3 pipeline/basemap/ground.py            # run from the repo root (downloads GIBS tiles on first run)

How the App colours a land pixel (SHADER-NUMBERS.md 3.2 / 4.4, basemap/data/shader/shader-numbers.json):
    albedo_lin = HSV-tint( linearise(Landcover-<Class>.<Light|Dark>-Elevated fillColor at the tile zoom),
                           temperature axis (arctic | base | veryHot) x aridity axis (veryWet | base | veryDry) )
    colour_lin = albedo_lin * light(n),  light(n) = ambient * cube(n) + lightColor * max(n.L, 0)
    flat ground n = (0,0,1):  light = 0.49683 * 0.8120 + 0.7085 * 0.90625 = 1.0455  (lighting, ambient_irradiance_cube)
    out = sRGB-encode(colour_lin)
Inputs:
    ~/Money/styl-work/default-56689.styl      Landcover-*-Elevated-{Light,Dark}-Base fillColor bands (Apple zoom)
    basemap/data/shader/shader-numbers.json   climate_tinting.groundSettings[Night].json HSV deltas, lighting
    pipeline/basemap/raw/koppen/               Beck 2023 Koppen-Geiger 0.1 deg -> temperature/aridity codes (table below)
    NASA GIBS MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual (500 m, EPSG:3857 z7 tiles, box lat 0-60 lng 90-160)
    pipeline/basemap/raw/ne_land/             Natural Earth 10m land (alpha mask, same as climate-globe.png)
Outputs (map/data/):
    ground-light.png / ground-dark.png        global 4096^2 Web-Mercator, class from Koppen only (fallback outside the box)
    ground-ea-light.png / ground-ea-dark.png  East-Asia box at GIBS z7 resolution, class from MODIS IGBP
    ui/basemap/ground.json                    bounds, sources, the two mapping tables, decoded sheet colours (-> meta-ui.json)
"""
import io
import json
import math
import os
import sys
import time
import urllib.request

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "styl"))
import nelib  # noqa: E402
from resolve import Resolver  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(ROOT, "map", "data")
STYL = os.path.expanduser("~/Money/styl-work/default-56689.styl")
SHADER = os.path.join(ROOT, "basemap", "data", "shader", "shader-numbers.json")
GIBS_LAYER = "MODIS_Combined_L3_IGBP_Land_Cover_Type_Annual"
GIBS_TIME = "2024-01-01"
GIBS_URL = f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{GIBS_LAYER}/default/{GIBS_TIME}/GoogleMapsCompatible_Level8/{{z}}/{{y}}/{{x}}.png"
GIBS_COLORMAP = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/MODIS_IGBP_Land_Cover_Type.xml"
GIBS_Z = 7
EA_DOWNSAMPLE = 2         # output raster at GIBS z6 resolution (3200x3456): a 6400x6912 image source decodes to 177 MB
                          # and stalled the acceptance's software-GL render; z6 is 2 raster px per screen px at MapLibre z7
BOX = {"lat": (0.0, 60.0), "lng": (90.0, 160.0)}        # acceptance 2026-09-16: East Asia + Japan only
APPLE_ZOOM = 6.0          # sheet band for the overlay rasters: Apple z6 = MapLibre z5 (the Japan acceptance view)
N_GLOBAL = 4096

# GIBS colormap rgb -> IGBP code (fetched from GIBS_COLORMAP, 2026-09-16); 0/17 share one colour (water)
IGBP_RGB = {(33, 138, 33): 1, (49, 204, 49): 2, (152, 204, 49): 3, (150, 250, 150): 4, (141, 186, 141): 5,
            (186, 141, 141): 6, (245, 222, 179): 7, (218, 235, 157): 8, (255, 213, 0): 9, (240, 185, 103): 10,
            (71, 131, 181): 11, (250, 239, 115): 12, (255, 0, 0): 13, (153, 147, 86): 14, (255, 255, 255): 15,
            (191, 191, 189): 16, (134, 202, 227): 17, (100, 100, 100): 255}
# IGBP class -> Apple Landcover class (the reasoning is in map/README.md)
IGBP_APPLE = {1: "Forest", 2: "Forest", 3: "Forest", 4: "Forest", 5: "Forest", 8: "Forest",
              6: "Shrubland", 7: "Shrubland", 9: "Herbaceous", 10: "Herbaceous", 11: "Wetlands",
              12: "Cultivated", 14: "Cultivated", 13: "Ground", 15: "IceSnow", 16: "Barren", 17: None, 0: None, 255: None}
# 13 Urban -> Ground, not Developed: the App paints the Kanto / Osaka plains in the Ground colour at Apple z6
# (light (240,241,229) = Ground (239,240,230) x light; dark (60,79,106) = Ground dark (62,79,104) x light), while
# Landcover-Developed-Elevated-Dark is lavender (204,170,255) — a higher-zoom class (verification on snap-japan{,-dark}.png)
# Koppen (Beck 2023 code) -> (temperature code, aridity code) in palette-cell units:
# temperature 0 arctic / 1 base / 2 veryHot ; aridity 0 veryWet / 1 base / 2 veryDry.  The App's own
# temperature/aridity textures are not decoded (VMP4), so Koppen stands in; the values are checked against the
# 705 App land samples (palette-land.json) in map/README.md.
KOPPEN_CLIMATE = {
    1: (2, 1), 2: (2, 1), 3: (1.5, 1),                      # Af Am Aw
    4: (1.5, 2), 5: (1, 2), 6: (1.5, 1), 7: (1, 1.5),        # BWh BWk BSh BSk
    8: (1, 1.5), 9: (1, 1.5), 10: (1, 1.5),                  # Csa Csb Csc
    11: (1.5, 1), 12: (1, 1.5), 13: (1, 1.5),                # Cwa Cwb Cwc
    14: (1, 1), 15: (1, 1), 16: (1, 1),                      # Cfa Cfb Cfc
    17: (1, 1), 18: (1, 1), 19: (0.5, 1.5), 20: (0.5, 1.5),  # Dsa Dsb Dsc Dsd
    21: (1, 1), 22: (1, 1), 23: (0.5, 1.5), 24: (0.5, 1.5),  # Dwa Dwb Dwc Dwd
    25: (1, 1), 26: (1, 1), 27: (0.5, 1), 28: (0.5, 1),      # Dfa Dfb Dfc Dfd
    29: (0, 1), 30: (0, 1),                                  # ET EF
}
# Koppen -> default Apple class where no land-cover raster is available (outside the box)
KOPPEN_CLASS = {4: "Barren", 5: "Barren", 6: "Shrubland", 7: "Shrubland", 29: "Barren", 30: "IceSnow"}
DEFAULT_CLASS = "Forest"
CLASSES = ["Forest", "Wetlands", "Cultivated", "Herbaceous", "Shrubland", "Barren", "IceSnow", "Ground", "Developed"]
UNTINTED = {"Ground", "Developed"}     # SHADER-NUMBERS 4.4: all 9 palette cells equal


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---- colour maths (linear RGB, as the shader) ------------------------------------------------------------
def srgb_to_lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb8(v):
    v = np.clip(v, 0, 1)
    s = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    return np.clip(np.round(s * 255), 0, 255).astype(np.uint8)


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(-1); mn = rgb.min(-1); d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rc = np.where(m & (mx == r), ((g - b) / np.where(d == 0, 1, d)) % 6, 0)
    gc = np.where(m & (mx == g) & (mx != r), (b - r) / np.where(d == 0, 1, d) + 2, 0)
    bc = np.where(m & (mx == b) & (mx != r) & (mx != g), (r - g) / np.where(d == 0, 1, d) + 4, 0)
    h = (rc + gc + bc) * 60.0
    s = np.where(mx > 1e-9, d / np.where(mx == 0, 1, mx), 0)
    return np.stack([h, s, mx], -1)


def hsv_to_rgb(hsv):
    h, s, v = hsv[..., 0] % 360.0, np.clip(hsv[..., 1], 0, 1), np.clip(hsv[..., 2], 0, 1)
    c = v * s; hp = h / 60.0; x = c * (1 - np.abs(hp % 2 - 1)); m = v - c
    i = np.floor(hp).astype(int) % 6
    r = np.choose(i, [c, x, 0 * c, 0 * c, x, c]); g = np.choose(i, [x, c, c, x, 0 * c, 0 * c]); b = np.choose(i, [0 * c, 0 * c, x, c, c, x])
    return np.stack([r + m, g + m, b + m], -1)


def tint(base_lin, dh, ds, dv):
    """groundSettings HSV adjustment of a linear-RGB colour (additive H deg, S, V)."""
    hsv = rgb_to_hsv(np.asarray(base_lin, float)[None, :])
    hsv[..., 0] += dh; hsv[..., 1] += ds; hsv[..., 2] += dv
    return hsv_to_rgb(hsv)[0]


def cells_for(base_lin, adj, untinted):
    """3x3 palette cells [aridity 0..2][temperature 0..2] (SHADER-NUMBERS 4.4: axes add)."""
    t_adj = [adj["arcticHSVAdjustment"], (0, 0, 0), adj["veryHotHSVAdjustment"]]
    a_adj = [adj["veryWetHSVAdjustment"], (0, 0, 0), adj["veryDryHSVAdjustment"]]
    cells = np.zeros((3, 3, 3))
    for ai in range(3):
        for ti in range(3):
            if untinted:
                cells[ai, ti] = base_lin
            else:
                dh = t_adj[ti][0] + a_adj[ai][0]; ds = t_adj[ti][1] + a_adj[ai][1]; dv = t_adj[ti][2] + a_adj[ai][2]
                cells[ai, ti] = tint(base_lin, dh, ds, dv)
    return cells


def sample_cells(cells, T, A):
    """Bilinear palette lookup for temperature/aridity codes in [0, 2] (the App's sampler is linear)."""
    t0 = np.clip(np.floor(T).astype(int), 0, 1); a0 = np.clip(np.floor(A).astype(int), 0, 1)
    ft = (T - t0)[..., None]; fa = (A - a0)[..., None]
    c00 = cells[a0, t0]; c01 = cells[a0, t0 + 1]; c10 = cells[a0 + 1, t0]; c11 = cells[a0 + 1, t0 + 1]
    return (c00 * (1 - ft) + c01 * ft) * (1 - fa) + (c10 * (1 - ft) + c11 * ft) * fa


# ---- inputs ------------------------------------------------------------------------------------------------
def sheet_colours():
    """Landcover-<Class>-Elevated-{Light,Dark}-Base fillColor bands from the flat sheet (Apple zoom)."""
    R = Resolver(STYL)
    out = {}
    for cls in CLASSES:
        out[cls] = {}
        for mode in ("Light", "Dark"):
            name = f"Landcover-{cls}-Elevated-{mode}-Base"
            if name not in R.by_name:
                log(f"  {name}: not in sheet")
                continue
            bands = []
            for zmin, zmax, v in R.bands(name, 1):
                if isinstance(v, dict) and "rgba" in v:
                    bands.append({"zmin": zmin, "zmax": zmax, "rgb": v["rgba"][:3], "a": v["rgba"][3]})
            out[cls][mode.lower()] = bands
    return out


def band_at(bands, z):
    for b in bands:
        if b["zmin"] <= z < b["zmax"]:
            return b
    return bands[-1] if bands else None


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def land_mask(x0, x1, y0, y1, W, H):
    """Natural Earth land rasterised on a Web-Mercator window: x in [x0,x1) world fraction, y likewise (0 = top)."""
    land = np.zeros((H, W), dtype=np.uint8)
    for kind, rings, _ in nelib.read_layer(os.path.join(RAW, "ne_land", "ne_10m_land")):
        if kind != "polygon":
            continue
        for r in rings:
            fx = (r[:, 0] + 180) / 360
            fy = 0.5 - np.array([merc_y(v) for v in np.clip(r[:, 1], -85.05, 85.05)]) / (2 * math.pi)
            if fx.max() < x0 or fx.min() > x1 or fy.max() < y0 or fy.min() > y1:
                continue
            x = (fx - x0) / (x1 - x0) * W; y = (fy - y0) / (y1 - y0) * H
            px0, px1 = max(int(x.min()), 0), min(int(x.max()) + 2, W)
            py0, py1 = max(int(y.min()), 0), min(int(y.max()) + 2, H)
            if px1 <= px0 or py1 <= py0:
                continue
            im = Image.new("1", (px1 - px0, py1 - py0), 0)
            ImageDraw.Draw(im).polygon(list(zip((x - px0).tolist(), (y - py0).tolist())), fill=1)
            land[py0:py1, px0:px1] ^= np.asarray(im, dtype=np.uint8)
    return land


def koppen_grid(x0, x1, y0, y1, W, H):
    kg = np.asarray(Image.open(os.path.join(RAW, "koppen", "1991_2020", "koppen_geiger_0p1.tif")))
    H0, W0 = kg.shape
    fy = y0 + (np.arange(H) + 0.5) / H * (y1 - y0)
    lats = np.degrees(2 * np.arctan(np.exp((0.5 - fy) * 2 * math.pi)) - math.pi / 2)
    rows = np.clip(((90 - lats) / 180 * H0).astype(int), 0, H0 - 1)
    fx = x0 + (np.arange(W) + 0.5) / W * (x1 - x0)
    cols = np.clip((fx * W0).astype(int), 0, W0 - 1)
    return kg[rows][:, cols]


def gibs_tiles():
    """IGBP class raster of the box at GIBS_Z (nearest-colour decode of the GIBS PNG tiles, cached in raw/gibs)."""
    n = 2 ** GIBS_Z
    fx0 = (BOX["lng"][0] + 180) / 360; fx1 = (BOX["lng"][1] + 180) / 360
    fy0 = 0.5 - merc_y(BOX["lat"][1]) / (2 * math.pi); fy1 = 0.5 - merc_y(BOX["lat"][0]) / (2 * math.pi)
    tx0, tx1 = int(fx0 * n), int(math.ceil(fx1 * n)); ty0, ty1 = int(fy0 * n), int(math.ceil(fy1 * n))
    W, H = (tx1 - tx0) * 256, (ty1 - ty0) * 256
    cls = np.zeros((H, W), dtype=np.uint8)
    cache = os.path.join(RAW, "gibs", GIBS_LAYER, GIBS_TIME, str(GIBS_Z))
    os.makedirs(cache, exist_ok=True)
    keys = np.array(list(IGBP_RGB.keys()), int); vals = np.array(list(IGBP_RGB.values()), int)
    fetched = 0
    for ty in range(ty0, ty1):
        for tx in range(tx0, tx1):
            p = os.path.join(cache, f"{ty}_{tx}.png")
            if not os.path.exists(p):
                url = GIBS_URL.format(z=GIBS_Z, y=ty, x=tx)
                for attempt in range(3):
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "transit-basemap/1.0 (github herclyon; land-cover class raster)"})
                        with urllib.request.urlopen(req, timeout=30) as r:
                            open(p, "wb").write(r.read())
                        fetched += 1
                        break
                    except Exception as e:  # noqa: BLE001
                        log(f"  {url}: {e} (attempt {attempt + 1})"); time.sleep(2)
            rgba = np.asarray(Image.open(p).convert("RGBA")).astype(int)
            im = rgba[..., :3]
            # nearest legend colour (the tiles are palette PNGs, so this is exact); transparent = nodata (255)
            d = ((im[:, :, None, :] - keys[None, None, :, :]) ** 2).sum(-1)
            code = vals[d.argmin(-1)]
            code[rgba[..., 3] < 128] = 255
            cls[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = code
    if EA_DOWNSAMPLE > 1:
        # majority of each block would be better for a categorical raster; nearest (top-left) keeps thin coasts as they are
        cls = cls[::EA_DOWNSAMPLE, ::EA_DOWNSAMPLE]
        H, W = cls.shape
    log(f"GIBS: {(tx1 - tx0) * (ty1 - ty0)} tiles ({fetched} fetched), raster {W}x{H} (downsample {EA_DOWNSAMPLE})")
    bounds = [[tx0 / n * 360 - 180, lat_of(ty0 / n)], [tx1 / n * 360 - 180, lat_of(ty0 / n)],
              [tx1 / n * 360 - 180, lat_of(ty1 / n)], [tx0 / n * 360 - 180, lat_of(ty1 / n)]]
    return cls, (tx0 / n, tx1 / n, ty0 / n, ty1 / n), bounds


def lat_of(fy):
    return math.degrees(2 * math.atan(math.exp((0.5 - fy) * 2 * math.pi)) - math.pi / 2)


# ---- rasters -----------------------------------------------------------------------------------------------
def paint(cls_idx, kop, land, sheet, adj, mode, light):
    """cls_idx: int raster indexing CLASSES (-1 = no land cover -> Koppen default); kop: Koppen codes."""
    H, W = kop.shape
    T = np.ones((H, W)); A = np.ones((H, W))
    for k, (t, a) in KOPPEN_CLIMATE.items():
        m = kop == k
        T[m] = t; A[m] = a
    # class raster: MODIS where given, Koppen default elsewhere
    ci = cls_idx.copy()
    fallback = ci < 0
    if fallback.any():
        default = np.full((H, W), CLASSES.index(DEFAULT_CLASS))
        for k, c in KOPPEN_CLASS.items():
            default[kop == k] = CLASSES.index(c)
        ci[fallback] = default[fallback]
    out = np.zeros((H, W, 3))
    for i, cls in enumerate(CLASSES):
        m = ci == i
        if not m.any():
            continue
        b = band_at(sheet[cls][mode], APPLE_ZOOM)
        base = srgb_to_lin(b["rgb"])
        cells = cells_for(base, adj, cls in UNTINTED)
        out[m] = sample_cells(cells, T[m], A[m])
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[..., :3] = lin_to_srgb8(out * light)
    rgba[..., 3] = 255
    rgba[land == 0, 3] = 0
    return rgba


def main():
    sn = json.load(open(SHADER))
    L = sn["lighting"]
    cube_z = sn["ambient_irradiance_cube"]["face_mean"][sn["ambient_irradiance_cube"]["faces_order"].index("+z")]
    light = L["ambientLightColor_linear"][0] * cube_z + L["lightColor_linear"][0] * L["tileLightDirection"][2]
    log(f"light(0,0,1) = {L['ambientLightColor_linear'][0]} * {cube_z} + {L['lightColor_linear'][0]} * {L['tileLightDirection'][2]} = {light:.4f}")
    adj_day = sn["climate_tinting"]["groundSettings.json"]["1-6"]
    adj_night = sn["climate_tinting"]["groundSettingsNight.json"]["1-9"]
    sheet = sheet_colours()
    for cls in CLASSES:
        log(f"  {cls:10s} light {band_at(sheet[cls]['light'], APPLE_ZOOM)['rgb'] if sheet[cls].get('light') else None}  dark {band_at(sheet[cls]['dark'], APPLE_ZOOM)['rgb'] if sheet[cls].get('dark') else None}")

    # global fallback raster (Koppen class + Koppen tint)
    N = N_GLOBAL
    kop = koppen_grid(0, 1, 0, 1, N, N)
    land = land_mask(0, 1, 0, 1, N, N)
    for mode, adj in (("light", adj_day), ("dark", adj_night)):
        rgba = paint(np.full((N, N), -1), kop, land, sheet, adj, mode, light)
        Image.fromarray(rgba).save(os.path.join(OUT, f"ground-{mode}.png"), optimize=True)
        log(f"ground-{mode}.png: {int((rgba[..., 3] > 0).sum())} land px")

    # East Asia box: MODIS IGBP class
    igbp, (fx0, fx1, fy0, fy1), bounds = gibs_tiles()
    H, W = igbp.shape
    cls_idx = np.full((H, W), -1)
    for code, cls in IGBP_APPLE.items():
        if cls is not None:
            cls_idx[igbp == code] = CLASSES.index(cls)
    kop_b = koppen_grid(fx0, fx1, fy0, fy1, W, H)
    land_b = land_mask(fx0, fx1, fy0, fy1, W, H)
    land_b[igbp == 17] = 0          # MODIS water (lakes, coastal water) -> transparent, the water layers show
    for mode, adj in (("light", adj_day), ("dark", adj_night)):
        rgba = paint(cls_idx, kop_b, land_b, sheet, adj, mode, light)
        # unclassified land inside the box keeps the Koppen default (cls_idx -1 handled in paint)
        Image.fromarray(rgba).save(os.path.join(OUT, f"ground-ea-{mode}.png"), optimize=True)
        log(f"ground-ea-{mode}.png: {W}x{H}, {os.path.getsize(os.path.join(OUT, f'ground-ea-{mode}.png')) / 1e6:.1f} MB")
    hist = {int(k): int(v) for k, v in zip(*np.unique(igbp, return_counts=True))}

    meta = {
        "what": "ground colour rasters for the z5-8 overlay band: Landcover sheet colour x groundSettings climate tint x flat-ground light, sRGB-encoded",
        "formula": "sRGB(linearise(fillColor) tinted by (temperature, aridity) HSV cells, bilinear, x light(0,0,1))",
        "light_flat_ground": {"value": round(light, 4), "expr": "ambientLightColor * cube(+z) + lightColor * L.z",
                              "source": "basemap/data/shader/shader-numbers.json lighting.{ambientLightColor_linear,lightColor_linear,tileLightDirection}, ambient_irradiance_cube.face_mean[+z]"},
        "sheet": {"file": os.path.basename(STYL), "styles": "Landcover-<Class>-Elevated-{Light,Dark}-Base 1:fillColor", "apple_zoom_used": APPLE_ZOOM,
                  "note": "Apple z = MapLibre z + 1; band containing Apple z6 = the MapLibre z5 acceptance view", "colours": sheet},
        "hsv": {"day": adj_day, "night": adj_night, "source": "shader-numbers.json climate_tinting.groundSettings.json['1-6'] / groundSettingsNight.json['1-9']",
                "cells": "3x3 per class, axes add (SHADER-NUMBERS 4.4), sampled bilinearly by the codes below"},
        "koppen_climate": {str(k): {"temperature": v[0], "aridity": v[1]} for k, v in KOPPEN_CLIMATE.items()},
        "koppen_default_class": dict(KOPPEN_CLASS, default=DEFAULT_CLASS),
        "igbp_to_apple": {str(k): v for k, v in IGBP_APPLE.items()},
        "landcover_source": {"name": "NASA GIBS " + GIBS_LAYER + " (MODIS MCD12Q1 IGBP, 500 m)", "url_template": GIBS_URL, "time": GIBS_TIME,
                             "colormap": GIBS_COLORMAP, "tile_zoom": GIBS_Z, "box": BOX, "igbp_histogram": hist},
        "global": {"size_px": N, "bounds": [[-180, 85.0511], [180, 85.0511], [180, -85.0511], [-180, -85.0511]], "files": ["ground-light.png", "ground-dark.png"]},
        "east_asia": {"size_px": [W, H], "bounds": bounds, "files": ["ground-ea-light.png", "ground-ea-dark.png"]},
    }
    json.dump(meta, open(os.path.join(ROOT, "ui", "basemap", "ground.json"), "w"), indent=1, ensure_ascii=False)
    log("ui/basemap/ground.json written")


if __name__ == "__main__":
    main()
