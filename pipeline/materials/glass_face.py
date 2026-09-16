#!/usr/bin/env python3
"""The face step of CoreAnimation's `glassBackground` filter (Liquid Glass), as decoded from QuartzCore.

Sources (MATERIALS.md §4 "How the filter composites them"):
  - shader: QuartzCore.framework/Resources/default.metallib, `glass_background_*_lpf` → `glass_background_base`
    (max-luma compression, then the 3x4 face colour matrix, mixed by FaceOpacity);
  - matrix builder: CA::ColorMatrix::set_ycc_composite(white, black, saturation, fillColor) in the shared-cache
    QuartzCore — Rec.709 RGB→YCbCr, Y' = black + (white − black)·Y, Cb'/Cr' = 0.5 + sat·(C − 0.5), YCbCr→RGB,
    then fillColor composited source-over.

Usage:
  glass_face.py                       # print the CSS equivalents of every §4 parameter set
  glass_face.py R G B [variant]       # run one backdrop colour (0–255) through a variant (default: regular-light)
"""
import sys

LUMA = (0.2126, 0.7152, 0.0722)
R2Y = ((0.2126, 0.7152, 0.0722), (-0.1146, -0.3854, 0.5), (0.5, -0.4542, -0.0458))   # QuartzCore literal pool
Y2R = ((1.0, 0.0, 1.5748), (1.0, -0.1873, -0.4681), (1.0, 1.8556, 0.0))

# (White, Black, Saturation, FillColor rgba 0–1, MaxLumaSDR) per §4 variant
VARIANTS = {
    'regular-light': (0.96, 0.4, 1.2, (1, 1, 1, 0.2), 1.0),
    'regular-dark': (1.125, 0.08, 1.3, (0, 0, 0, 0), 0.35),
    'clear-light': (0.95, 0.2, 1.0, (1, 1, 1, 0.1), 1.0),        # also the NSPopover frame
    'clear-dark': (0.8, 0.05, 1.0, (1, 1, 1, 0.05), 1.0),
    'sidebar-light': (1.03, 0.4, 1.2, (1, 1, 1, 0.2), 0.85),
    'sidebar-dark': (0.5, 0.1, 0.6, (0, 0, 0, 0), 1.0),
    'search-dark': (1.125, 0.08, 1.3, (0, 0, 0, 0), 0.6),
}


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def face(rgb255, white, black, sat, fill, lmax=1.0):
    c = [x / 255 for x in rgb255]
    y = dot(LUMA, c)
    if lmax < 1:                                   # step 4: soft max-luma compression
        k = min(1.0, max(0.0, 1 - y * (1 - lmax)))
        c = [k * (y + (x - y) * (1 + 0.3 * (1 - k))) for x in c]
        y = dot(LUMA, c)
    ycc = [dot(R2Y[i], c) for i in range(3)]      # step 5: luma levels + chroma saturation in Rec.709 YCbCr
    ycc[0] = black + (white - black) * ycc[0]
    ycc[1] *= sat
    ycc[2] *= sat
    rgb = [dot(Y2R[i], ycc) for i in range(3)]
    fr, fg, fb, fa = fill
    rgb = [(1 - fa) * v + fa * f for v, f in zip(rgb, (fr, fg, fb))]
    return tuple(int(round(min(1, max(0, v)) * 255)) for v in rgb)


def css(white, black, sat):
    """contrast(c) brightness(b) reproduce Y' = black + slope·Y per channel; saturate(sat/slope) restores the chroma."""
    slope = white - black
    c = 0.5 * slope / (0.5 * slope + black)
    b = slope / c
    return f'contrast({c:.3f}) brightness({b:.3f}) saturate({sat / slope:.3f})'


def main(argv):
    if len(argv) >= 4:
        rgb = tuple(int(v) for v in argv[1:4])
        name = argv[4] if len(argv) > 4 else 'regular-light'
        w, bk, s, fill, lmax = VARIANTS[name]
        print(name, rgb, '->', face(rgb, w, bk, s, fill, lmax), '(no MaxLuma:', face(rgb, w, bk, s, fill), ')')
        return
    for name, (w, bk, s, fill, lmax) in VARIANTS.items():
        extra = '' if lmax >= 1 else f'  + MaxLuma {lmax}: brightness(1 − {1 - lmax:.2f}·Ȳ) first'
        print(f'{name:14s} {css(w, bk, s)}  background: rgba({int(fill[0]*255)},{int(fill[1]*255)},{int(fill[2]*255)},{fill[3]}){extra}')
    sea = (104, 161, 198)   # App sea under the Map Modes popover, native-mapmodes.png
    print('check: clear-light over', sea, '->', face(sea, *VARIANTS['clear-light']), 'App rgb(135,181,211)')


if __name__ == '__main__':
    main(sys.argv)
