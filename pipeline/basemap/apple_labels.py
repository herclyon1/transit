#!/usr/bin/env python3
"""Apple's globe-zoom label set (what the App names at Apple z2-6) as a reference table, and the join onto our public
layers so the UI can show the same features with the sheet's PhysicalFeature / Ocean / City classes.

    /tmp/spr_labels tiles.db 6 > pipeline/basemap/raw/apple-labels-raw.tsv     (pipeline/basemap/spr_labels.m)
    python3 pipeline/basemap/apple_labels.py                                  # from the repo root

Reads the raw dump (GEOVectorTile decode of the VECTOR_SPR_STANDARD tiles in the local cache copy: physical features
= label paths, pois = point labels) and writes
    ~/Money/styl-work/apple-data/apple-globe-labels.tsv   (outside the repo) one row per feature per tile: kind, name (native), type, subtype, minzoom,
                                                rank, lon/lat of the point or of the path's middle, the path itself
    ~/Money/styl-work/apple-data/apple-globe-labels-calibration.json   our features joined to Apple's label rows by name
                                                (outside the repo: calibration for the label rules only; map/data
                                                carries no apple_* field — user's rule 2026-09-17)
Attribute ids read off the decoded pairs (basemap/data/globe/apple-globe-labels.md): 5 FeatureType (3 point / 21 physical
line-area), 6 type (0 continent, 1 country, 2 state, 3 city, 130 capital, 180 island, 5 sea, 140 desert, 170 region,
221 water body, 428 undersea area, 430 mountains, 431 undersea ridge), 92 subtype, 85 min zoom (tile zoom at which the
feature first appears), 10 rank (cities / seas), 4 country.
"""
import collections
import json
import math
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'pipeline', 'basemap', 'raw', 'apple-labels-raw.tsv')
OUT_TSV = os.path.expanduser('~/Money/styl-work/apple-data/apple-globe-labels.tsv')   # Apple label data stays outside the repo
CALIB = os.path.expanduser('~/Money/styl-work/apple-data/apple-globe-labels-calibration.json')
TYPE6 = {'0': 'continent', '1': 'country', '2': 'state', '3': 'city', '5': 'sea', '130': 'capital', '180': 'island', '411': 'other-point',
         '140': 'desert', '170': 'region', '221': 'water', '223': 'plain', '424': 'undersea-424', '428': 'undersea-area', '430': 'mountains', '431': 'undersea-ridge'}
SUB92 = {'1': 'island group', '6': 'desert', '8': 'escarpment', '9': 'upland', '15': 'range', '17': 'plateau', '18': 'land basin', '31': 'basin', '32': 'peninsula',
         '35': 'ridge', '36': 'fan', '37': 'trench/trough', '39': 'rise', '41': 'shelf', '42': 'seascarp', '48': 'plain', '50': 'plain', '52': 'lowland', '56': 'reef'}


def lat_of(fy):
    return math.degrees(2 * math.atan(math.exp((0.5 - fy) * 2 * math.pi)) - math.pi / 2)


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\b(the|of|desert|mountains|mts|range|sea|ocean|trench|basin|ridge|plateau|plain|islands|island|bay|gulf|strait)\b', ' ', s)
    return ' '.join(s.split())


def main():
    rows = [l.rstrip('\n').split('\t') for l in open(RAW, encoding='utf-8')][1:]
    out = []
    for r in rows:
        if len(r) < 10:
            continue
        z, x, y, kind, idx, name, w1, w2, geom = int(r[0]), int(r[1]), int(r[2]), r[3], int(r[4]), r[5], r[6], r[7], r[8]
        if z < 2 or z > 6 or not name:
            continue
        attrs = dict(p.split('=') for p in (r[10] if len(r) > 10 else '').split() if '=' in p)
        n = 2 ** z
        if kind == 'poi':
            fx, fy = (float(v) for v in geom.split(','))
            lon = (x + fx) / n * 360 - 180; lat = lat_of((y + 1 - fy) / n)
            path = ''
        else:
            pts = [tuple(float(v) for v in p.split(',')) for p in geom.split(';') if p]
            if not pts:
                continue
            ll = [((x + fx) / n * 360 - 180, lat_of((y + 1 - fy) / n)) for fx, fy in pts]
            lon, lat = ll[len(ll) // 2]
            path = ';'.join(f'{a:.4f},{b:.4f}' for a, b in ll)
        out.append({'z': z, 'x': x, 'y': y, 'kind': kind, 'name': name, 'type': TYPE6.get(attrs.get('6'), attrs.get('6', '')),
                    'subtype': SUB92.get(attrs.get('92'), attrs.get('92', '')), 'minzoom': attrs.get('85', ''), 'rank': attrs.get('10', ''),
                    'country': attrs.get('4', ''), 'w1': w1, 'w2': w2, 'lon': round(lon, 4), 'lat': round(lat, 4), 'path': path, 'attrs': r[10] if len(r) > 10 else ''})
    cols = ['z', 'x', 'y', 'kind', 'name', 'type', 'subtype', 'minzoom', 'rank', 'country', 'w1', 'w2', 'lon', 'lat', 'path', 'attrs']
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        f.write('\t'.join(cols) + '\n')
        for o in sorted(out, key=lambda o: (o['z'], o['kind'], o['type'], o['name'])):
            f.write('\t'.join(str(o[c]) for c in cols) + '\n')
    print(f'{len(out)} rows -> {OUT_TSV}', file=sys.stderr)
    # the unique feature set per (kind, type, name) with its lowest zoom
    first = {}
    for o in out:
        k = (o['kind'], o['type'], o['name'])
        if k not in first or int(o['minzoom'] or 99) < int(first[k]['minzoom'] or 99):
            first[k] = o
    # join onto our layers by normalised name -> CALIBRATION FILE OUTSIDE THE REPO (user's rule 2026-09-17: Apple's per-feature
    # min-zoom / rank is tile content, not a rule; map/data carries only fields our own rules compute, checked against this file)
    def join(path, namekey, kinds):
        d = json.load(open(path, encoding='utf-8'))
        idx = collections.defaultdict(list)
        for k, o in first.items():
            if o['type'] in kinds:
                idx[norm(o['name'])].append(o)
        rows = []
        for ft in d['features']:
            p = ft['properties']
            cands = idx.get(norm(str(p.get(namekey) or p.get('name') or '')))
            if not cands:
                continue
            gx, gy = (ft['geometry']['coordinates'] if ft['geometry']['type'] == 'Point' else p.get('rep', [None, None])[::-1] if p.get('rep') else (None, None))
            best = min(cands, key=lambda o: (abs(o['lon'] - gx) + abs(o['lat'] - gy)) if gx is not None else 0)
            if gx is not None and abs(best['lon'] - gx) + abs(best['lat'] - gy) > 25:
                continue
            rows.append({'name': p.get(namekey) or p.get('name'), 'apple_name': best['name'], 'apple_minzoom': int(best['minzoom'] or 0),
                         'apple_type': best['type'] + ('/' + best['subtype'] if best['subtype'] else ''), 'apple_rank': int(best['rank']) if best['rank'] else None,
                         'ours': {k: v for k, v in p.items() if k not in ('name_zh', 'name_ja', 'rep', 'axis')}})
        print(f'{os.path.basename(path)}: {len(rows)} features matched', file=sys.stderr)
        return rows
    calib = {'what': 'Apple globe label set (z2-6) joined to our layers by name; calibration for the label rules (cities.py, undersea.py, physical) — never shipped',
             'physical': join(os.path.join(ROOT, 'map', 'data', 'physical.geojson'), 'name', {'desert', 'region', 'mountains', 'plain'}),
             'undersea': join(os.path.join(ROOT, 'map', 'data', 'undersea.geojson'), 'label', {'undersea-area', 'undersea-ridge', 'undersea-424'})}
    cities = os.path.join(ROOT, 'map', 'data', 'cities.geojson')
    if os.path.exists(cities):
        calib['cities'] = join(cities, 'name_en', {'city', 'capital'})
    # what Apple names that we have no feature for (English-looking names only)
    missing = [o for k, o in first.items() if o['kind'] == 'physical' and re.match(r'^[A-Za-z]', o['name'])]
    have = set()
    for path, key in (('physical.geojson', 'name'), ('undersea.geojson', 'label')):
        d = json.load(open(os.path.join(ROOT, 'map', 'data', path), encoding='utf-8'))
        have |= {norm(str(f['properties'].get(key) or '')) for f in d['features']}
    missing = sorted({o['name'] for o in missing if norm(o['name']) not in have})
    print(f'{len(missing)} Apple physical names without a match in physical/undersea.geojson: {missing[:40]}', file=sys.stderr)
    calib['unmatched_physical_names'] = missing
    calib['counts_by_zoom_kind_type'] = collections.Counter((o['z'], o['kind'], o['type']) for o in out).most_common()
    json.dump(calib, open(CALIB, 'w'), indent=1, ensure_ascii=False)
    print(f'calibration file -> {CALIB}', file=sys.stderr)


if __name__ == '__main__':
    main()
