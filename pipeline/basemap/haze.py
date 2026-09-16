#!/usr/bin/env python3
"""Limb haze (atmosphere seen through, inside the disc) as an overlay colour + opacity per radius.

The App screenshot ~/Money/styl-work/native-limb-land-light.png (maps://?ll=30,60&spn=50,60,
sidebar closed) has land (North China) and sea (South China Sea) on the same limb, so at each
radial bin the observed colour P over a known base B (the globe palette centre colours for the
pixel's NE depth band / Koppen tint) lets a shared overlay be solved:
    P - B = a*H - a*B   ->  least squares in (K = a*H, a) over all pixels of the bin
giving the haze colour H and opacity a per r/limb bin. Written to ui/basemap/haze-globe.json;
globe-data.py copies it into map/data/meta.json and drawLimb() paints it.

    python3 pipeline/basemap/haze.py
"""
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
from importlib import import_module  # noqa: E402
gd = import_module("globe-data")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "pipeline", "basemap", "raw")
PNG = os.path.expanduser("~/Money/styl-work/native-limb-land-light.png")
EDGES = [0.50, 0.60, 0.70, 0.78, 0.84, 0.88, 0.91, 0.94, 0.96, 0.975, 0.985, 0.995, 1.0]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def main():
    img = np.asarray(Image.open(PNG).convert("RGB"))
    H, W = img.shape[:2]
    params, anchors, res, (lcx, lcy, lr, ln, lrms) = G.fit_camera(img, ll_hint=(30.18, 51.15))
    lat0, lng0, cx, cy, f, D = params
    limb_r = f / math.sqrt(D * D - 1)
    gp = json.load(open(os.path.join(ROOT, "ui", "basemap", "palette-globe.json")))
    band_col = {b["depth_min_m"]: np.array((b.get("centre") or b)["rgb"], float) for b in gp["ocean_bands"]}
    tint_col = {t: np.array((v.get("centre") or v)["rgb"], float) for t, v in gp["land_tints"].items()}
    shelf = json.load(open(os.path.join(ROOT, "ui", "basemap", "palette-shelf.json")))
    shelf_ramp_x = shelf["raster"]["ramp_depth_m"]; shelf_ramp_c = np.array(shelf["raster"]["ramp_rgb"], float)
    layers, _ = P.ne_layers()
    kg = np.asarray(Image.open(os.path.join(RAW, "koppen", "1991_2020", "koppen_geiger_0p1.tif")))
    step = 3
    gx, gy = np.meshgrid(np.arange(4, W - 4, step), np.arange(4, H - 4, step))
    glat, glng = G.unproject(params, gx.astype(float), gy.astype(float))
    rr = np.hypot(gx - cx, gy - cy) / limb_r
    rows = []   # (r, P rgb, B rgb, kind)
    for yi in range(gx.shape[0]):
        for xi in range(gx.shape[1]):
            la, lo = glat[yi, xi], glng[yi, xi]
            r = rr[yi, xi]
            if not np.isfinite(la) or r < EDGES[0] or r > 1.0:
                continue
            x0, y0 = int(gx[yi, xi]), int(gy[yi, xi])
            if x0 > 2440 or (x0 > 2400 and y0 < 520):    # toolbar / window edge
                continue
            w = img[y0 - 1:y0 + 2, x0 - 1:x0 + 2].reshape(-1, 3).astype(int)
            if (w.max(0) - w.min(0)).max() > 24:
                continue
            cls = P.ne_depth_class(layers, la, lo)
            if cls is None:
                i = int((lo + 180) / 0.1); j = int((90 - la) / 0.1)
                k = int(kg[min(max(j, 0), kg.shape[0] - 1), min(max(i, 0), kg.shape[1] - 1)])
                if k == 0:
                    continue
                tint = gd.KOPPEN_TINT.get(k, gd.DEFAULT_TINT)
                if tint not in tint_col:
                    continue
                B, kind = tint_col[tint], "land"
            else:
                if cls == 0:
                    ele, _, _, _ = P.elevation_and_slope(la, lo, z=6)
                    if ele >= 0 or ele < -200:
                        B = band_col[0]
                    else:
                        B = np.stack([np.interp(-ele, shelf_ramp_x, shelf_ramp_c[:, k]) for k in range(3)])
                else:
                    B = band_col.get(cls, band_col[max(band_col)])
                kind = "ocean"
            rows.append((float(r), np.median(w, 0).astype(float), B, kind))
    log("samples", len(rows), "land", sum(1 for r in rows if r[3] == "land"), "ocean", sum(1 for r in rows if r[3] == "ocean"))
    bins = []
    for lo_, hi_ in zip(EDGES[:-1], EDGES[1:]):
        sel = [r for r in rows if lo_ <= r[0] < hi_]
        nl = sum(1 for r in sel if r[3] == "land"); no = len(sel) - nl
        if len(sel) < 20:
            continue
        Pm = np.array([r[1] for r in sel]); Bm = np.array([r[2] for r in sel])
        # (P - B) = K - a*B, unknowns K (3) and a: rows per pixel per channel
        A = np.zeros((len(sel) * 3, 4)); y = np.zeros(len(sel) * 3)
        for i in range(len(sel)):
            for c in range(3):
                A[3 * i + c, c] = 1.0; A[3 * i + c, 3] = -Bm[i, c]; y[3 * i + c] = Pm[i, c] - Bm[i, c]
        sol, *_ = np.linalg.lstsq(A, y, rcond=None)
        a = float(np.clip(sol[3], 0, 1)); Hc = (sol[:3] / a) if a > 0.02 else np.array([np.nan] * 3)
        pred = Bm * (1 - a) + a * Hc if a > 0.02 else Bm
        rms = float(np.sqrt(((Pm - pred) ** 2).sum(1).mean()))
        bins.append({"r_min": lo_, "r_max": hi_, "n": len(sel), "n_land": nl, "n_ocean": no, "alpha": round(a, 3),
                     "haze_rgb": [int(round(v)) for v in Hc] if a > 0.02 else None, "rms_residual": round(rms, 1),
                     "observed_mean_land": [int(v) for v in Pm[[r[3] == "land" for r in sel]].mean(0)] if nl else None,
                     "observed_mean_ocean": [int(v) for v in Pm[[r[3] == "ocean" for r in sel]].mean(0)] if no else None})
        log(f"  r {lo_:.3f}-{hi_:.3f} n={len(sel):5d} (land {nl}, ocean {no}) a={a:.3f} H={bins[-1]['haze_rgb']} rms {rms:.1f}")
    doc = {
        "what": "Apple Maps globe: inner limb haze as overlay colour H and opacity a per r/limb bin, solved from land and sea pixels on the same limb",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "pipeline/basemap/haze.py",
        "source_image": {"file": PNG, "size_px": [W, H], "scale": 2, "view": "maps://?ll=30,60&spn=50,60, sidebar closed, 1280x744 pt"},
        "camera": {"lat0": round(lat0, 3), "lng0": round(lng0, 3), "D_earth_radii": round(D, 4), "limb_radius_px": round(limb_r, 1),
                   "anchors": len(anchors), "rms_px": round(float(math.sqrt((res ** 2).mean())), 2)},
        "base_colours": "palette-globe.json centre colours per NE depth band / Koppen tint; 0-200 m via palette-shelf ramp",
        "model": "P = (1-a) B + a H per bin, least squares in (aH, a) over all pixels (3 channels each)",
        "bins": bins,
    }
    out = os.path.join(ROOT, "ui", "basemap", "haze-globe.json")
    json.dump(doc, open(out, "w"), indent=1, ensure_ascii=False)
    log("wrote", out)


if __name__ == "__main__":
    main()
