#!/usr/bin/env python3
"""Find the page camera that best overlays an App globe screenshot (acceptance metric = share of
pixels differing by > 40 after masking the toolbar column). Coordinate descent over zoom, centre
and right padding; each step renders the page headless and scores it with cmpdiff.

    python3 pipeline/basemap/aligncam.py ~/Money/styl-work/native-nosidebar.png 3.30 30.14 124.45 0
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.environ.get("ACCEPT_BASE", "http://127.0.0.1:8792")
TMP = os.path.join(ROOT, "pipeline", "basemap", "raw", "align")
os.makedirs(TMP, exist_ok=True)


def score(app, z, lat, lng, padr, extra=""):
    out = os.path.join(TMP, f"z{z:.3f}_{lat:.2f}_{lng:.2f}_p{padr}.png")
    if not os.path.exists(out):
        pad = f"&padr={padr}" if padr > 0 else (f"&padl={-padr}" if padr < 0 else "")
        subprocess.run([sys.executable, os.path.join(ROOT, "pipeline/basemap/shot.py"),
                        f"{BASE}/map/index.html#{z:.3f}/{lat:.2f}/{lng:.2f}{pad}{extra}", "1280", "744", out, "--settle", "5"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    a = np.asarray(Image.open(out).convert("RGB")).astype(int)
    d = np.abs(a - app).max(2)
    mask = np.ones(d.shape, bool); mask[:, 1228:] = False
    return float(100 * ((d > 40) & mask).sum() / mask.sum())


def main():
    app_png = os.path.expanduser(sys.argv[1])
    z, lat, lng, padr = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
    app = np.asarray(Image.open(app_png).convert("RGB").resize((1280, 744), Image.BOX)).astype(int)
    best = score(app, z, lat, lng, padr)
    print(f"start z {z} lat {lat} lng {lng} padr {padr}: {best:.2f}%", flush=True)
    steps = {"z": 0.02, "lat": 0.15, "lng": 0.15, "padr": 8}
    for rnd in range(3):
        improved = False
        for key in ("lng", "lat", "z", "padr"):
            for sgn in (+1, -1):
                cand = dict(z=z, lat=lat, lng=lng, padr=padr)
                cand[key] = cand[key] + sgn * steps[key]
                s = score(app, cand["z"], cand["lat"], cand["lng"], int(cand["padr"]))
                print(f"  {key}{'+' if sgn > 0 else '-'} -> z {cand['z']:.3f} lat {cand['lat']:.2f} lng {cand['lng']:.2f} padr {int(cand['padr'])}: {s:.2f}%", flush=True)
                if s < best - 0.02:
                    best, z, lat, lng, padr = s, cand["z"], cand["lat"], cand["lng"], int(cand["padr"]); improved = True
        if not improved:
            for k in steps: steps[k] /= 2
    print(f"best z {z:.3f} lat {lat:.2f} lng {lng:.2f} padr {padr}: {best:.2f}%")


if __name__ == "__main__":
    main()
