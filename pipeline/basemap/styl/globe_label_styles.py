#!/usr/bin/env python3
"""Resolved label styles of the globe sheet for the feature classes Apple names at globe zoom (RENDER-PIPELINE 2.8 /
basemap/data/globe/apple-globe-labels.md): the cascade resolved with resolve.py (Mac Elevated context, diamond=last),
one row per (style, property, zoom band).

    python3 pipeline/basemap/styl/globe_label_styles.py ~/Money/styl-work/globe-default-iosmac-6857.styl > basemap/data/globe/globe-label-styles.tsv
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resolve import Resolver  # noqa: E402
from styl_decode import prop_label, fmt_value  # noqa: E402

STYLES = [
    # physical line / area labels by Apple rank (= the tile zoom the feature first appears at, attribute 85)
    'PhysicalFeature-Rank-1-2-Globe', 'PhysicalFeature-Rank-3-5-Globe', 'PhysicalFeature-Rank-6-Globe', 'PhysicalFeature-Rank-7-Globe',
    'PhysicalFeature-Rank-8-9-Globe', 'PhysicalFeature-Rank-1-2-Island-Globe', 'PhysicalFeature-Rank-3-5-Island-Globe',
    # point classes
    'PhysicalFeature-Area-Points-Globe', 'PhysicalFeature-Region-Points-Globe', 'PhysicalFeature-Mountain-Points-Globe',
    'PhysicalFeature-Coastal-Points-Globe', 'PhysicalFeature-Island-Points-Globe', 'PhysicalFeature-Undersea-Points-Globe-Base',
    'PhysicalFeature-Undersea-Area-Points-Globe-Base', 'PhysicalFeature-Elevation-Points-Globe-Base',
    # water bodies, continents, cities
    'Ocean-Label-Point-ExtraLarge', 'Ocean-Label-Point-Large', 'Ocean-Label-Point-Medium', 'Ocean-Label-Point-Small', 'Ocean-Label-Point-ExtraSmall',
    'Ocean-Label-Line-Large', 'Ocean-Label-Line-Medium', 'Ocean-Label-Line-Small', 'Ocean-Label-Color-Globe-Base',
    'Continent-PointLabel-Globe', 'City-Globe-Base', 'City-Style-02', 'City-Style-03', 'City-Style-04', 'City-Style-05', 'City-Style-06',
]
PROPS = {1: 'fillColor', 18: 'textSizeScale', 23: 'fontSpec', 24: 'textColor', 25: 'labelHaloColor', 29: 'fontSizeParam', 33: 'labelTextVisibility',
         58: 'sizeRange', 59: 'dropShadowColor', 172: 'labelInfo', 187: 'labelDefaultTextPosition', 0: 'visible', 26: 'labelHaloWidth', 30: 'textCase',
         31: 'letterSpacing', 170: 'labelColorSource', 260: 'textElementMarginVertical', 12: 'opacity'}


def main():
    path = sys.argv[1]
    for mode, ctx in (('light', {'client': {69: 2, 1: 0}}), ('dark', {'client': {69: 2, 1: 1}})):
        r = Resolver(path, context=ctx)
        print('mode\tstyle\tprop\tzoom\tvalue' if mode == 'light' else '', end='\n' if mode == 'light' else '')
        for name in STYLES:
            if name not in r.by_name:
                print(f'{mode}\t{name}\t(not in sheet)\t\t', file=sys.stdout)
                continue
            for pid in sorted(PROPS):
                try:
                    bands = r.bands(name, pid)
                except Exception:
                    continue
                for zmin, zmax, v in bands:
                    if v is None:
                        continue
                    print(f'{mode}\t{name}\t{prop_label(pid)}\t{zmin:g}-{zmax:g}\t{fmt_value(v)}')


if __name__ == '__main__':
    main()
