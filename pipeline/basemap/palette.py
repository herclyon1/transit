#!/usr/bin/env python3
"""Apple's renderer as a measuring instrument: sample MKMapSnapshotter output at
coordinates whose bathymetry / elevation is known from public-domain data, and
regress depth -> colour and elevation/shading -> colour.

Run from the repo root (any of the three worktrees):

    swiftc -O pipeline/basemap/sample.swift -o pipeline/basemap/raw/sample
    python3 pipeline/basemap/palette.py            # renders, downloads, fits
    python3 pipeline/basemap/palette.py --no-render  # reuse raw/renders/*.png

Outputs (committed):
    ui/basemap/palette-ocean.json   depth band -> RGB, light + dark
    ui/basemap/palette-land.json    elevation band x shading -> RGB, light + dark,
                                    fitted hill-shade light azimuth, VectorKit
                                    groundSettings exaggeration table
Inputs (gitignored, pipeline/basemap/raw/):
    ne_bathy/            Natural Earth 10m bathymetry (public domain)
    terrarium/           AWS Terrain Tiles z5 (Mapzen terrarium encoding)
    renders/             the snapshot PNGs every number cites (Apple imagery,
                         never committed or published; re-render with the args
                         recorded in the json to reproduce)

Every sample carries the image it was read from, its pixel, its coordinate and
the render timestamp. Nothing here is hand-tuned.
"""
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "pipeline", "basemap", "raw")
OUT = os.path.join(ROOT, "ui", "basemap")
RENDERS = os.path.join(RAW, "renders")
SAMPLE_BIN = os.path.join(RAW, "sample")
os.makedirs(RENDERS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# ---- the view: same as the Maps App window the acceptance session screenshots
VIEW = dict(lat=30.0, lng=125.0, dlat=50.0, dlng=60.0, w=1280, h=744)

# ---- sources -----------------------------------------------------------------
NE_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip"
NE_PAGE = "https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-bathymetry/"
NE_LEVELS = [("L", 0), ("K", 200), ("J", 1000), ("I", 2000), ("H", 3000), ("G", 4000),
             ("F", 5000), ("E", 6000), ("D", 7000), ("C", 8000), ("B", 9000), ("A", 10000)]
TERR_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TERR_DOC = "https://github.com/tilezen/joerd/blob/master/docs/data-sources.md"
TERR_Z = 5  # 256 px / 11.25 deg = ~4.9 km/px at the equator; the render is ~8.7 km/px
GROUND_SETTINGS = "/System/Library/PrivateFrameworks/VectorKit.framework/Versions/A/Resources/groundSettings.json"
GROUND_SETTINGS_NIGHT = "/System/Library/PrivateFrameworks/VectorKit.framework/Versions/A/Resources/groundSettingsNight.json"

# raster grid used to look up Natural Earth depth class (0.05 deg ~ 5.5 km, finer than a render pixel)
GRID_LNG0, GRID_LNG1, GRID_LAT0, GRID_LAT1, GRID_RES = 60.0, 185.0, -15.0, 70.0, 0.05

WIN = 2            # sample window half-size: (2*WIN+1)^2 = 25 px median
MAX_RANGE = 24     # reject windows whose per-channel range exceeds this (labels, coastlines, graticule)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- 1. render ---------------------------------------------------------------
def render(mode, no_render):
    png = os.path.join(RENDERS, f"ea-{mode}.png")
    meta = os.path.join(RENDERS, f"ea-{mode}.json")
    if no_render and os.path.exists(png) and os.path.exists(meta):
        return png, json.load(open(meta))
    if not os.path.exists(SAMPLE_BIN):
        subprocess.run(["swiftc", "-O", os.path.join(ROOT, "pipeline/basemap/sample.swift"), "-o", SAMPLE_BIN], check=True)
    pts = os.path.join(RENDERS, "empty-points.json")
    json.dump([], open(pts, "w"))
    args = [SAMPLE_BIN, str(VIEW["lat"]), str(VIEW["lng"]), str(VIEW["dlat"]), str(VIEW["dlng"]),
            str(VIEW["w"]), str(VIEW["h"]), png, pts, meta]
    if mode == "dark":
        args.append("dark")
    subprocess.run(args, check=True)
    m = json.load(open(meta))
    m["render"]["sha256"] = sha256(png)
    m["render"]["image"] = os.path.relpath(png, ROOT)
    json.dump(m, open(meta, "w"), indent=1, sort_keys=True)
    return png, m


class Projection:
    """Web-Mercator pixel mapping solved from the renderer's own point(for:) grid."""

    def __init__(self, grid_points):
        g = {p["id"]: p for p in grid_points if p.get("grid")}
        c, ne, sw = g["grid:c"], g["grid:ne"], g["grid:sw"]
        self.kx = (ne["px"] - sw["px"]) / (ne["lng"] - sw["lng"])
        self.x0 = c["px"] - self.kx * c["lng"]
        self.ky = (sw["py"] - ne["py"]) / (self._merc(ne["lat"]) - self._merc(sw["lat"]))
        self.y0 = c["py"] + self.ky * self._merc(c["lat"])
        # self-check: the four corners must reproduce to < 0.01 px
        for p in g.values():
            px, py = self.to_px(p["lat"], p["lng"])
            assert abs(px - p["px"]) < 0.01 and abs(py - p["py"]) < 0.01, (p, px, py)

    @staticmethod
    def _merc(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    def to_px(self, lat, lng):
        return self.x0 + self.kx * lng, self.y0 - self.ky * self._merc(lat)

    def to_ll(self, px, py):
        lng = (px - self.x0) / self.kx
        lat = math.degrees(2 * math.atan(math.exp((self.y0 - py) / self.ky)) - math.pi / 2)
        return lat, lng


# ---- 2. Natural Earth bathymetry --------------------------------------------
def read_shp_rings(path):
    d = open(path, "rb").read()
    pos, out = 100, []
    while pos < len(d):
        _, clen = struct.unpack(">ii", d[pos:pos + 8]); pos += 8
        end = pos + clen * 2
        if struct.unpack("<i", d[pos:pos + 4])[0] == 5:
            nparts, npts = struct.unpack("<ii", d[pos + 36:pos + 44])
            parts = struct.unpack(f"<{nparts}i", d[pos + 44:pos + 44 + 4 * nparts])
            off = pos + 44 + 4 * nparts
            xy = np.frombuffer(d, dtype="<f8", count=2 * npts, offset=off).reshape(npts, 2)
            for i in range(nparts):
                a, b = parts[i], parts[i + 1] if i + 1 < nparts else npts
                out.append(xy[a:b])
        pos = end
    return out


def ne_layers():
    """Return {depth: uint8 raster} rasterised with even-odd fill on GRID_*."""
    zpath = os.path.join(RAW, "ne_10m_bathymetry_all.zip")
    shp_dir = os.path.join(RAW, "ne_bathy")
    if not os.path.exists(zpath):
        log("downloading", NE_URL)
        urllib.request.urlretrieve(NE_URL, zpath)
    if not os.path.exists(shp_dir):
        zipfile.ZipFile(zpath).extractall(shp_dir)
    W = int(round((GRID_LNG1 - GRID_LNG0) / GRID_RES))
    H = int(round((GRID_LAT1 - GRID_LAT0) / GRID_RES))
    layers, version = {}, None
    for letter, depth in NE_LEVELS:
        base = os.path.join(shp_dir, f"ne_10m_bathymetry_{letter}_{depth}")
        if version is None:
            version = open(base + ".VERSION.txt").read().strip()
        acc = np.zeros((H, W), dtype=np.uint8)
        for ring in read_shp_rings(base + ".shp"):
            x = (ring[:, 0] - GRID_LNG0) / GRID_RES
            y = (GRID_LAT1 - ring[:, 1]) / GRID_RES
            if x.max() < 0 or x.min() > W or y.max() < 0 or y.min() > H:
                continue
            x0, x1 = max(int(math.floor(x.min())), 0), min(int(math.ceil(x.max())) + 1, W)
            y0, y1 = max(int(math.floor(y.min())), 0), min(int(math.ceil(y.max())) + 1, H)
            if x1 <= x0 or y1 <= y0:
                continue
            im = Image.new("1", (x1 - x0, y1 - y0), 0)
            ImageDraw.Draw(im).polygon(list(zip((x - x0).tolist(), (y - y0).tolist())), fill=1)
            acc[y0:y1, x0:x1] ^= np.asarray(im, dtype=np.uint8)
        layers[depth] = acc
        log(f"NE {letter}_{depth}: {int(acc.sum())} cells")
    return layers, version


def ne_depth_class(layers, lat, lng):
    """Deepest Natural Earth level containing the point; None = land (not in L_0)."""
    i = int((lng - GRID_LNG0) / GRID_RES)
    j = int((GRID_LAT1 - lat) / GRID_RES)
    if not (0 <= i < layers[0].shape[1] and 0 <= j < layers[0].shape[0]):
        return None
    best = None
    for _, depth in NE_LEVELS:
        if layers[depth][j, i]:
            best = depth
    return best


# ---- 3. terrarium elevation -------------------------------------------------
_tiles = {}


def terrarium_tile(z, x, y):
    key = (z, x, y)
    if key in _tiles:
        return _tiles[key]
    d = os.path.join(RAW, "terrarium", str(z), str(x))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{y}.png")
    if not os.path.exists(p):
        url = TERR_URL.format(z=z, x=x, y=y)
        for attempt in range(3):
            try:
                urllib.request.urlretrieve(url, p)
                break
            except Exception as e:  # noqa: BLE001
                log("retry", url, e)
                time.sleep(1 + attempt)
        else:
            raise RuntimeError(url)
    a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float64)
    ele = a[:, :, 0] * 256 + a[:, :, 1] + a[:, :, 2] / 256 - 32768
    _tiles[key] = ele
    return ele


def elevation_and_slope(lat, lng, z=TERR_Z):
    """Elevation (m), slope (deg), aspect (deg clockwise from north, downhill) via Horn's method."""
    n = 2 ** z
    fx = (lng + 180) / 360 * n
    lr = math.radians(lat)
    fy = (1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n
    tx, ty = int(fx), int(fy)
    px, py = int((fx - tx) * 256), int((fy - ty) * 256)
    # stitch a 3x3 neighbourhood across tile borders
    def val(dx, dy):
        X, Y, ttx, tty = px + dx, py + dy, tx, ty
        if X < 0: X += 256; ttx -= 1
        if X > 255: X -= 256; ttx += 1
        if Y < 0: Y += 256; tty -= 1
        if Y > 255: Y -= 256; tty += 1
        return terrarium_tile(z, ttx % n, min(max(tty, 0), n - 1))[Y, X]
    e = [[val(dx, dy) for dx in (-1, 0, 1)] for dy in (-1, 0, 1)]
    # metres per pixel at this latitude
    mpp = 40075016.686 * math.cos(lr) / (256 * n)
    dzdx = ((e[0][2] + 2 * e[1][2] + e[2][2]) - (e[0][0] + 2 * e[1][0] + e[2][0])) / (8 * mpp)
    dzdy = ((e[2][0] + 2 * e[2][1] + e[2][2]) - (e[0][0] + 2 * e[0][1] + e[0][2])) / (8 * mpp)
    slope = math.degrees(math.atan(math.hypot(dzdx, dzdy)))
    # atan2(dzdx, -dzdy) is the uphill compass direction (checked on Fuji's four flanks,
    # 2026-09-16); +180 makes it the standard aspect = downhill (facing) direction, 0 = N, 90 = E
    aspect = (math.degrees(math.atan2(dzdx, -dzdy)) + 180) % 360
    return e[1][1], slope, aspect, (tx, ty, px, py)


def hillshade(slope_deg, aspect_deg, az_deg, alt_deg=45.0):
    s, a = math.radians(slope_deg), math.radians(aspect_deg)
    zen, az = math.radians(90 - alt_deg), math.radians(az_deg)
    return max(0.0, math.cos(zen) * math.cos(s) + math.sin(zen) * math.sin(s) * math.cos(az - a))


# ---- 4. sampling --------------------------------------------------------------
def sample_window(img, px, py):
    x, y = int(px), int(py)
    if x - WIN < 0 or y - WIN < 0 or x + WIN >= img.shape[1] or y + WIN >= img.shape[0]:
        return None
    w = img[y - WIN:y + WIN + 1, x - WIN:x + WIN + 1].reshape(-1, 3).astype(int)
    rng = int((w.max(axis=0) - w.min(axis=0)).max())
    med = np.median(w, axis=0)
    return [int(round(v)) for v in med], rng


def hexcol(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def stats(rows, key):
    arr = np.array([r[key] for r in rows], dtype=float)
    med = np.median(arr, axis=0)
    dev = np.sqrt(((arr - med) ** 2).sum(axis=1))
    return {
        "rgb": [int(round(v)) for v in med],
        "hex": hexcol([int(round(v)) for v in med]),
        "n": len(rows),
        "mad_rgb": [float(round(v, 1)) for v in np.median(np.abs(arr - med), axis=0)],
        "rms_residual": float(round(math.sqrt((dev ** 2).mean()), 1)),
        "max_residual": float(round(dev.max(), 1)),
    }


def fit_light_azimuth(rows):
    """Azimuth (deg from N, clockwise) whose 45-deg-altitude hill-shade best
    correlates with sample luminance, after removing the per-band median."""
    if len(rows) < 12:
        return None
    lum = np.array([0.2126 * r["light_rgb"][0] + 0.7152 * r["light_rgb"][1] + 0.0722 * r["light_rgb"][2] for r in rows])
    bands = np.array([r.get("tint", r["band"]) for r in rows])
    for b in set(bands):
        lum[bands == b] -= np.median(lum[bands == b])
    best, curve = None, {}
    for az in range(0, 360, 5):
        hs = np.array([hillshade(r["slope_deg"], r["aspect_deg"], az) for r in rows])
        if hs.std() == 0:
            continue
        c = float(np.corrcoef(hs, lum)[0, 1])
        if az % 30 == 0:
            curve[str(az)] = round(c, 2)
        if best is None or c > best[1]:
            best = (az, c)
    return {"azimuth_deg": best[0], "pearson_r": round(best[1], 3), "n": len(rows), "r_by_azimuth": curve,
            "note": "argmax over 5-deg steps of corr(hillshade(slope, aspect, az, alt=45), luminance demeaned per "
                    "tint class (land) / depth class (ocean)); r < 0.3 means the fit is not usable"}


def main():
    no_render = "--no-render" in sys.argv
    light_png, light_meta = render("light", no_render)
    dark_png, dark_meta = render("dark", no_render)
    proj = Projection(light_meta["points"])
    light = np.asarray(Image.open(light_png).convert("RGB"))
    dark = np.asarray(Image.open(dark_png).convert("RGB"))
    H, W = light.shape[:2]
    lat_n, lng_w = proj.to_ll(0, 0)
    lat_s, lng_e = proj.to_ll(W, H)
    log(f"visible: lat {lat_s:.2f}..{lat_n:.2f} lng {lng_w:.2f}..{lng_e:.2f}")

    layers, ne_version = ne_layers()

    # deterministic jittered grid of candidates over the visible pixels
    rng = np.random.default_rng(20260916)
    step = 12  # px
    cands = []
    for py in range(WIN + 2, H - WIN - 2, step):
        for px in range(WIN + 2, W - WIN - 2, step):
            cands.append((px + rng.uniform(-4, 4), py + rng.uniform(-4, 4)))
    log("candidates", len(cands))

    ocean, land = [], []
    for px, py in cands:
        lat, lng = proj.to_ll(px, py)
        if lat < -8 or lat > 62 or lng < GRID_LNG0 or lng > GRID_LNG1:
            continue
        cls = ne_depth_class(layers, lat, lng)
        sl = sample_window(light, px, py)
        sd = sample_window(dark, px, py)
        if sl is None or sd is None or sl[1] > MAX_RANGE or sd[1] > MAX_RANGE:
            continue
        ele, slope, aspect, tile = elevation_and_slope(lat, lng)
        row = {
            "lat": round(lat, 4), "lng": round(lng, 4), "px": int(px), "py": int(py),
            "light_rgb": sl[0], "light_hex": hexcol(sl[0]), "dark_rgb": sd[0], "dark_hex": hexcol(sd[0]),
            "window_range_light": sl[1], "window_range_dark": sd[1],
            "terrarium_m": round(float(ele), 1), "slope_deg": round(slope, 2), "aspect_deg": round(aspect, 1),
            "terrarium_tile": f"{TERR_Z}/{tile[0]}/{tile[1]} px {tile[2]},{tile[3]}",
        }
        if cls is None:
            if ele < 0:      # NE says land, ETOPO1 says water: coast ambiguity, drop
                continue
            tint = tint_class(sl[0])
            if tint is None:  # inland water (lakes) or unclassifiable
                continue
            row["band"] = land_band(ele)
            row["tint"] = tint
            land.append(row)
        else:
            if ele > 0:      # NE says ocean, ETOPO1 says land: drop
                continue
            row["ne_depth_class_m"] = cls
            row["band"] = cls
            ocean.append(row)
    log("kept ocean", len(ocean), "land", len(land))

    # ---- ocean: keep 200, stratified by NE class -----------------------------
    by = {}
    for r in ocean:
        by.setdefault(r["band"], []).append(r)
    target = 200
    classes = sorted(by)
    quota = {c: min(len(by[c]), max(6, target // len(classes))) for c in classes}
    # fill the remainder from the largest classes
    while sum(quota.values()) < target and any(quota[c] < len(by[c]) for c in classes):
        for c in sorted(classes, key=lambda c: -len(by[c])):
            if quota[c] < len(by[c]) and sum(quota.values()) < target:
                quota[c] += 1
    picked = []
    for c in classes:
        idx = rng.choice(len(by[c]), quota[c], replace=False)
        picked += [by[c][i] for i in sorted(idx)]
    for i, r in enumerate(picked):
        r["id"] = f"o{i:03d}"
    ocean_bands = []
    for c in classes:
        rows = [r for r in picked if r["band"] == c]
        nxt = next((d for _, d in NE_LEVELS if d > c), None)
        ocean_bands.append({
            "depth_min_m": c, "depth_max_m": nxt,
            "natural_earth_layer": f"ne_10m_bathymetry_{[l for l, d in NE_LEVELS if d == c][0]}_{c}",
            "terrarium_depth_m_median": round(float(np.median([-r["terrarium_m"] for r in rows])), 0),
            "light": stats(rows, "light_rgb"), "dark": stats(rows, "dark_rgb"),
            "sample_ids": [r["id"] for r in rows],
        })
    ocean_az = fit_light_azimuth([r for r in picked if r["slope_deg"] > 0.05])

    # ---- land: elevation band x shading ---------------------------------------
    for i, r in enumerate(land):
        r["id"] = f"l{i:03d}"
    land_az = fit_light_azimuth([r for r in land if r["slope_deg"] > 0.3])
    az = land_az["azimuth_deg"] if land_az else 315
    for r in land:
        r["hillshade_fit"] = round(hillshade(r["slope_deg"], r["aspect_deg"], az), 3)
        r["shading"] = "flat" if r["slope_deg"] < 0.3 else ("lit" if r["hillshade_fit"] > hillshade(0, 0, az) else "shaded")
    land_tints = []
    for tint in TINT_ORDER:
        rows_t = [r for r in land if r["tint"] == tint]
        if len(rows_t) < 3:
            continue
        ele = np.array([r["terrarium_m"] for r in rows_t])
        entry = {
            "tint": tint, "rule": TINT_RULES[tint],
            "n": len(rows_t),
            "elevation_m_p10_p50_p90": [int(v) for v in np.percentile(ele, [10, 50, 90])],
            "example_coords": [[r["lat"], r["lng"]] for r in rows_t[:3]],
            "by_shading": {}, "by_elevation_flat": [],
        }
        for sh in ("flat", "lit", "shaded"):
            rows = [r for r in rows_t if r["shading"] == sh]
            if len(rows) >= 3:
                entry["by_shading"][sh] = {"light": stats(rows, "light_rgb"), "dark": stats(rows, "dark_rgb"),
                                          "sample_ids": [r["id"] for r in rows]}
        for lo, hi in LAND_BANDS:
            rows = [r for r in rows_t if r["band"] == lo and r["shading"] == "flat"]
            if len(rows) >= 3:
                entry["by_elevation_flat"].append({"elevation_min_m": lo, "elevation_max_m": hi,
                                                   "light": stats(rows, "light_rgb"), "dark": stats(rows, "dark_rgb"),
                                                   "sample_ids": [r["id"] for r in rows]})
        land_tints.append(entry)
    hs_probe = hillshade_probe(no_render)

    common_sources = {
        "renderer": {
            "light": light_meta["render"], "dark": dark_meta["render"],
            "note": "Apple's own renderer (MKMapSnapshotter) run locally as an instrument. The PNGs are Apple "
                    "imagery and are not committed; re-render with sample.swift and the recorded args to reproduce.",
        },
        "projection": {
            "method": "Web Mercator solved from MKMapSnapshot.point(for:) at the region centre and corners "
                      "(grid:* points in the render json), corners reproduce to <0.01 px",
            "visible_bbox": {"lat": [round(lat_s, 3), round(lat_n, 3)], "lng": [round(lng_w, 3), round(lng_e, 3)]},
            "px_per_deg_lng": round(proj.kx, 4),
        },
        "sampling": {
            "window_px": 2 * WIN + 1, "statistic": "per-channel median",
            "reject_if_channel_range_gt": MAX_RANGE,
            "candidate_grid_px": step, "jitter_px": 4, "seed": 20260916,
            "cross_check": "Natural Earth class must agree in sign with the terrarium elevation, else the point is dropped",
        },
    }

    ocean_doc = {
        "what": "Apple Maps (macOS, VectorKit native style) ocean colour by depth band, East Asia view, light and dark",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "pipeline/basemap/palette.py",
        "sources": dict(common_sources, **{
            "bathymetry_class": {
                "name": f"Natural Earth 10m Bathymetry v{ne_version}", "url": NE_URL, "page": NE_PAGE,
                "license": "public domain", "levels_m": [d for _, d in NE_LEVELS],
                "lookup": f"even-odd rasterisation at {GRID_RES} deg, deepest containing layer wins",
            },
            "depth_continuous": {
                "name": f"AWS Terrain Tiles (terrarium) z{TERR_Z}; ocean values come from ETOPO1 per the Tilezen source list",
                "url": TERR_URL, "doc": TERR_DOC, "decode": "(R*256 + G + B/256) - 32768 metres",
                "role": "sanity check and per-band median depth only; the bands themselves are Natural Earth",
            },
        }),
        "bands": ocean_bands,
        "seafloor_shading": {"light_azimuth_fit": ocean_az,
                             "note": "the renderer also hill-shades the seafloor; residuals inside a band are mostly this relief"},
        "samples": picked,
    }
    land_doc = {
        "what": "Apple Maps (macOS, VectorKit native style) land colour by elevation band and hill-shade class, East Asia view, light and dark",
        "generated_utc": ocean_doc["generated_utc"],
        "generator": "pipeline/basemap/palette.py",
        "caveat": "at this zoom the renderer's land colour is a land-cover/climate tint (humid green, semi-humid "
                  "yellow-green, dry tan, very-dry pink-white, high/arctic grey-white) with only a faint hill-shade on "
                  "top; elevation alone does not predict it. Tints are classified from the renderer's own output by "
                  "hue/saturation (rule recorded per tint); 'flat' rows are the base tint, lit/shaded the hill-shade "
                  "delta. The strong hill-shade seen in the Maps App at country zoom is measured separately in "
                  "hillshade.probe_japan_alps.",
        "sources": dict(common_sources, **{
            "elevation": {
                "name": f"AWS Terrain Tiles (terrarium) z{TERR_Z}", "url": TERR_URL, "doc": TERR_DOC,
                "decode": "(R*256 + G + B/256) - 32768 metres",
                "slope_aspect": f"Horn 3x3 on the z{TERR_Z} tile (~{40075016.686 / (256 * 2 ** TERR_Z) / 1000:.1f} km/px at the equator)",
            },
            "exaggeration": {
                "file": GROUND_SETTINGS, "night_file": GROUND_SETTINGS_NIGHT,
                "copied_from": "~/Money/styl-work/groundSettings.json (same bytes as the framework copy)",
            },
        }),
        "hillshade": {
            "globe_view_fit": land_az,
            "probe_japan_alps": hs_probe,
            "altitude_deg_assumed": 45,
            "class_rule": "slope<0.3deg = flat; else lit if hillshade(az_fit) > hillshade of flat ground, shaded otherwise",
        },
        "ground_settings": load_ground_settings(),
        "tints": land_tints,
        "samples": land,
    }
    with open(os.path.join(OUT, "palette-ocean.json"), "w") as f:
        json.dump(ocean_doc, f, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT, "palette-land.json"), "w") as f:
        json.dump(land_doc, f, indent=1, ensure_ascii=False)
    log("ocean bands:")
    for b in ocean_bands:
        log(f"  {b['depth_min_m']:>5}-{str(b['depth_max_m']):<5} n={b['light']['n']:3d} light {b['light']['hex']} rms {b['light']['rms_residual']:5.1f}  dark {b['dark']['hex']} rms {b['dark']['rms_residual']:5.1f}")
    log("land tints:")
    for t in land_tints:
        for sh, v in t["by_shading"].items():
            log(f"  {t['tint']:12s} {sh:6s} n={v['light']['n']:3d} light {v['light']['hex']} rms {v['light']['rms_residual']:5.1f}  dark {v['dark']['hex']} rms {v['dark']['rms_residual']:5.1f}")
    log("azimuth land", land_az, "ocean", ocean_az, "alps probe", hs_probe["fit"])


import colorsys

# Tint classes describe the renderer's output, they are not a design choice:
# the light-mode land samples cluster in hue at ~15-45 (pink-white), ~45-66
# (tan), ~66-80 (yellow-green), ~80-140 (green); grey-white (sat < 0.06) is the
# high plateau. Hue 170-230 with saturation is inland water and is dropped.
TINT_RULES = {
    "high_grey":  "sat < 0.06 (grey-white, Tibetan plateau)",
    "very_dry":   "hue < 45 and sat < 0.2 (pink-white, Taklamakan / western Gobi)",
    "dry":        "45 <= hue < 66 (tan, Mongolia / Gobi)",
    "semi_humid": "66 <= hue < 80 (yellow-green, steppe)",
    "humid":      "80 <= hue < 140 (green)",
}
TINT_ORDER = ["humid", "semi_humid", "dry", "very_dry", "high_grey"]


def tint_class(rgb):
    h, sat, _ = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    h *= 360
    if 170 <= h <= 230 and sat > 0.2:
        return None  # lake
    if sat < 0.06:
        return "high_grey"
    if h < 45 and sat < 0.2:
        return "very_dry"
    if 45 <= h < 66:
        return "dry"
    if 66 <= h < 80:
        return "semi_humid"
    if 80 <= h < 140:
        return "humid"
    return None


# country-zoom probe where hill-shade dominates: Japanese Alps (Hida / Kiso ranges)
PROBE = dict(lat=36.3, lng=137.7, dlat=1.0, dlng=1.4, w=1280, h=744, z=10)


def hillshade_probe(no_render):
    """Fit the renderer's hill-shade light azimuth on a country-zoom render
    against terrarium z10 slope/aspect (same method as the globe-view fit)."""
    png = os.path.join(RENDERS, "probe-alps-light.png")
    meta = os.path.join(RENDERS, "probe-alps-light.json")
    if not (no_render and os.path.exists(png) and os.path.exists(meta)):
        pts = os.path.join(RENDERS, "empty-points.json")
        json.dump([], open(pts, "w"))
        subprocess.run([SAMPLE_BIN, str(PROBE["lat"]), str(PROBE["lng"]), str(PROBE["dlat"]), str(PROBE["dlng"]),
                        str(PROBE["w"]), str(PROBE["h"]), png, pts, meta], check=True)
        m = json.load(open(meta))
        m["render"]["sha256"] = sha256(png)
        m["render"]["image"] = os.path.relpath(png, ROOT)
        json.dump(m, open(meta, "w"), indent=1, sort_keys=True)
    m = json.load(open(meta))
    proj = Projection(m["points"])
    img = np.asarray(Image.open(png).convert("RGB"))
    H, W = img.shape[:2]
    rows = []
    for py in range(4, H - 4, 8):
        for px in range(4, W - 4, 8):
            s = sample_window(img, px, py)
            if s is None or s[1] > 40:
                continue
            h, sat, _ = colorsys.rgb_to_hsv(*[c / 255 for c in s[0]])
            if not (40 <= h * 360 <= 140) or sat < 0.1:
                continue  # land tints only: roads, water and labels out
            lat, lng = proj.to_ll(px, py)
            ele, slope, aspect, _ = elevation_and_slope(lat, lng, z=PROBE["z"])
            if ele <= 0 or slope < 2:
                continue
            rows.append({"light_rgb": s[0], "slope_deg": slope, "aspect_deg": aspect, "band": land_band(ele)})
    return {"render": m["render"], "terrarium_zoom": PROBE["z"], "samples_used": len(rows),
            "filters": "5x5 window range <= 40, hue 40-140 & sat >= 0.1, elevation > 0, slope >= 2 deg",
            "fit": fit_light_azimuth(rows)}


LAND_BANDS = [(0, 200), (200, 500), (500, 1000), (1000, 2000), (2000, 3000), (3000, 4500), (4500, None)]


def land_band(ele):
    for lo, hi in LAND_BANDS:
        if hi is None or ele < hi:
            return lo
    return LAND_BANDS[-1][0]


def load_ground_settings():
    out = {}
    for name, path in (("day", GROUND_SETTINGS), ("night", GROUND_SETTINGS_NIGHT)):
        try:
            g = json.load(open(path))
        except Exception:  # noqa: BLE001
            g = json.load(open(os.path.expanduser(f"~/Money/styl-work/{os.path.basename(path)}")))
        out[name] = {
            "groundElevationScale_by_zoom": {k: v["groundElevationScale"] for k, v in g.items() if "groundElevationScale" in v},
            "normalsSharpnessBias_by_zoom": {k: v["normalsSharpnessBias"] for k, v in g.items() if "normalsSharpnessBias" in v},
            "hsv_adjustments_by_zoom_range": {k: v for k, v in g.items() if "-" in k},
        }
    return out


if __name__ == "__main__":
    main()
