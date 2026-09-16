#!/usr/bin/env python3
"""Fit the Maps App globe camera on a screenshot and sample the globe palette.

The App's globe is its own style sheet (globe-default-*.styl) that MKMapSnapshotter
cannot render, so the only way to measure its colours is the App screenshot itself.
Pixel -> lat/lng needs the camera: a perspective view of a unit sphere,
    p = R(lat0, lng0) * unit(lat, lng);  x = cx + f * p.x / (D - p.z);  y = cy - f * p.y / (D - p.z)
with six unknowns (lat0, lng0, cx, cy, f, D). Anchors are the city markers (white
disc in a dark ring, ~7 px at 2x) matched to Natural Earth 10m populated places
(public domain); the fit is Gauss-Newton with a numerical Jacobian and RANSAC-style
re-matching. With the camera, every globe pixel gets a coordinate, and colours are
sampled by Natural Earth bathymetry level (ocean) and Koppen->tint class (land),
away from labels (5x5 window uniformity) and away from the limb haze.

    python3 pipeline/basemap/globefit.py ~/Money/styl-work/native.png ui/basemap/palette-globe.json
"""
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelib  # noqa: E402
sys.argv, _argv = [sys.argv[0]], sys.argv
import palette as P  # noqa: E402  (ne_layers, ne_depth_class, NE_LEVELS)
sys.argv = _argv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "pipeline", "basemap", "raw")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---- camera --------------------------------------------------------------------------------
def unit(lat, lng):
    la, lo = np.radians(lat), np.radians(lng)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


def rot(lat0, lng0):
    """Rotation taking unit(lat0, lng0) to +z (toward the camera), north to +y."""
    lo, la = math.radians(lng0), math.radians(lat0)
    Rz = np.array([[math.cos(-lo), -math.sin(-lo), 0], [math.sin(-lo), math.cos(-lo), 0], [0, 0, 1]])
    # after Rz the centre is at longitude 0: (cos la, 0, sin la); rotate about y to bring it to +z
    a = math.pi / 2 - la
    Ry = np.array([[math.cos(a), 0, -math.sin(a)], [0, 1, 0], [math.sin(a), 0, math.cos(a)]])
    # after Ry: x -> right (east), y -> north?  check: north pole (0,0,1) -> Ry -> (-sin a, 0, cos a): we want +y up,
    # so swap axes: camera x = east = y_world', camera y = north = -x_world'
    M = Ry @ Rz
    swap = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]])
    return swap @ M


def project(params, lat, lng):
    lat0, lng0, cx, cy, f, D = params
    p = unit(lat, lng) @ rot(lat0, lng0).T
    front = p[..., 2] > 1.0 / D           # visible hemisphere for a camera at distance D
    x = cx + f * p[..., 0] / (D - p[..., 2])
    y = cy - f * p[..., 1] / (D - p[..., 2])
    return x, y, front


def unproject(params, x, y):
    """Pixel -> (lat, lng) by ray/sphere intersection; NaN outside the disc."""
    lat0, lng0, cx, cy, f, D = params
    dx = (x - cx) / f; dy = -(y - cy) / f
    # ray from camera (0,0,D) with direction (dx, dy, -1); sphere |p|=1
    dirv = np.stack([dx, dy, -np.ones_like(dx)], -1)
    o = np.array([0, 0, D])
    b = 2 * (dirv @ o); c = D * D - 1; a = (dirv ** 2).sum(-1)
    disc = b * b - 4 * a * c
    t = (-b - np.sqrt(np.where(disc >= 0, disc, np.nan))) / (2 * a)
    p = o + dirv * t[..., None]
    w = p @ rot(lat0, lng0)              # inverse rotation
    lat = np.degrees(np.arcsin(np.clip(w[..., 2], -1, 1)))
    lng = np.degrees(np.arctan2(w[..., 1], w[..., 0]))
    return lat, lng


def limb_circle(img, glow_px=14):
    """The globe's silhouette: per row, the first non-black run scanning left from the space side,
    minus the measured 7 pt (14 px @2x) glow that sits outside the solid disc. Least-squares circle."""
    lum = img.astype(int).sum(2)
    H, W = lum.shape
    pts = []
    for y in range(40, H - 40, 8):
        row = lum[y, :2452]
        nz = np.nonzero(row > 6)[0]
        if len(nz) == 0:
            continue
        x = nz[-1]
        # reject stars: need 3 consecutive lit pixels at the boundary
        if x < 3 or not (row[x - 1] > 6 and row[x - 2] > 6):
            continue
        pts.append((x - glow_px, y))
    P_ = np.array(pts, float)
    # algebraic circle fit: x^2 + y^2 + a x + b y + c = 0
    A = np.column_stack([P_[:, 0], P_[:, 1], np.ones(len(P_))])
    b = -(P_[:, 0] ** 2 + P_[:, 1] ** 2)
    a, bb, c = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = -a / 2, -bb / 2
    r = math.sqrt(cx * cx + cy * cy - c)
    res = np.hypot(P_[:, 0] - cx, P_[:, 1] - cy) - r
    # one robust pass: drop points > 3 px off (toolbar edge, labels touching the limb)
    keep = np.abs(res) < 3
    if keep.sum() >= 10:
        A, b = A[keep], b[keep]
        a, bb, c = np.linalg.lstsq(A, b, rcond=None)[0]
        cx, cy = -a / 2, -bb / 2
        r = math.sqrt(cx * cx + cy * cy - c)
        res = np.hypot(P_[keep, 0] - cx, P_[keep, 1] - cy) - r
    return cx, cy, r, int(keep.sum()), float(np.sqrt((res ** 2).mean()))


def fit(params, lat, lng, px, py, limb=None, iters=40):
    """Gauss-Newton. With limb=(cx, cy, r) fixed, only lat0, lng0, D are free and f = r*sqrt(D^2-1)."""
    params = np.array(params, float)
    free = [0, 1, 5] if limb else [0, 1, 2, 3, 4, 5]

    def full(pr):
        q = pr.copy()
        if limb:
            q[2], q[3] = limb[0], limb[1]
            q[4] = limb[2] * math.sqrt(max(q[5] * q[5] - 1, 1e-6))
        return q
    for _ in range(iters):
        x, y, _ = project(full(params), lat, lng)
        r = np.concatenate([x - px, y - py])
        J = np.zeros((len(r), len(free)))
        for col, k in enumerate(free):
            h = 1e-4 * max(1.0, abs(params[k]))
            q = params.copy(); q[k] += h
            x2, y2, _ = project(full(q), lat, lng)
            J[:, col] = (np.concatenate([x2 - px, y2 - py]) - r) / h
        step = np.linalg.lstsq(J.T @ J + 1e-6 * np.eye(len(free)), -J.T @ r, rcond=None)[0]
        for col, k in enumerate(free):
            params[k] += step[col]
        params[5] = max(params[5], 1.05)
        if np.abs(step).max() < 1e-7:
            break
    params = full(params)
    x, y, _ = project(params, lat, lng)
    return params, np.hypot(x - px, y - py)


# ---- city markers ----------------------------------------------------------------------------
def detect_markers(img):
    """White disc (>= 3 px) inside a dark ring, isolated from text: Apple's globe city marker."""
    a = img.astype(int)
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    sat = a.max(2) - a.min(2)
    white = lum > 225
    dark = (lum < 140) & (sat < 60)
    H, W = lum.shape
    seen = np.zeros_like(white); out = []
    ys, xs = np.nonzero(white)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]; seen[y0, x0] = True; pts = []
        while stack and len(pts) <= 60:
            y, x = stack.pop(); pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and white[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; stack.append((ny, nx))
        if not (6 <= len(pts) <= 45):
            continue
        py = np.array([p[0] for p in pts]); px = np.array([p[1] for p in pts])
        h, w = py.max() - py.min() + 1, px.max() - px.min() + 1
        if h > 8 or w > 8 or h < 3 or w < 3 or abs(h - w) > 2:
            continue
        cy, cx = py.mean(), px.mean()
        # dark ring: the 1-2 px band around the white blob must be mostly dark
        y0b, y1b, x0b, x1b = int(py.min()) - 2, int(py.max()) + 3, int(px.min()) - 2, int(px.max()) + 3
        if y0b < 0 or x0b < 0 or y1b > H or x1b > W:
            continue
        band = dark[y0b:y1b, x0b:x1b].copy()
        band[2:-2, 2:-2] = False
        ring_frac = band.sum() / (band.size - (y1b - y0b - 4) * (x1b - x0b - 4))
        if ring_frac < 0.6:
            continue
        # isolation: no dark pixels 2..6 px left or right of the ring (letters sit 2-4 px apart; the marker is >= 7 px from its text)
        if cx < 430:                        # the App's sidebar
            continue
        # letters like 'o' pass the ring test too; the camera fit's re-matching drops them
        out.append((cx, cy, len(pts), ring_frac))
    return out


def main():
    png = os.path.expanduser(_argv[1]) if len(_argv) > 1 else os.path.expanduser("~/Money/styl-work/native.png")
    out_path = _argv[2] if len(_argv) > 2 else os.path.join(ROOT, "ui", "basemap", "palette-globe.json")
    img = np.asarray(Image.open(png).convert("RGB"))
    H, W = img.shape[:2]
    st = os.stat(png)
    markers = detect_markers(img)
    log("marker candidates", len(markers))
    mx = np.array([m[0] for m in markers]); my = np.array([m[1] for m in markers])

    # Natural Earth populated places, the only public list with the same city set
    places = nelib.read_layer(os.path.join(RAW, "ne_places", "ne_10m_populated_places_simple"))
    cities = [(r["name"], float(pt[1]), float(pt[0]), r["scalerank"]) for k, pt, r in places if k == "point" and r["scalerank"] <= 3]
    clat = np.array([c[1] for c in cities]); clng = np.array([c[2] for c in cities])

    # initial camera: the App was opened on ll=30,125 in a window whose map centre is the image centre;
    # the right limb sits at x~2435 on row 800 (labels.py) -> f / sqrt(D^2-1) ~ 1155 px; D=3 to start
    lcx, lcy, lr, ln, lrms = limb_circle(img)
    log(f"limb circle: cx {lcx:.1f} cy {lcy:.1f} r {lr:.1f} from {ln} rows, rms {lrms:.2f} px")
    limb = (lcx, lcy, lr)
    params = np.array([30.0, 125.0, lcx, lcy, lr * math.sqrt(8), 3.0])
    # seed correspondences: six markers identified by eye on the detection overlay (2026-09-16,
    # raw/labels-debug/dots.png); they only start the fit — every anchor below is re-detected and
    # re-matched within a few px, and the seeds are replaced by whatever the fit then finds.
    SEEDS = {"Tokyo": (1794, 536), "Taipei": (1406, 890), "Hong Kong": (1210, 972), "Bangkok": (858, 1164),
             "Sapporo": (1766, 336)}
    si, sx, sy = [], [], []
    for name, (px_, py_) in SEEDS.items():
        i = next(k for k, c in enumerate(cities) if c[0] == name)
        d = np.hypot(mx - px_, my - py_); j = int(d.argmin())
        if d[j] < 12:
            si.append(i); sx.append(mx[j]); sy.append(my[j])
    params, res = fit(params, clat[si], clng[si], np.array(sx), np.array(sy), limb=limb)
    log(f"seed fit: {len(si)} cities, rms {math.sqrt((res ** 2).mean()):.2f} px; lat0 {params[0]:.3f} lng0 {params[1]:.3f} D {params[5]:.3f}")
    matches = None
    for radius in (30, 15, 12, 12):   # 12 px keeps the NE anchors (Tokyo, Sapporo sit ~10 px off: a residual model error, see README)
        x, y, front = project(params, clat, clng)
        pairs = []
        for i in range(len(cities)):
            if not front[i] or not (0 <= x[i] < W and 0 <= y[i] < H):
                continue
            d = np.hypot(mx - x[i], my - y[i])
            j = int(d.argmin())
            if d[j] < radius:
                pairs.append((i, j, float(d[j])))
        # one marker per city and vice versa: keep the closest
        best = {}
        for i, j, d in pairs:
            if j not in best or d < best[j][1]:
                best[j] = (i, d)
        matches = [(i, j) for j, (i, d) in best.items()]
        if len(matches) < 6:
            log("too few matches at radius", radius, len(matches)); break
        ci = np.array([m[0] for m in matches]); mj = np.array([m[1] for m in matches])
        params, res = fit(params, clat[ci], clng[ci], mx[mj], my[mj], limb=limb)
        log(f"radius {radius}: {len(matches)} matches, rms {math.sqrt((res ** 2).mean()):.2f} px, max {res.max():.2f}; "
            f"lat0 {params[0]:.3f} lng0 {params[1]:.3f} cx {params[2]:.1f} cy {params[3]:.1f} f {params[4]:.1f} D {params[5]:.3f}")
    ci = np.array([m[0] for m in matches]); mj = np.array([m[1] for m in matches])
    x, y, _ = project(params, clat[ci], clng[ci])
    res = np.hypot(x - mx[mj], y - my[mj])
    anchors = [{"city": cities[i][0], "lat": cities[i][1], "lng": cities[i][2], "marker_px": [round(float(mx[j]), 1), round(float(my[j]), 1)],
                "residual_px": round(float(r), 2)} for (i, j), r in zip(matches, res)]
    lat0, lng0, cx, cy, f, D = params
    limb_r = f / math.sqrt(D * D - 1)

    # ---- sampling ----------------------------------------------------------------------------
    layers, ne_version = P.ne_layers()
    kg = np.asarray(Image.open(os.path.join(RAW, "koppen", "1991_2020", "koppen_geiger_0p1.tif")))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from importlib import import_module
    gd = import_module("globe-data")
    step = 6
    gx, gy = np.meshgrid(np.arange(4, W - 4, step), np.arange(4, H - 4, step))
    glat, glng = unproject(params, gx.astype(float), gy.astype(float))
    rr = np.hypot(gx - cx, gy - cy) / limb_r
    ocean, land = {}, {}
    for yi in range(gx.shape[0]):
        for xi in range(gx.shape[1]):
            x0, y0 = int(gx[yi, xi]), int(gy[yi, xi])
            la, lo = glat[yi, xi], glng[yi, xi]
            if not np.isfinite(la) or rr[yi, xi] > 0.82:      # haze-free part of the disc only
                continue
            if x0 < 420:                                     # the App's sidebar covers the left 210 pt
                continue
            w = img[y0 - 2:y0 + 3, x0 - 2:x0 + 3].reshape(-1, 3).astype(int)
            if (w.max(0) - w.min(0)).max() > 18:             # labels, roads, coastlines out
                continue
            med = [int(v) for v in np.median(w, axis=0)]
            cls = P.ne_depth_class(layers, la, lo)
            rec = {"px": [x0, y0], "lat": round(float(la), 3), "lng": round(float(lo), 3), "rgb": med, "r_over_limb": round(float(rr[yi, xi]), 3)}
            if cls is None:
                i = int((lo + 180) / 0.1); j = int((90 - la) / 0.1)
                k = int(kg[min(max(j, 0), kg.shape[0] - 1), min(max(i, 0), kg.shape[1] - 1)])
                if k == 0:
                    continue
                tint = gd.KOPPEN_TINT.get(k, gd.DEFAULT_TINT)
                rec["koppen"] = k
                land.setdefault(tint, []).append(rec)
            else:
                ocean.setdefault(cls, []).append(rec)

    def stats(rows):
        arr = np.array([r["rgb"] for r in rows], float)
        med = np.median(arr, 0); dev = np.sqrt(((arr - med) ** 2).sum(1))
        return {"rgb": [int(round(v)) for v in med], "hex": "#%02x%02x%02x" % tuple(int(round(v)) for v in med), "n": len(rows),
                "rms_residual": round(float(np.sqrt((dev ** 2).mean())), 1), "mad_rgb": [round(float(v), 1) for v in np.median(np.abs(arr - med), 0)]}

    # haze trend inside the disc: median luminance of deep-ocean samples by r/limb bins
    deep = [r for c in (4000, 5000, 6000) for r in ocean.get(c, [])]
    bins = {}
    for r in deep:
        b = round(math.floor(r["r_over_limb"] * 10) / 10, 1)
        bins.setdefault(b, []).append(r["rgb"])
    haze = {str(b): {"rgb": [int(v) for v in np.median(np.array(v), 0)], "n": len(v)} for b, v in sorted(bins.items())}

    doc = {
        "what": "Apple Maps (macOS 27) GLOBE style colours sampled from the Maps App screenshot through a fitted globe camera",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "pipeline/basemap/globefit.py",
        "source_image": {"file": png, "size_px": [W, H], "scale": 2, "mtime_local": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
                         "note": "Maps App globe view screenshot by the acceptance session; sidebar (x < 420 px) excluded"},
        "camera": {
            "model": "perspective camera at distance D (earth radii) looking at the sphere centre; x = cx + f*px/(D-pz), y = cy - f*py/(D-pz)",
            "lat0": round(lat0, 4), "lng0": round(lng0, 4), "cx_px": round(cx, 2), "cy_px": round(cy, 2), "f_px": round(f, 2), "D_earth_radii": round(D, 4),
            "limb_radius_px": round(limb_r, 1), "camera_altitude_km": round((D - 1) * 6371.0, 0),
            "limb_fit": {"rows": ln, "rms_px": round(lrms, 2), "glow_offset_px": 14,
                         "method": "first non-black run scanning from space per row, minus the 14 px (2x) outer glow measured in labels.py; least-squares circle"},
            "anchors": anchors, "rms_px": round(float(math.sqrt((res ** 2).mean())), 2), "max_px": round(float(res.max()), 2),
            "anchor_source": f"Natural Earth 10m populated places v{open(os.path.join(RAW, 'ne_places', 'ne_10m_populated_places_simple.VERSION.txt')).read().strip()} matched to detected city markers (white disc in dark ring)",
        },
        "sampling": {"grid_px": step, "window_px": 5, "reject_if_channel_range_gt": 18, "max_r_over_limb": 0.82,
                     "ocean_class": f"Natural Earth 10m bathymetry v{ne_version}", "land_class": "Koppen (Beck et al. 2023) -> tint via globe-data.KOPPEN_TINT"},
        "ocean_bands": [dict(depth_min_m=c, depth_max_m=next((d for _, d in P.NE_LEVELS if d > c), None), **stats(ocean[c]),
                             centre=(stats([r for r in ocean[c] if r["r_over_limb"] <= 0.5]) if any(r["r_over_limb"] <= 0.5 for r in ocean[c]) else None))
                        for c in sorted(ocean)],
        "ocean_bands_note": "top-level stats: whole disc up to r/limb 0.82 (includes the radial haze trend, hence the residual); "
                            "'centre': r/limb <= 0.5 only, the least hazed colour of the band",
        "land_tints": {t: dict(stats(v), centre=(stats([r for r in v if r["r_over_limb"] <= 0.5]) if any(r["r_over_limb"] <= 0.5 for r in v) else None))
                       for t, v in land.items()},
        "haze_by_r_over_limb_deep_ocean": haze,
        # evidence subsample: every k-th grid sample per class so the file stays ~1 MB (stats above use all)
        "samples_note": "every k-th sample per class (k chosen to keep <= 200 per class); statistics above use all samples",
        "samples": {"ocean": {str(c): v[::max(1, len(v) // 200)] for c, v in ocean.items()},
                    "land": {t: v[::max(1, len(v) // 200)] for t, v in land.items()}},
    }
    json.dump(doc, open(out_path, "w"), indent=1, ensure_ascii=False)
    log("ocean:")
    for b in doc["ocean_bands"]:
        log(f"  {b['depth_min_m']:>5} n={b['n']:4d} {b['hex']} rms {b['rms_residual']}")
    log("land:", {t: (v["hex"], v["n"]) for t, v in doc["land_tints"].items()})
    log("haze:", {k: v["rgb"] for k, v in haze.items()})


if __name__ == "__main__":
    main()
