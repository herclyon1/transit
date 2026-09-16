#!/usr/bin/env python3
"""Shelf-sea colour ramp (0-200 m) from the Maps App globe screenshot, and the raster that paints it.

Natural Earth's shallowest level is one 0-200 m band, but the App grades the shelf by
depth (the Yellow Sea is almost white, the outer shelf blue). Method:
  1. camera for ~/Money/styl-work/native-nosidebar.png (globefit.fit_camera)
  2. every disc pixel that Natural Earth classes as 0-200 m gets its ETOPO1 depth from the
     AWS terrarium tiles (z6), 5x5-uniform windows only, r/limb <= 0.82
  3. median colour per depth bin -> ui/basemap/palette-shelf.json (with n / residual)
  4. map/data/shelf-globe.png: Web-Mercator 4096^2 RGBA, pixels with -200 m < depth < 0
     coloured by piecewise-linear interpolation of the bins, everything else transparent
     (the page draws it above the 0-200 m fill and below the deeper fills and land)

    python3 pipeline/basemap/shelf.py            # run from the repo root; ~1000 terrarium z5 tiles cached in raw/
"""
import concurrent.futures as cf
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv, _argv = [sys.argv[0]], sys.argv
import globefit as G  # noqa: E402
import palette as P  # noqa: E402
sys.argv = _argv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "pipeline", "basemap", "raw")
PNG = os.path.expanduser("~/Money/styl-work/native-nosidebar.png")
BINS = [0, 10, 25, 50, 75, 100, 150, 200]       # metres below sea level
RASTER_Z = 5                                    # 32x32 tiles, 8192 px world -> 4096 Mercator output


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def stats(rows):
    arr = np.array(rows, float)
    med = np.median(arr, 0); dev = np.sqrt(((arr - med) ** 2).sum(1))
    return {"rgb": [int(round(v)) for v in med], "hex": "#%02x%02x%02x" % tuple(int(round(v)) for v in med), "n": len(rows),
            "rms_residual": round(float(np.sqrt((dev ** 2).mean())), 1)}


def sample_shelf():
    img = np.asarray(Image.open(PNG).convert("RGB"))
    H, W = img.shape[:2]
    params, anchors, res, (lcx, lcy, lr, ln, lrms) = G.fit_camera(img, ll_hint=(30.18, 124.5))
    lat0, lng0, cx, cy, f, D = params
    limb_r = f / math.sqrt(D * D - 1)
    layers, ne_version = P.ne_layers()
    step = 4
    gx, gy = np.meshgrid(np.arange(4, W - 4, step), np.arange(4, H - 4, step))
    glat, glng = G.unproject(params, gx.astype(float), gy.astype(float))
    rr = np.hypot(gx - cx, gy - cy) / limb_r
    rows = []
    for yi in range(gx.shape[0]):
        for xi in range(gx.shape[1]):
            la, lo = glat[yi, xi], glng[yi, xi]
            if not np.isfinite(la) or rr[yi, xi] > 0.82:
                continue
            x0, y0 = int(gx[yi, xi]), int(gy[yi, xi])
            if P.ne_depth_class(layers, la, lo) != 0:
                continue
            w = img[y0 - 2:y0 + 3, x0 - 2:x0 + 3].reshape(-1, 3).astype(int)
            if (w.max(0) - w.min(0)).max() > 18:
                continue
            ele, _, _, _ = P.elevation_and_slope(la, lo, z=6)
            if ele >= 0 or ele < -200:
                continue
            rows.append({"px": [x0, y0], "lat": round(float(la), 3), "lng": round(float(lo), 3),
                         "depth_m": round(float(-ele), 1), "rgb": [int(v) for v in np.median(w, 0)], "r_over_limb": round(float(rr[yi, xi]), 3)})
    bins = []
    for lo_, hi_ in zip(BINS[:-1], BINS[1:]):
        sel = [r for r in rows if lo_ <= r["depth_m"] < hi_]
        if len(sel) >= 8:
            bins.append(dict(depth_min_m=lo_, depth_max_m=hi_, **stats([r["rgb"] for r in sel]),
                             centre=stats([r["rgb"] for r in sel if r["r_over_limb"] <= 0.6]) if sum(r["r_over_limb"] <= 0.6 for r in sel) >= 8 else None))
    doc = {
        "what": "Apple Maps GLOBE style: shelf-sea (0-200 m) colour by depth, sampled from the App screenshot through the fitted camera",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "pipeline/basemap/shelf.py",
        "source_image": {"file": PNG, "size_px": [W, H], "scale": 2, "view": "maps://?ll=30,125&spn=50,60, sidebar closed, 1280x744 pt"},
        "camera": {"lat0": round(lat0, 4), "lng0": round(lng0, 4), "D_earth_radii": round(D, 4), "f_px": round(f, 1), "cx_px": round(cx, 1), "cy_px": round(cy, 1),
                   "limb_radius_px": round(limb_r, 1), "anchors": anchors, "rms_px": round(float(math.sqrt((res ** 2).mean())), 2)},
        "depth_source": {"name": "AWS Terrain Tiles terrarium z6 (ocean = ETOPO1)", "url": P.TERR_URL},
        "class_source": f"Natural Earth 10m bathymetry v{ne_version} level 0 (0-200 m) selects the pixels",
        "sampling": {"grid_px": step, "window_px": 5, "reject_if_channel_range_gt": 18, "max_r_over_limb": 0.82},
        "bins": bins,
        "samples": rows[::max(1, len(rows) // 400)],
    }
    return doc


def ramp(bins):
    """Piecewise-linear RGB(depth) through the bin centres (centre stats when present)."""
    xs = [(b["depth_min_m"] + b["depth_max_m"]) / 2 for b in bins]
    cs = np.array([(b["centre"] or b)["rgb"] for b in bins], float)
    def f(d):
        d = np.clip(d, xs[0], xs[-1])
        return np.stack([np.interp(d, xs, cs[:, k]) for k in range(3)], -1)
    return f, xs, cs


def build_raster(bins, out_png):
    N = 4096
    n = 2 ** RASTER_Z
    f, xs, cs = ramp(bins)
    rgba = np.zeros((N, N, 4), dtype=np.uint8)
    tiles = [(x, y) for x in range(n) for y in range(n)]
    def fetch(t):
        return t, P.terrarium_tile(RASTER_Z, t[0], t[1])
    done = 0
    with cf.ThreadPoolExecutor(16) as ex:
        for (tx, ty), ele in ex.map(fetch, tiles):
            # 256x256 tile -> 128x128 output block (2x2 mean), Mercator tile grid == Mercator output grid
            e = ele.reshape(128, 2, 128, 2).mean((1, 3))
            m = (e < 0) & (e > -200)
            if m.any():
                col = f(-e[m])
                blk = rgba[ty * 128:(ty + 1) * 128, tx * 128:(tx + 1) * 128]
                blk[m, 0] = col[:, 0]; blk[m, 1] = col[:, 1]; blk[m, 2] = col[:, 2]; blk[m, 3] = 255
            done += 1
            if done % 128 == 0:
                log(f"  tiles {done}/{len(tiles)}")
    Image.fromarray(rgba, "RGBA").save(out_png, optimize=True)
    log("wrote", out_png, os.path.getsize(out_png) / 1e6, "MB")
    return {"size_px": N, "terrarium_zoom": RASTER_Z, "bounds": [[-180, 85.0511], [180, 85.0511], [180, -85.0511], [-180, -85.0511]],
            "ramp_depth_m": xs, "ramp_rgb": cs.astype(int).tolist()}


def main():
    out_json = os.path.join(ROOT, "ui", "basemap", "palette-shelf.json")
    doc = sample_shelf()
    for b in doc["bins"]:
        log(f"  {b['depth_min_m']:>4}-{b['depth_max_m']:<4} n={b['n']:5d} {b['hex']} rms {b['rms_residual']}  centre {(b['centre'] or {}).get('hex')}")
    doc["raster"] = build_raster(doc["bins"], os.path.join(ROOT, "map", "data", "shelf-globe.png"))
    json.dump(doc, open(out_json, "w"), indent=1, ensure_ascii=False)
    log("wrote", out_json)


if __name__ == "__main__":
    main()
