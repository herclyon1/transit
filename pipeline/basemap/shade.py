#!/usr/bin/env python3
"""Terrain light factor for the flat map's z5-8 band, computed the way the App lights its ground mesh
(SHADER-NUMBERS 3.1 / 4.1, RENDER-PIPELINE 2.5): public DEM in, the App's formula and numbers, no sampling.

    python3 pipeline/basemap/shade.py                 # run from the repo root (downloads AWS terrarium z7 tiles on first run)

    n(x, y)  = normalize(-s * dh/dx, -s * dh/dy, 1)        s = groundElevationScale(Apple z): z5 3.25, z6 2.5, z7 1.5, z8 1.4
    light(n) = ambient * cube(n) + lightColor * max(n . L, 0)     ambient 0.49683, lightColor 0.7085, L = (-0.366, -0.211, 0.906)
    factor   = light(n) / light(0, 0, 1)                            (= 1 on flat ground; the UI multiplies linear albedo by it)
No extra smoothing (MESH_KM 0): the 1 km z7 DEM already gives less relief than the App (ui/basemap/shade.json check_japan_view).
Outputs: map/data/shade-ea-z{5,6,7}.png  (8-bit grey, factor = v / 128; East-Asia box lat 0-60 / lng 90-160 at AWS z7,
6400 x 6912 downsampled 2x -> 3200 x 3456 like ground-ea), ui/basemap/shade.json (bounds, formula, numbers, checks).
"""
import io
import json
import math
import os
import sys
import time
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(HERE, "raw", "terrarium")
OUT = os.path.join(ROOT, "map", "data")
SHADER = os.path.join(ROOT, "basemap", "data", "shader", "shader-numbers.json")
BOX = {"lat": (0.0, 60.0), "lng": (90.0, 160.0)}
Z = 7
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SCALES = {5: 3.25, 6: 2.5, 7: 1.5, 8: 1.4}
MESH_KM = {5: 0, 6: 0, 7: 0, 8: 0}       # no extra smoothing: the 1 km z7 DEM is closer to the App (see ui/basemap/shade.json checks)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def merc_y(lat):
    return (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2


def lat_of(fy):
    return math.degrees(2 * math.atan(math.exp((0.5 - fy) * 2 * math.pi)) - math.pi / 2)


def fetch(z, x, y):
    p = os.path.join(RAW, f"{z}-{x}-{y}.png")
    if not os.path.exists(p):
        os.makedirs(RAW, exist_ok=True)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=60) as r:
                    open(p, "wb").write(r.read())
                break
            except Exception as e:
                log(f"  {z}/{x}/{y}: {e}"); time.sleep(2)
    im = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
    return im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768


def dem():
    n = 2 ** Z
    x0 = int((BOX["lng"][0] + 180) / 360 * n); x1 = int(math.ceil((BOX["lng"][1] + 180) / 360 * n))
    y0 = int(merc_y(BOX["lat"][1]) * n); y1 = int(math.ceil(merc_y(BOX["lat"][0]) * n))
    H = np.zeros(((y1 - y0) * 256, (x1 - x0) * 256), np.float32)
    for ty in range(y0, y1):
        for tx in range(x0, x1):
            H[(ty - y0) * 256:(ty - y0 + 1) * 256, (tx - x0) * 256:(tx - x0 + 1) * 256] = fetch(Z, tx, ty)
        log(f"  row {ty - y0 + 1}/{y1 - y0}")
    bounds = {"lng": [x0 / n * 360 - 180, x1 / n * 360 - 180], "lat": [lat_of(y1 / n), lat_of(y0 / n)]}
    return H, bounds, (x0, y0)


def cube_sampler(sn):
    c = sn["ambient_irradiance_cube"]
    mean = dict(zip(c["faces_order"], c["face_mean"]))
    def cube(n):
        # the cube is 8x8 per face and nearly flat (face means 0.81-0.88, texels within 2 %): use the face mean of the
        # dominant axis; ground normals stay within ~30 deg of +z, so this is the +z face except on the steepest slopes
        ax = np.argmax(np.abs(n), axis=-1)
        sign = np.take_along_axis(n, ax[..., None], -1)[..., 0] >= 0
        out = np.empty(n.shape[:-1], np.float32)
        for i, axis in enumerate("xyz"):
            out[(ax == i) & sign] = mean["+" + axis]
            out[(ax == i) & ~sign] = mean["-" + axis]
        return out
    return cube


def light_factor(H, lat_rows, s, mesh_km, sn):
    L = np.array(sn["lighting"]["tileLightDirection"], np.float32)
    amb = sn["lighting"]["ambientLightColor_linear"][0]; lc = sn["lighting"]["lightColor_linear"][0]
    cube = cube_sampler(sn)
    # metres per pixel (z7: 40075 km / 2^7 / 256 at the equator, x cos(lat))
    mpp_eq = 40075016.69 / (2 ** Z) / 256
    coslat = np.cos(np.radians(lat_rows))[:, None]
    # smooth to the mesh spacing: box of (mesh_km * 1000 / (mpp_eq * cos lat)) px, using a separable uniform filter
    from scipy.ndimage import uniform_filter
    k = max(1, int(round(mesh_km * 1000 / mpp_eq / max(float(coslat.mean()), 0.3))))
    Hs = uniform_filter(H, size=k, mode="nearest") if k > 1 else H
    dy, dx = np.gradient(Hs)
    gx = dx / (mpp_eq * coslat); gy = -dy / (mpp_eq * coslat)      # y up (north) for the App's tile space
    n = np.stack([-s * gx, -s * gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lit = amb * cube(n) + lc * np.clip(n @ L, 0, None)
    flat = amb * cube(np.array([[[0, 0, 1.0]]], np.float32))[0, 0] + lc * L[2]
    return lit / flat, k


def main():
    sn = json.load(open(SHADER))
    H, bounds, origin = dem()
    log(f"DEM {H.shape}, bounds {bounds}")
    n = 2 ** Z
    lat_rows = np.array([lat_of((origin[1] * 256 + i + 0.5) / (n * 256)) for i in range(H.shape[0])])
    meta = {"what": "terrain light factor light(n)/light(0,0,1) for the flat map (RENDER-PIPELINE 2.5 / 7.4), from the AWS terrarium DEM with the App's formula",
            "bounds": bounds, "coordinates": [[bounds["lng"][0], bounds["lat"][1]], [bounds["lng"][1], bounds["lat"][1]], [bounds["lng"][1], bounds["lat"][0]], [bounds["lng"][0], bounds["lat"][0]]],
            "encoding": "8-bit grey, factor = value / 128 (1.0 = flat ground); multiply the linear albedo by it, then sRGB-encode",
            "formula": "n = normalize(-s dh/dx, -s dh/dy, 1); light = 0.49683 cube(n) + 0.7085 max(n.L, 0); L = (-0.366, -0.211, 0.906) view-fixed (azimuth 240 deg, altitude 65 deg)",
            "files": {}, "stats": {}}
    for z, s in SCALES.items():
        if z == 8:
            continue
        f, k = light_factor(H, lat_rows, s, MESH_KM[z], sn)
        small = f[::2, ::2]
        img = np.clip(np.round(small * 128), 0, 255).astype(np.uint8)
        name = f"shade-ea-z{z}.png"
        Image.fromarray(img).save(os.path.join(OUT, name), optimize=True)
        meta["files"][name] = {"apple_zoom": z, "groundElevationScale": s, "dem_smoothing_px_at_z7": k, "size": list(img.shape[::-1])}
        meta["stats"][name] = {"p1": round(float(np.percentile(f, 1)), 3), "p5": round(float(np.percentile(f, 5)), 3), "p50": round(float(np.percentile(f, 50)), 3),
                               "p95": round(float(np.percentile(f, 95)), 3), "p99": round(float(np.percentile(f, 99)), 3), "min": round(float(f.min()), 3), "max": round(float(f.max()), 3)}
        log(name, meta["stats"][name])
    meta["check_japan_view"] = {
        "app": "snap-japan.png (Apple z6.x), forest-coloured pixels of the Japanese Alps box x 560-700 y 330-430 (1280x744): luma p5 181 / p50 204 / p95 216 = linear 0.73 / 0.95 / 1.08 of the flat Forest colour (176,222,144) x light = luma 210",
        "formula_1km_s2.5": "Alps box lon 136.5-139.5 lat 35-37 on the z7 DEM: p5 0.83 / p50 1.00 / p95 1.05 (3 km smoothing: 0.90 / 1.00 / 1.04)",
        "reading": "the App darkens its slopes about twice as deep as n.L with s = 2.5 on a 1 km DEM; the extra is not in the formula decoded so far — candidates: the ground shadow map (DaVinci::groundShadowMap_* in the metallib, shadow x direct term, RENDER-PIPELINE 2.5) and normalsSharpnessBias 0.93 (semantics unknown). A tilt exaggeration of 2 on the 1 km slopes reproduces p5 0.67 / p50 0.98 / p95 1.05"}
    json.dump(meta, open(os.path.join(ROOT, "ui", "basemap", "shade.json"), "w"), indent=1)
    log("done")


if __name__ == "__main__":
    main()
