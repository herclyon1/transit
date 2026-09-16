#!/usr/bin/env python3
"""Acceptance metric: share of pixels where our render differs from the App screenshot by more than 40.

    python3 pipeline/basemap/cmpdiff.py <ours.png 1280x744> <app.png 2560x1488 or 1280x744> [out-diff.png]

Both images at 1280x744 (LANCZOS resample, as the acceptance session does), the App toolbar column
x > 1228 masked, per-pixel max(|dR|,|dG|,|dB|) > 40 counted. Same recipe as the acceptance
session's cmp2-diff.png (2026-09-16).
"""
import sys

import numpy as np
from PIL import Image

ours = Image.open(sys.argv[1]).convert("RGB")
app = Image.open(sys.argv[2]).convert("RGB")
if ours.size != (1280, 744):
    ours = ours.resize((1280, 744), Image.LANCZOS)
if app.size != (1280, 744):
    app = app.resize((1280, 744), Image.LANCZOS)
a = np.asarray(ours).astype(int); b = np.asarray(app).astype(int)
d = np.abs(a - b).max(2)
mask = np.ones(d.shape, bool); mask[:, 1228:] = False
bad = (d > 40) & mask
print(f"diff>40: {bad.sum()} / {mask.sum()} = {100 * bad.sum() / mask.sum():.2f}%")
if len(sys.argv) > 3:
    Image.fromarray((bad * 255).astype(np.uint8)).save(sys.argv[3])
