#!/usr/bin/env python3
"""Calibrate the globe page's hill-shade exaggeration against Apple's renders.

Target: the luminance amplitude over the 5-95% hill-shade range measured on Apple's
own output (palette-land.json hillshade section):
    z~9 Japanese Alps probe  : 14.3 luma units   (regression slope 24.2 x hs range 0.59)
    z~4 East Asia globe view : ~0   (humid lit vs shaded differ by < 3 RGB, sign reversed)
Method: load map/index.html in headless Chrome at the same views, set
hillshade-exaggeration to k, screenshot, sample a pixel grid, look up terrarium
slope/aspect at the same coordinates (same code as palette.py) and regress luminance
on hillshade(az=260, alt=45). Bisect k until the amplitude matches. Writes the result
into map/data/meta.json -> hillshade.exaggeration_by_zoom.

    python3 pipeline/basemap/calibrate.py   (rangeserver on 8792 must be running)
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
import palette as P  # noqa: E402  (elevation_and_slope, hillshade)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(ROOT, "map", "meta-ui.json")
TMP = os.path.join(ROOT, "pipeline", "basemap", "raw", "calib")
os.makedirs(TMP, exist_ok=True)
BASE = os.environ.get("ACCEPT_BASE", "http://127.0.0.1:8792")

VIEWS = {
    # name: (hash, terrarium zoom for slope, target amplitude, method)
    # alps: regression of luminance on hillshade, exactly as measured on Apple's probe render
    "alps_z9": ("ll=36.3,137.7&spn=1.0,1.4", 10, 14.3, "regress"),
    # globe: at this zoom Apple's shading is not directional (humid lit vs shaded within noise) but sloped
    # ground is ~6 luma darker than flat (palette-land humid: flat #bfe98b 205.8, lit 198.9, shaded 200.9).
    # Tints confound a direct regression here, so the target is the 5-95% range of the per-pixel
    # luminance change caused by the hill-shade layer alone (render at k minus render at k=0).
    "globe_z4": ("ll=30,125&spn=50,60", 5, 6.0, "delta"),
    # country zoom (the Japan acceptance view): the target is measured on the App's own flat render of the
    # same view (styl-work/snap-japan.png) with the same regression, through our page's pixel->lnglat map
    "japan_z5": ("ll=36,138&spn=12,16&ui=0", 7, os.path.expanduser("~/Money/styl-work/snap-japan.png"), "regress"),
}


def shoot(view_hash, k, out):
    js = ("(async()=>{const m=__globe.map; __globe.setHillshade(%s); await new Promise(r=>setTimeout(r,1500));"
          "const pts=[]; for(let y=8;y<innerHeight-8;y+=8) for(let x=8;x<innerWidth-8;x+=8){const ll=m.unproject([x,y]);"
          "pts.push([x,y,ll.lng,ll.lat]);} return JSON.stringify({z:m.getZoom(),pts});})()" % k)
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline/basemap/shot.py"), f"{BASE}/map/index.html#{view_hash}",
                    "1280", "744", out, "--settle", "3", "--eval-js", js, "--eval-out", out + ".json"], check=True,
                   stdout=subprocess.DEVNULL)
    d = json.loads(json.load(open(out + ".json")))
    return d["z"], d["pts"]


def amplitude(png, pts, tz, land_only=True):
    img = np.asarray(Image.open(png).convert("RGB")).astype(float)
    rows = []
    for x, y, lng, lat in pts:
        if not (-85 < lat < 85):
            continue
        # skip labels/halo: 5x5 window must be smooth
        w = img[y - 2:y + 3, x - 2:x + 3].reshape(-1, 3)
        if (w.max(0) - w.min(0)).max() > 40:
            continue
        try:
            ele, slope, aspect, _ = P.elevation_and_slope(lat, lng, z=tz)
        except Exception:  # noqa: BLE001
            continue
        if land_only and ele <= 0:
            continue
        if slope < (2 if tz >= 10 else 0.3):
            continue
        lum = img[y, x] @ [0.2126, 0.7152, 0.0722]
        rows.append((lum, P.hillshade(slope, aspect, 260, 45)))
    if len(rows) < 30:
        return None, len(rows)
    a = np.array(rows)
    A = np.vstack([np.ones(len(a)), a[:, 1]]).T
    b = np.linalg.lstsq(A, a[:, 0], rcond=None)[0]
    lo, hi = np.percentile(a[:, 1], [5, 95])
    return float(b[1] * (hi - lo)), len(rows)


def delta_amplitude(png_k, png_0, pts):
    a = np.asarray(Image.open(png_k).convert("RGB")).astype(float) @ [0.2126, 0.7152, 0.0722]
    b = np.asarray(Image.open(png_0).convert("RGB")).astype(float) @ [0.2126, 0.7152, 0.0722]
    d = np.array([a[y, x] - b[y, x] for x, y, lng, lat in pts if -85 < lat < 85])
    d = d[np.abs(d) > 0.01]            # pixels the hill-shade touched at all (land + seafloor relief)
    if len(d) < 30:
        return None, len(d)
    lo, hi = np.percentile(d, [5, 95])
    return float(hi - lo), len(d)


def main():
    meta = json.load(open(META))
    result = {}
    only = [a for a in ARGS if not a.startswith("-")]
    for name, (h, tz, target, method) in VIEWS.items():
        if only and name not in only:
            continue
        lo, hi = 0.0, 1.0
        best = None
        png0 = None
        if isinstance(target, str):   # measure the target amplitude on the App image with our pixel grid
            probe = os.path.join(TMP, f"{name}-probe.png")
            z, pts = shoot(h, 0.05, probe)
            app_png = os.path.join(TMP, f"{name}-app.png")
            Image.open(target).convert("RGB").resize((1280, 744), Image.LANCZOS).save(app_png)
            target, n_t = amplitude(app_png, pts, tz)
            print(f"{name}: App target amplitude {target:.2f} from {n_t} land samples ({os.path.basename(VIEWS[name][2])})", file=sys.stderr, flush=True)
            VIEWS[name] = (h, tz, target, method)
        if method == "delta":
            png0 = os.path.join(TMP, f"{name}-0.000.png")
            shoot(h, 0.0, png0)
        for it in range(7):
            k = (lo + hi) / 2
            png = os.path.join(TMP, f"{name}-{k:.3f}.png")
            z, pts = shoot(h, k, png)
            amp, n = amplitude(png, pts, tz) if method == "regress" else delta_amplitude(png, png0, pts)
            print(f"{name} z={z:.2f} k={k:.3f} amplitude={amp} n={n}", file=sys.stderr, flush=True)
            if amp is None:
                break
            best = (k, amp, n, z)
            if abs(amp - target) < 0.5:
                break
            if amp < target:
                lo = k
            else:
                hi = k
        result[name] = {"zoom": round(best[3], 2), "k": round(best[0], 3), "amplitude": round(best[1], 1), "n": best[2],
                        "target": target, "method": method}
    ex = dict(meta["hillshade"].get("exaggeration_by_zoom") or {})   # keep earlier anchors (z3, z9) when a view is skipped
    ex.update({str(round(v["zoom"])): v["k"] for v in result.values()})
    meta["hillshade"]["exaggeration_by_zoom"] = ex
    meta["hillshade"]["calibration"] = dict(meta["hillshade"].get("calibration") or {}, **result, method=__doc__.strip().split("\n")[0], azimuth=260, altitude=45)
    json.dump(meta, open(META, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
