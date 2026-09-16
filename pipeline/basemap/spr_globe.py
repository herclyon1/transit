#!/usr/bin/env python3
"""Globe ground rasters (Apple z < 4.6) from Apple's own SPR tiles, decoded by Apple's decoder — no sampling.

    python3 pipeline/basemap/spr_globe.py [--dump tiles.db]      # run from the repo root

Inputs (pipeline/basemap/raw/spr/, written by pipeline/basemap/spr_dump.m from a copy of the geod tile cache):
    <z>-<x>-<y>.json          material-raster record: per-pixel value -> stack of DaVinci material ids (chapter 155)
    <z>-<x>-<y>-mat0.pgm      the 1024^2 material index raster (the shader's styleIndexTexture)
    <z>-<x>-<y>-attr153.pgm   ClimateTemperature codes 0..6 (Arctic .. VeryHot), 128^2   (chapter 154, attribute 153)
    <z>-<x>-<y>-attr154.pgm   ClimatePrecipitation codes 0..5 (VeryWet .. VeryDry), 128^2 (chapter 154, attribute 154)
    <z>-<x>-<y>-verts.f32 / -idx.u16 / -meshes.bin   the DaVinci terrain mesh (chapter 100): float3 (x, y up, z) in
                              tile units, z = height / tile width in Mercator metres (RENDER-PIPELINE 2.5)
    basemap/data/globe/spr-materials.json            material id -> Landcover class (from the captured z2 palettes)
    ~/Money/styl-work/default-56689.styl             Landcover-<Class>-Elevated-{Light,Dark}-Base fillColor bands
    basemap/data/shader/shader-numbers.json          groundSettings HSV climate deltas, light(0,0,1)
Outputs (map/data/, ui/basemap/ground-globe.json):
    ground-globe-{light,dark}.png      world 4096^2 Web-Mercator albedo x light(0,0,1), alpha 0 = water / no Apple tile
    ground-globe-ea-{light,dark}.png   lon 90..180, lat 0..66.51 at the z3 tiles' own 1024 px / 45 deg (2048^2)
    spr-class-globe.png                world 4096^2 8-bit class raster (index into the class list of the JSON, 255 = none)
    climate-temp-globe.png / climate-arid-globe.png   world 1024^2 codes as stored (255 = no tile)
    height-globe.png / height-globe-ea.png            terrarium RGB (h = R*256 + G + B/256 - 32768 m), 2048^2 / 1024^2
Per pixel (SHADER-NUMBERS 3.2 / 4.4): albedo_lin = HSV-tint(linearise(sheet colour of the stack's class at APPLE_ZOOM),
cells by temperature / aridity codes), out = sRGB(albedo_lin * light(0,0,1)); the UI's post-pass lights the relief.
"""
import glob
import json
import math
import os
import struct
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ground  # noqa: E402  (colour maths, sheet colours, climate cells — the same code as the z5-8 rasters)

ROOT = ground.ROOT
RAW = os.path.join(HERE, "raw", "spr")
OUT = ground.OUT
MATERIALS = os.path.join(ROOT, "basemap", "data", "globe", "spr-materials.json")
APPLE_ZOOM = 3.0            # the globe is drawn from Apple z2-4 tiles; the sheet band at z3 is the middle of it
N_WORLD = 4096              # = 4 z2 tiles x 1024 px (z3 tiles downsampled 2x into the same canvas)
EA = {"x": (6, 8), "y": (2, 4)}   # z3 tiles x6-7, y2-3: lon 90..180, lat 0..66.51
TILE_SIZE_M = {2: 10018754.17, 3: 5009377.09, 4: 2504688.54}   # 40075016.69 / 2^z (the tiles' own tileSizeInMeters)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_tile(path_json):
    d = json.load(open(path_json))
    z, x, y = d["z"], d["x"], d["y"]
    base = path_json[:-5]
    m = d["material_rasters"][0]
    ids, a, b = m["ids"], m["a"], m["b"]
    stacks, p = [], 0
    for n in b:
        stacks.append([ids[i] for i in a[p:p + n]]); p += n
    t = {"z": z, "x": x, "y": y, "stacks": stacks,
         "mat": np.asarray(Image.open(base + "-mat0.pgm")),
         "temp": np.asarray(Image.open(base + "-attr153.pgm")),
         "arid": np.asarray(Image.open(base + "-attr154.pgm"))}
    if os.path.exists(base + "-verts.f32"):
        t["verts"] = np.fromfile(base + "-verts.f32", np.float32).reshape(-1, 3)
    return t


def stack_class(stack, table):
    """Class of a material stack: the last material with a class (modifiers 264 / 310 carry none; [223] = Ground)."""
    cls = None
    for mid in stack:
        c = table.get(str(mid & 0xffff), {}).get("class")
        if c and c != "modifier":
            cls = c
    return cls or "Ground"


def class_raster(t, table, classes):
    lut = np.array([classes.index(stack_class(s, table)) for s in t["stacks"]] + [classes.index("Ground")] * (256 - len(t["stacks"])), np.uint8)
    return lut[t["mat"]]


def paint(cls_idx, temp, arid, sheet, adj, mode, light, classes, extra_lin):
    """cls_idx H x W class indices; temp / arid H x W codes (0..6 / 0..5, 255 = none)."""
    H, W = cls_idx.shape
    T = 1 + (temp.astype(float) - 3) / 3.0                        # cell coordinate 0..2 (SHADER-NUMBERS 3.2)
    A = np.where(arid < 3, 1 + (arid.astype(float) - 3) / 3.0, 1 + (arid.astype(float) - 3) / 2.0)
    T = np.clip(np.where(temp == 255, 1, T), 0, 2); A = np.clip(np.where(arid == 255, 1, A), 0, 2)
    out = np.zeros((H, W, 3))
    for i, cls in enumerate(classes):
        m = cls_idx == i
        if not m.any():
            continue
        if cls in extra_lin:                      # no sheet style: the captured palette row (linear) — spr-materials.json
            base = np.array(extra_lin[cls])
        else:
            b = ground.band_at(sheet[cls][mode], APPLE_ZOOM)
            base = ground.srgb_to_lin(b["rgb"])
        cells = ground.cells_for(base, adj, cls in ground.UNTINTED)
        out[m] = ground.sample_cells(cells, T[m], A[m])
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = ground.lin_to_srgb8(out * light)
    rgba[..., 3] = 255
    return rgba


def height_grid(t, n):
    """Rasterise the tile's mesh to an n x n height grid (metres): z * tileWidth * cos(lat) (Mercator z -> metres)."""
    from scipy.interpolate import griddata
    v = t["verts"]
    z = t["z"]; ts = TILE_SIZE_M[z]
    gx, gy = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n)   # gy: row 0 = top of the tile
    pts = np.stack([v[:, 0], 1 - v[:, 1]], -1)                                  # mesh y is up; raster rows go down
    h = griddata(pts, v[:, 2] * ts, (gx, gy), method="linear", fill_value=0.0)
    # Mercator scale: latitude of each row
    fy = (t["y"] + gy) / (2 ** z)
    lat = np.radians(np.array([ground.lat_of(f) for f in fy[:, 0]]))[:, None]
    return h * np.cos(lat)


def terrarium(h):
    v = np.clip(h + 32768.0, 0, 65535.99)
    r = np.floor(v / 256); g = np.floor(v - r * 256); b = np.floor((v - np.floor(v)) * 256)
    return np.stack([r, g, b], -1).astype(np.uint8)


def main():
    if "--dump" in sys.argv:
        db = sys.argv[sys.argv.index("--dump") + 1]
        exe = os.path.join(HERE, "raw", "spr_dump")
        os.makedirs(RAW, exist_ok=True)
        subprocess.check_call(["clang", "-fobjc-arc", "-framework", "Foundation", "-lsqlite3", "-o", exe, os.path.join(HERE, "spr_dump.m")])
        subprocess.check_call([exe, db, RAW, "4"], env=dict(os.environ, SPR_MESHRAW="1"))
    table = json.load(open(MATERIALS))
    classes = table["classes"]
    extra_lin = {c: v for c, v in table.get("class_colour_lin_captured", {}).items()}
    sheet = ground.sheet_colours()
    R = ground.Resolver(ground.STYL)
    for cls in classes:
        if cls not in sheet and cls not in extra_lin:
            for mode in ("Light", "Dark"):
                name = f"Landcover-{cls}-Elevated-{mode}-Base"
                bands = [{"zmin": a, "zmax": b, "rgb": v["rgba"][:3], "a": v["rgba"][3]} for a, b, v in R.bands(name, 1) if isinstance(v, dict) and "rgba" in v]
                if not bands:
                    raise SystemExit(f"{name}: not in the sheet")
                sheet.setdefault(cls, {})[mode.lower()] = bands
    sh = json.load(open(ground.SHADER))
    L = sh["lighting"]
    cube_z = sh["ambient_irradiance_cube"]["face_mean"][sh["ambient_irradiance_cube"]["faces_order"].index("+z")]
    light = L["ambientLightColor_linear"][0] * cube_z + L["lightColor_linear"][0] * L["tileLightDirection"][2]   # 1.0455, as ground.py
    adj = {"light": sh["climate_tinting"]["groundSettings.json"]["1-6"], "dark": sh["climate_tinting"]["groundSettingsNight.json"]["1-9"]}
    tiles = [load_tile(f) for f in sorted(glob.glob(os.path.join(RAW, "*.json"))) if os.path.basename(f)[0] in "23" and "-" in os.path.basename(f)]
    tiles = [t for t in tiles if t["z"] in (2, 3)]
    log(f"{len(tiles)} tiles (z2 {sum(t['z'] == 2 for t in tiles)}, z3 {sum(t['z'] == 3 for t in tiles)})")
    # world canvases at z2 resolution (1024 px per z2 tile); z3 tiles overwrite (downsampled 2x, nearest)
    cls_w = np.full((N_WORLD, N_WORLD), 255, np.uint8)
    temp_w = np.full((N_WORLD // 4, N_WORLD // 4), 255, np.uint8); arid_w = temp_w.copy()
    h_w = np.zeros((N_WORLD // 2, N_WORLD // 2), np.float32); h_has = np.zeros_like(h_w, bool)
    coverage = []
    for t in sorted(tiles, key=lambda t: t["z"]):            # z2 first, z3 on top
        z, x, y = t["z"], t["x"], t["y"]
        px = N_WORLD >> z                                       # pixels per tile on the world canvas
        ci = class_raster(t, table["materials"], classes)
        step = 1024 // px
        cls_w[y * px:(y + 1) * px, x * px:(x + 1) * px] = ci[::step, ::step]
        cp = px // 4                                            # climate canvas: 128 px per z3 tile, 256 per z2 tile
        def fit(r):
            return np.repeat(np.repeat(r, cp // 128, 0), cp // 128, 1) if cp >= 128 else r[::128 // cp, ::128 // cp]
        temp_w[y * cp:(y + 1) * cp, x * cp:(x + 1) * cp] = fit(t["temp"])
        arid_w[y * cp:(y + 1) * cp, x * cp:(x + 1) * cp] = fit(t["arid"])
        if "verts" in t:
            hp = px // 2
            h = height_grid(t, hp)
            h_w[y * hp:(y + 1) * hp, x * hp:(x + 1) * hp] = h; h_has[y * hp:(y + 1) * hp, x * hp:(x + 1) * hp] = True
        coverage.append(f"{z}/{x}/{y}")
    # climate codes upsampled to the class canvas (nearest; the shader samples them bilinearly on a 128^2 texture per tile)
    temp_big = np.repeat(np.repeat(temp_w, 4, 0), 4, 1); arid_big = np.repeat(np.repeat(arid_w, 4, 0), 4, 1)
    water = classes.index("Water")
    for mode in ("light", "dark"):
        rgba = paint(np.where(cls_w == 255, 0, cls_w), temp_big, arid_big, sheet, adj[mode], mode, light, classes, extra_lin)
        rgba[(cls_w == 255) | (cls_w == water), 3] = 0
        Image.fromarray(rgba).save(os.path.join(OUT, f"ground-globe-{mode}.png"), optimize=True)
        log(f"ground-globe-{mode}.png written")
    # East-Asia box at native z3 resolution
    ea_cls = np.full((2048, 2048), 255, np.uint8); ea_t = np.full((256, 256), 255, np.uint8); ea_a = ea_t.copy(); ea_h = np.zeros((1024, 1024), np.float32)
    for t in tiles:
        if t["z"] == 3 and EA["x"][0] <= t["x"] < EA["x"][1] and EA["y"][0] <= t["y"] < EA["y"][1]:
            ox, oy = (t["x"] - EA["x"][0]) * 1024, (t["y"] - EA["y"][0]) * 1024
            ea_cls[oy:oy + 1024, ox:ox + 1024] = class_raster(t, table["materials"], classes)
            ea_t[oy // 8:oy // 8 + 128, ox // 8:ox // 8 + 128] = t["temp"]; ea_a[oy // 8:oy // 8 + 128, ox // 8:ox // 8 + 128] = t["arid"]
            if "verts" in t:
                ea_h[oy // 2:oy // 2 + 512, ox // 2:ox // 2 + 512] = height_grid(t, 512)
    for mode in ("light", "dark"):
        rgba = paint(np.where(ea_cls == 255, 0, ea_cls), np.repeat(np.repeat(ea_t, 8, 0), 8, 1), np.repeat(np.repeat(ea_a, 8, 0), 8, 1), sheet, adj[mode], mode, light, classes, extra_lin)
        rgba[(ea_cls == 255) | (ea_cls == water), 3] = 0
        Image.fromarray(rgba).save(os.path.join(OUT, f"ground-globe-ea-{mode}.png"), optimize=True)
    # class + climate + height rasters
    Image.fromarray(cls_w).save(os.path.join(OUT, "spr-class-globe.png"), optimize=True)   # 8-bit grey = class index
    Image.fromarray(temp_w).save(os.path.join(OUT, "climate-temp-globe.png"), optimize=True)
    Image.fromarray(arid_w).save(os.path.join(OUT, "climate-arid-globe.png"), optimize=True)
    Image.fromarray(terrarium(h_w)).save(os.path.join(OUT, "height-globe.png"), optimize=True)
    Image.fromarray(terrarium(ea_h)).save(os.path.join(OUT, "height-globe-ea.png"), optimize=True)
    meta = {
        "what": "globe ground rasters from Apple's SPR tiles (VECTOR_SPR_MERCATOR z2-3) decoded with GeoServices' GEOVectorTile; see RENDER-PIPELINE 2.4-2.5",
        "generator": "pipeline/basemap/spr_globe.py <- pipeline/basemap/spr_dump.m <- ~/Library/.../com.apple.geod/.../MapTiles.sqlitedb (copy)",
        "world": {"crs": "EPSG:3857 whole world", "size": N_WORLD, "coordinates": [[-180, 85.0511], [180, 85.0511], [180, -85.0511], [-180, -85.0511]],
                  "files": ["ground-globe-light.png", "ground-globe-dark.png", "spr-class-globe.png", "climate-temp-globe.png (1024)", "climate-arid-globe.png (1024)", "height-globe.png (2048, terrarium)"]},
        "east_asia": {"lng": [90, 180], "lat": [0, 66.51326], "size": 2048, "coordinates": [[90, 66.51326], [180, 66.51326], [180, 0], [90, 0]],
                      "files": ["ground-globe-ea-light.png", "ground-globe-ea-dark.png", "height-globe-ea.png (1024, terrarium)"]},
        "apple_zoom_of_sheet_colours": APPLE_ZOOM, "light_flat": light,
        "classes": classes, "class_index_255": "no Apple tile in the cache copy (alpha 0 in the albedo rasters)",
        "coverage_tiles": coverage,
        "climate": {"temp_codes": "0 Arctic 1 VeryCold 2 Cold 3 Cool 4 Warm 5 Hot 6 VeryHot (VectorKit gss enum strings); cell = 1 + (T-3)/3",
                    "arid_codes": "0 VeryWet 1 Wet 2 Moist 3 SemiDry 4 Dry 5 VeryDry; cell = 1 + (A-3)/3 for A<3, 1 + (A-3)/2 for A>=3 (SHADER-NUMBERS 3.2)",
                    "hsv_deltas": adj},
        "height": {"source": "DaVinci terrain mesh (chapter 100) vertex z x tileSizeInMeters x cos(lat); vertex spacing ~25 km at z3, ~50 km at z2",
                   "exaggeration_by_apple_zoom": sh["climate_tinting"]["groundSettings.json"],
                   "note": "z1-4 groundElevationScale 14 / 9 / 7 / 5 is what makes the App's z3 globe look mountainous (RENDER-PIPELINE 2.5)"},
    }
    json.dump(meta, open(os.path.join(ROOT, "ui", "basemap", "ground-globe.json"), "w"), indent=1, ensure_ascii=False)
    log("done")


if __name__ == "__main__":
    main()
