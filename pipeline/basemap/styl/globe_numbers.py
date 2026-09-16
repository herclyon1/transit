#!/usr/bin/env python3
"""Curated number table for the globe style sheet: colours / widths / font sizes of the styles that draw on the globe.

Reads the full TSV produced by `styl_decode.py FILE.styl --tsv` and keeps the properties we can name with confidence:
  1 fill colour, 2 stroke colour (kDefaultStrokeColor), 3 width, 6 stroke width, 21 font size (pt), 23 font spec,
  24 text colour, 25 text halo colour (kDefaultLabelHaloColor), 29/18 label size factors, 32 label spacing.
Usage: globe_numbers.py IN.tsv OUT.tsv
"""
import sys

KEEP = {'1': 'fill', '2': 'stroke', '3': 'width', '6': 'strokeWidth', '21': 'fontSize', '23': 'font', '24': 'textColor',
        '25': 'haloColor', '18': 'textScale?', '29': 'haloWidth?', '32': 'labelSpacing', '57': 'glowColor?', '55': 'glowWidth?'}
GLOBE_WORDS = ('globe', 'ocean', 'continent', 'country', 'border', 'coastline', 'rivers', 'lake', 'physicalfeature', 'capitalcity', 'city-', 'state')


def main(src, dst):
    n = 0
    with open(src) as f, open(dst, 'w') as o:
        o.write('style\tsource\tzoom\tcondition\tprop_id\tmeaning\ttype\tvalue\n')
        next(f)
        for line in f:
            style, score, source, zoom, cond, pset, pid, prop, typ, value = line.rstrip('\n').split('\t')
            if pid not in KEEP:
                continue
            name = style.lower()
            if not any(w in name for w in GLOBE_WORDS):
                continue
            o.write('\t'.join([style, source, zoom, cond, pid, KEEP[pid], typ, value]) + '\n')
            n += 1
    print(f'{n} rows -> {dst}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
