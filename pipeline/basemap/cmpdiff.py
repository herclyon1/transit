#!/usr/bin/env python3
"""Acceptance metric: share of pixels where our render differs from the App screenshot by more than a threshold.

    python3 pipeline/basemap/cmpdiff.py <ours.png 1280x744> <app.png 2560x1488 or 1280x744> [out-diff.png] [--t 40]

Both images at 1280x744 (LANCZOS resample, as the acceptance session does), the App toolbar column
x > 1228 masked, per-pixel luminance of |dRGB| (PIL 'L': 299/587/114) > t counted — the exact recipe of the
acceptance session's cmp-accept.py (2026-09-16; an earlier version of this file used max(|dR|,|dG|,|dB|), which
reads ~1.7x higher). The threshold argument exists for dark mode, where absolute differences are small and
t = 40 hides most of them (acceptance, 2026-09-16 evening: report t = 20 alongside).
"""
import sys

import numpy as np
from PIL import Image

args = [a for a in sys.argv[1:] if not a.startswith("--")]
thr = 40
if "--t" in sys.argv:
    thr = int(sys.argv[sys.argv.index("--t") + 1])
    args = [a for a in args if a != str(thr)]
ours = Image.open(args[0]).convert("RGB")
app = Image.open(args[1]).convert("RGB")
if ours.size != (1280, 744):
    ours = ours.resize((1280, 744), Image.LANCZOS)
if app.size != (1280, 744):
    app = app.resize((1280, 744), Image.LANCZOS)
a = np.asarray(ours).astype(int); b = np.asarray(app).astype(int)
dd = np.abs(a - b)
d = (dd[..., 0] * 299 + dd[..., 1] * 587 + dd[..., 2] * 114 + 500) // 1000     # PIL convert('L') of the difference image
mask = np.ones(d.shape, bool); mask[:, 1228:] = False
bad = (d > thr) & mask
print(f"diff>{thr}: {bad.sum()} / {d.size} = {100 * bad.sum() / d.size:.2f}%")   # denominator = all 1280x744 px, as cmp-accept.py
if len(args) > 2:
    Image.fromarray((bad * 255).astype(np.uint8)).save(args[2])
