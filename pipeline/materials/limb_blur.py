#!/usr/bin/env python3
"""Measure the glass blur from the globe limb under the Maps sidebar (MATERIALS.md §4, BlurRadius vs backdrop scale).

The sidebar glass sits over the left limb of the globe in the acceptance globe shot; the sea -> black-space edge is
sharp outside the glass and smeared under it. The 10-90 % rise of the luma profile across the limb is the blur width:
a box of B points rises over 0.8*B, a Gaussian of sigma over 2.56*sigma.

Usage: limb_blur.py native.png [cx cy R]     (2x screenshot; camera circle from palette-globe.json by default)
"""
import sys

import numpy as np
from PIL import Image


def main(path, cx=1265.02, cy=743.4, R=1156.3):
    im = np.asarray(Image.open(path).convert('RGB')).astype(float)
    Y = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
    for y in (700, 900):                          # rows of the sidebar without text (800 has a label on it)
        xl = cx - np.sqrt(R * R - (y - cy) ** 2)
        p = Y[y, :400]
        lo, hi = p[:40].mean(), p[200:260].mean()
        t10, t90 = lo + 0.1 * (hi - lo), lo + 0.9 * (hi - lo)
        xs = np.arange(400)
        band = xs[(p > t10) & (p < t90) & (xs < 260)]
        print(f'row {y}: limb at x={xl:.0f}px, luma {lo:.0f} -> {hi:.0f}, 10-90 % rise x {band.min()}..{band.max()} = '
              f'{band.max() - band.min()} px @2x = {(band.max() - band.min()) / 2:.0f} pt  '
              f'(box {(band.max() - band.min()) / 2 / 0.8:.0f} pt / gaussian sigma {(band.max() - band.min()) / 2 / 2.563:.1f} pt)')
    xr = cx + np.sqrt(R * R - (743 - cy) ** 2)
    print('reference, right limb outside any glass (row 743):', [round(Y[743, x]) for x in range(int(xr) - 24, int(xr) + 12, 4)])


if __name__ == '__main__':
    args = [float(a) for a in sys.argv[2:5]]
    main(sys.argv[1], *args)
