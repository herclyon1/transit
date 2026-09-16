#!/usr/bin/env python3
"""City label points for the globe page: Natural Earth 10m populated places -> map/data/cities.geojson.

Source: https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip (public domain), unzipped to
pipeline/basemap/raw/ne_places/ (gitignored).

Globe-scale tiers (`globe_rank`), calibrated so that the East Asia view (#ll=30,125&spn=50,60, the App shows about
25 city names there) gets rank 1+2:
  1  SCALERANK 0-1                                   (Tokyo, Shanghai, Beijing, Hong Kong, Osaka, Seoul, Taipei ...)
  2  SCALERANK 2 with POP_MAX >= 3 M, or a national capital with SCALERANK <= 3
  3  SCALERANK <= 3 remainder, or POP_MAX >= 2 M
  4  SCALERANK <= 4
  5  SCALERANK 5-7
  6  SCALERANK 8-10
Only rank <= 4 is written by default (1148 points); `--all` keeps every tier (7342 points, 1.9 MB).
Fields: name, name_zh, name_ja, adm0, iso, capital (0/1), scalerank, pop_max, globe_rank, min_zoom (NE MIN_ZOOM).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'pipeline', 'basemap'))
import nelib

RAW = os.path.join(ROOT, 'pipeline', 'basemap', 'raw', 'ne_places', 'ne_10m_populated_places')
OUT = os.path.join(ROOT, 'map', 'data', 'cities.geojson')


def globe_rank(r):
    sr, pop, cap = r['SCALERANK'], r['POP_MAX'] or 0, 1 if r.get('ADM0CAP') == 1 else 0
    if sr <= 1:
        return 1
    if (sr == 2 and pop >= 3_000_000) or (cap and sr <= 3):
        return 2
    if sr <= 3 or pop >= 2_000_000:
        return 3
    if sr <= 4:
        return 4
    if sr <= 7:
        return 5
    return 6


def main():
    layer = nelib.read_layer(RAW)
    version = open(RAW + '.VERSION.txt').read().strip()
    feats = []
    for kind, pt, r in layer:
        if kind != 'point':
            continue
        feats.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [round(float(pt[0]), 4), round(float(pt[1]), 4)]},
            'properties': {
                'name': r['NAME'], 'name_zh': r.get('NAME_ZH') or '', 'name_ja': r.get('NAME_JA') or '',
                'adm0': r['ADM0NAME'], 'iso': r['ISO_A2'], 'capital': 1 if r.get('ADM0CAP') == 1 else 0,
                'scalerank': r['SCALERANK'], 'pop_max': r['POP_MAX'], 'globe_rank': globe_rank(r),
                'min_zoom': r.get('MIN_ZOOM'),
            },
        })
    feats.sort(key=lambda f: (f['properties']['globe_rank'], -(f['properties']['pop_max'] or 0)))
    max_rank = 6 if '--all' in sys.argv else 4          # the globe page never zooms past country level: rank <= 4 is enough
    feats = [f for f in feats if f['properties']['globe_rank'] <= max_rank]
    fc = {'type': 'FeatureCollection',
          'source': {'name': f'Natural Earth 10m populated places v{version}',
                     'url': 'https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip',
                     'license': 'public domain', 'generator': 'pipeline/basemap/cities.py',
                     'globe_rank': 'see cities.py header; rank 1+2 = the ~25 names the App shows on the East Asia globe view'},
          'features': feats}
    json.dump(fc, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    ea = [f for f in feats if 5 <= f['geometry']['coordinates'][1] <= 55 and 95 <= f['geometry']['coordinates'][0] <= 155]
    counts = {k: sum(1 for f in feats if f['properties']['globe_rank'] == k) for k in range(1, 7)}
    ea_counts = {k: sum(1 for f in ea if f['properties']['globe_rank'] == k) for k in range(1, 7)}
    print(f'{len(feats)} cities -> {OUT} ({os.path.getsize(OUT)//1024} KB); globe_rank counts {counts}; East Asia box {ea_counts}')
    print('East Asia rank 1-2:', ', '.join(f["properties"]["name"] for f in ea if f['properties']['globe_rank'] <= 2))


if __name__ == '__main__':
    main()
