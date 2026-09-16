#!/usr/bin/env python3
"""Physical-geography names for the globe page -> map/data/physical.geojson.

Three Natural Earth 10m inputs (public domain, https://naciscdn.org/naturalearth/10m/physical/...), unzipped under
pipeline/basemap/raw/ (gitignored):
  ne_regions_polys/ne_10m_geography_regions_polys      ranges, deserts, plateaus, plains, basins, peninsulas, islands ...
                                                        -> one Point per polygon at the largest ring's centroid (`kind` = FEATURECLA)
  ne_elev/ne_10m_geography_regions_elevation_points      named peaks and lows (Everest, K2, Gongga Shan, Dead Sea ...) with `elevation` m
  (equator / Tropic of Cancer / Tropic of Capricorn are generated, `kind` = 'Graticule'; NE graticules stop at whole degrees)
Islands and island groups are dropped (they have their own land shapes; the App does not name them at globe zoom).
Fields: name, name_zh, name_ja, kind, scalerank, min_label, max_label (NE's label zoom range), elevation (peaks only).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'pipeline', 'basemap'))
import nelib

RAW = os.path.join(ROOT, 'pipeline', 'basemap', 'raw')
OUT = os.path.join(ROOT, 'map', 'data', 'physical.geojson')
DROP = {'Island', 'Island group', 'Continent'}


def largest_ring_centroid(rings):
    best, best_area = None, -1
    for r in rings:
        a = abs(nelib.ring_area(r))
        if a > best_area:
            best_area, best = a, r
    x, y = best[:-1, 0], best[:-1, 1]
    x1, y1 = best[1:, 0], best[1:, 1]
    f = x * y1 - x1 * y
    area = f.sum() / 2
    if abs(area) < 1e-9:
        return [float(best[:, 0].mean()), float(best[:, 1].mean())]
    return [float(((x + x1) * f).sum() / (6 * area)), float(((y + y1) * f).sum() / (6 * area))]


def lname(r, k):
    return r.get(k) or r.get(k.upper()) or ''


def main():
    feats, counts = [], {}
    polys_base = os.path.join(RAW, 'ne_regions_polys', 'ne_10m_geography_regions_polys')
    for kind, rings, r in nelib.read_layer(polys_base):
        if kind != 'polygon' or r['FEATURECLA'] in DROP:
            continue
        c = largest_ring_centroid(rings)
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(c[0], 3), round(c[1], 3)]},
                      'properties': {'name': r['NAME'], 'name_zh': r.get('NAME_ZH', ''), 'name_ja': r.get('NAME_JA', ''),
                                     'kind': r['FEATURECLA'], 'scalerank': r['SCALERANK'], 'min_label': r.get('MIN_LABEL'), 'max_label': r.get('MAX_LABEL')}})
        counts[r['FEATURECLA']] = counts.get(r['FEATURECLA'], 0) + 1
    elev_base = os.path.join(RAW, 'ne_elev', 'ne_10m_geography_regions_elevation_points')
    for kind, pt, r in nelib.read_layer(elev_base):
        if kind != 'point':
            continue
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(float(pt[0]), 4), round(float(pt[1]), 4)]},
                      'properties': {'name': r['name'], 'name_zh': r.get('name_zh', ''), 'name_ja': r.get('name_ja', ''),
                                     'kind': 'Peak' if (r.get('elevation') or 0) >= 0 else 'Depression', 'scalerank': r['scalerank'],
                                     'min_label': r.get('min_zoom'), 'max_label': None, 'elevation': r.get('elevation')}})
        counts['Elevation point'] = counts.get('Elevation point', 0) + 1
    # equator and tropics: NE graticules only carry whole degrees (the tropics are at 23.44), and nelib does not read
    # polylines, so the three parallels are generated directly (straight lines in lng/lat)
    for lat, label in ((0.0, 'Equator'), (23.4367, 'Tropic of Cancer'), (-23.4367, 'Tropic of Capricorn')):
        coords = [[lng, lat] for lng in range(-180, 181, 2)]
        feats.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords},
                      'properties': {'name': label, 'name_zh': {'Equator': '赤道', 'Tropic of Cancer': '北回归线', 'Tropic of Capricorn': '南回归线'}[label],
                                     'name_ja': {'Equator': '赤道', 'Tropic of Cancer': '北回帰線', 'Tropic of Capricorn': '南回帰線'}[label],
                                     'kind': 'Graticule', 'scalerank': 0, 'min_label': 0, 'max_label': 24}})
        counts['Graticule'] = counts.get('Graticule', 0) + 1
    fc = {'type': 'FeatureCollection',
          'source': {'name': 'Natural Earth 10m geography_regions_polys v' + open(polys_base + '.VERSION.txt').read().strip()
                             + ', geography_regions_elevation_points v' + open(elev_base + '.VERSION.txt').read().strip()
                             + '; equator/tropics generated at 23.4367 deg (obliquity 2026)',
                     'urls': ['https://naciscdn.org/naturalearth/10m/physical/ne_10m_geography_regions_polys.zip',
                              'https://naciscdn.org/naturalearth/10m/physical/ne_10m_geography_regions_elevation_points.zip'],
                     'license': 'public domain', 'generator': 'pipeline/basemap/physical.py'},
          'features': feats}
    json.dump(fc, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(feats)} features -> {OUT} ({os.path.getsize(OUT)//1024} KB)')
    print('by kind:', dict(sorted(counts.items(), key=lambda x: -x[1])))
    ea = [f['properties']['name'] for f in feats if f['geometry']['type'] == 'Point' and 60 <= f['geometry']['coordinates'][0] <= 150
          and 20 <= f['geometry']['coordinates'][1] <= 55 and f['properties']['scalerank'] <= 3]
    print('East Asia scalerank<=3:', ea)


if __name__ == '__main__':
    main()
