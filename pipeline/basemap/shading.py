#!/usr/bin/env python3
"""Directional shading of the App's globe (brightness vs surface normal), fitted on the screenshot.

The deep-ocean colour is not constant over the disc: the east (right) side darkens toward the
limb, the west does not. That is a lit sphere: brightness = a + b * (n . L), n = surface normal
in camera space, L = light direction. Sampled on native-nosidebar.png through the fitted camera,
deep ocean only (NE bands >= 3000 m, uniform 5x5 windows), the G channel relative to the band's
centre colour:   G_obs / G_band = a + b*(nx Lx + ny Ly + nz Lz)   (linear least squares).
Writes ui/basemap/shading-globe.json: a, b, L (unit), fit r2, and the residual per r/limb bin.

    python3 pipeline/basemap/shading.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PNG = os.path.expanduser("~/Money/styl-work/native-nosidebar.png")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def main():
    img = np.asarray(Image.open(PNG).convert("RGB"))
    H, W = img.shape[:2]
    params, anchors, res, (lcx, lcy, lr, ln, lrms) = G.fit_camera(img, ll_hint=(30.18, 124.5))
    lat0, lng0, cx, cy, f, D = params
    limb_r = f / math.sqrt(D * D - 1)
    gp = json.load(open(os.path.join(ROOT, "ui", "basemap", "palette-globe.json")))
    band_col = {b["depth_min_m"]: np.array((b.get("centre") or b)["rgb"], float) for b in gp["ocean_bands"]}
    layers, _ = P.ne_layers()
    R = G.rot(lat0, lng0)
    step = 3
    gx, gy = np.meshgrid(np.arange(4, W - 4, step), np.arange(4, H - 4, step))
    glat, glng = G.unproject(params, gx.astype(float), gy.astype(float))
    rr = np.hypot(gx - cx, gy - cy) / limb_r
    X, y, meta_rows = [], [], []
    for yi in range(gx.shape[0]):
        for xi in range(gx.shape[1]):
            la, lo = glat[yi, xi], glng[yi, xi]
            r = rr[yi, xi]
            if not np.isfinite(la) or r > 0.9:
                continue
            x0, y0 = int(gx[yi, xi]), int(gy[yi, xi])
            if x0 > 2440 or (x0 > 2400 and y0 < 520):
                continue
            cls = P.ne_depth_class(layers, la, lo)
            if cls is None or cls < 3000 or cls not in band_col:
                continue
            w = img[y0 - 2:y0 + 3, x0 - 2:x0 + 3].reshape(-1, 3).astype(int)
            if (w.max(0) - w.min(0)).max() > 14:
                continue
            n = G.unit(la, lo) @ R.T                    # camera-frame normal: x right, y up, z toward camera
            X.append([1.0, n[0], n[1], n[2]])
            y.append(float(np.median(w, 0)[1]) / band_col[cls][1])
            meta_rows.append((r, x0, y0))
    X = np.array(X); y = np.array(y)
    sol, *_ = np.linalg.lstsq(X, y, rcond=None)
    a, bL = sol[0], sol[1:]
    b = float(np.linalg.norm(bL)); L = (bL / b).tolist()
    pred = X @ sol
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    # the band 'centre' colours were themselves sampled under this shading (n ~ (0,0,1) at the disc
    # centre): normalise so the factor is 1 at the centre normal
    centre_factor = a + b * L[2]
    log(f"n={len(y)} a={a:.4f} b={b:.4f} L={np.round(L, 3).tolist()} r2={r2:.3f} centre factor {centre_factor:.3f}")
    bins = {}
    for (r, x0, y0), o, p in zip(meta_rows, y, pred):
        k = f"{math.floor(r * 10) / 10:.1f}"
        bins.setdefault(k, []).append(o - p)
    az = math.degrees(math.atan2(L[0], L[1]))            # 0 = from top of screen, 90 = from the right
    el = math.degrees(math.asin(max(-1, min(1, L[2]))))
    doc = {
        "what": "Apple Maps globe: directional brightness over the disc (lit sphere), fitted on deep ocean of the App screenshot",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "pipeline/basemap/shading.py",
        "source_image": {"file": PNG, "view": "maps://?ll=30,125&spn=50,60, sidebar closed, 1280x744 pt @2x"},
        "camera": {"lat0": round(lat0, 3), "lng0": round(lng0, 3), "D_earth_radii": round(D, 4), "rms_px": round(float(math.sqrt((res ** 2).mean())), 2)},
        "model": "factor(n) = (a + b * n.L) / (a + b * Lz); n = surface normal in camera space (x right, y up, z toward camera); "
                 "the page multiplies the globe by factor(n) (black overlay with alpha 1 - factor)",
        "a": round(float(a), 4), "b": round(b, 4), "L": [round(v, 4) for v in L],
        "L_screen": {"azimuth_deg_from_top_clockwise": round(az, 1), "elevation_deg": round(el, 1)},
        "centre_factor": round(float(centre_factor), 4),
        "n_samples": int(len(y)), "r2": round(float(r2), 3),
        "residual_by_r_over_limb": {k: {"n": len(v), "mean": round(float(np.mean(v)), 4), "rms": round(float(np.sqrt(np.mean(np.square(v)))), 4)} for k, v in sorted(bins.items())},
        "bands_used": "NE >= 3000 m, G channel relative to palette-globe centre colour of the band",
    }
    out = os.path.join(ROOT, "ui", "basemap", "shading-globe.json")
    json.dump(doc, open(out, "w"), indent=1, ensure_ascii=False)
    log("wrote", out, json.dumps(doc["residual_by_r_over_limb"]))


if __name__ == "__main__":
    main()
