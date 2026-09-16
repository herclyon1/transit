#!/usr/bin/env python3
"""Hill-shade amplitude of a 1280x744 Web-Mercator render at a known camera: regress land luminance
on terrarium hillshade(az 260, alt 45) and report slope x (p95-p5 hillshade range), the same statistic
calibrate.py / palette.py use. Works on the App snapshot and on our render alike (no browser needed).

    python3 pipeline/basemap/hs-amplitude.py <png> <center_lng> <center_lat> <zoom> [terrarium_z]
"""
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ARGS = sys.argv[1:]
sys.argv = [sys.argv[0]]
import palette as P  # noqa: E402

png, clng, clat, zoom = ARGS[0], float(ARGS[1]), float(ARGS[2]), float(ARGS[3])
tz = int(ARGS[4]) if len(ARGS) > 4 else 7
img = np.asarray(Image.open(png).convert("RGB").resize((1280, 744), Image.LANCZOS)).astype(float)
W, H = 1280, 744
scale = 512 * 2 ** zoom          # world size in px at this zoom (MapLibre 512 tiles)


def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


cx = (clng + 180) / 360 * scale
cy = (1 - merc(clat) / math.pi) / 2 * scale
rows = []
for y in range(8, H - 8, 6):
    for x in range(8, W - 8, 6):
        wx = cx + (x - W / 2); wy = cy + (y - H / 2)
        lng = wx / scale * 360 - 180
        lat = math.degrees(2 * math.atan(math.exp((1 - 2 * wy / scale) * math.pi)) - math.pi / 2)
        w = img[y - 2:y + 3, x - 2:x + 3].reshape(-1, 3)
        if (w.max(0) - w.min(0)).max() > 40:      # roads / labels / coast
            continue
        ele, slope, aspect, _ = P.elevation_and_slope(lat, lng, z=tz)
        if ele <= 0 or slope < 1.0:
            continue
        rows.append((img[y, x] @ [0.2126, 0.7152, 0.0722], P.hillshade(slope, aspect, 260, 45)))
a = np.array(rows)
A = np.vstack([np.ones(len(a)), a[:, 1]]).T
b = np.linalg.lstsq(A, a[:, 0], rcond=None)[0]
lo, hi = np.percentile(a[:, 1], [5, 95])
r = np.corrcoef(a[:, 1], a[:, 0])[0, 1]
print(f"{os.path.basename(png)}: n={len(a)} slope={b[1]:.2f} hs_range={hi - lo:.2f} amplitude={b[1] * (hi - lo):.2f} r={r:.3f}")
