#!/usr/bin/env python3
"""Curated number table for the globe style sheet: colours / widths / font sizes of the styles that draw on the globe.

Reads the full TSV produced by `styl_decode.py FILE.styl --tsv` and keeps the properties we can name with confidence
(see inferred_names.py): fill/stroke colour, width, stroke width, font size, font spec, text colour, text halo colour,
text size scale, label spacing, coastline glow width/colour, grid colour.
Usage: globe_numbers.py IN.tsv OUT.tsv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inferred_names import name_of

KEEP = {str(i): name_of(i) for i in (1, 2, 3, 6, 21, 23, 24, 25, 18, 29, 32, 55, 57, 203)}
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
