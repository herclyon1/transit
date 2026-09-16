#!/usr/bin/env python3
"""Undersea feature names for the globe page (trenches, deeps, rises, seamount chains ...) -> map/data/undersea.geojson.

Source: GEBCO Gazetteer of Undersea Feature Names (IHO-IOC, hosted by NOAA NCEI), read through its public ArcGIS
feature service (https://www.gebco.net/data-products/undersea-feature-names lists the endpoints):
  https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/Undersea_Features/FeatureServer/{0,1,2}
  layer 0 Point_Features (2631), 1 Line_Features (1128), 2 Polygon_Features (1648); fields NAME, TYPE, FEATURE_ID.
Paged with resultOffset (maxRecordCount 2000), geometry as GeoJSON (f=geojson, WGS84).

Kept TYPEs and the globe class we give them (the App draws Ramapo Deep, Challenger Deep, Emperor Seamount Chain,
Shatsky Rise at globe zoom):
  class 1  Trench, Deep, Rise, Seamount Chain, Seamounts (chain), Fracture Zone
  class 2  Ridge, Plateau, Basin, Trough, Abyssal Plain, Escarpment
Everything else (single seamounts, banks, canyons ...) is dropped: 4,000+ names would be noise at globe scale.
Geometry: points as they are; lines as LineString; polygons collapsed to the centroid of their largest ring.
Every feature carries `rep` = [lng, lat] representative point, `type`, `cls`, `feature_id`, `geom_src` (point/line/polygon);
polygon features also `axis` = [[lng, lat], [lng, lat]], the polygon's long axis for spread (letter-spaced) text
and `label` = "NAME TYPE" (the gazetteer stores the specific term only: "Challenger" + "Deep").
Not in the gazetteer: "Ramapo Deep" (only a "Ramapo" Bank exists) — the App's Ramapo Deep label has no public source here.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'map', 'data', 'undersea.geojson')
RAW = os.path.join(ROOT, 'pipeline', 'basemap', 'raw', 'gebco_gazetteer')
SERVICE = 'https://services2.arcgis.com/C8EMgrsFcRFL6LrL/arcgis/rest/services/Undersea_Features/FeatureServer'
CLASS = {
    'Trench': 1, 'Deep': 1, 'Rise': 1, 'Seamount Chain': 1, 'Seamounts': 1, 'Fracture Zone': 1,
    'Ridge': 2, 'Plateau': 2, 'Basin': 2, 'Trough': 2, 'Abyssal Plain': 2, 'Escarpment': 2,
}


def fetch_layer(layer):
    """Download one layer as GeoJSON features, caching each page under raw/ (gitignored)."""
    os.makedirs(RAW, exist_ok=True)
    feats, offset = [], 0
    while True:
        cache = os.path.join(RAW, f'layer{layer}_{offset}.geojson')
        if os.path.exists(cache):
            page = json.load(open(cache))
        else:
            q = urllib.parse.urlencode({'where': '1=1', 'outFields': 'NAME,TYPE,FEATURE_ID', 'outSR': 4326,
                                        'resultOffset': offset, 'resultRecordCount': 2000, 'f': 'geojson'})
            with urllib.request.urlopen(f'{SERVICE}/{layer}/query?{q}', timeout=120) as r:
                page = json.load(r)
            json.dump(page, open(cache, 'w'))
        feats += page.get('features', [])
        if not page.get('properties', {}).get('exceededTransferLimit') and len(page.get('features', [])) < 2000:
            break
        offset += 2000
    return feats


def ring_area_centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        f = x0 * y1 - x1 * y0
        a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if abs(a) < 1e-12:
        xs, ys = zip(*ring)
        return 0.0, [sum(xs) / len(xs), sum(ys) / len(ys)]
    return abs(a) / 2, [cx / (3 * a), cy / (3 * a)]


def representative(geom):
    t, c = geom['type'], geom['coordinates']
    if t == 'Point':
        return c
    if t == 'MultiPoint':
        return c[0]
    if t in ('LineString', 'MultiLineString'):
        line = c if t == 'LineString' else max(c, key=len)
        return line[len(line) // 2]
    rings = [p[0] for p in c] if t == 'MultiPolygon' else [c[0]]
    return max((ring_area_centroid(r) for r in rings), key=lambda x: x[0])[1]


def label_axis(geom):
    """Two points [lng, lat] on the polygon's principal axis (PCA of the largest ring, in a local equirectangular frame),
    spanning the ring's extent along it: the App spreads the trench / basin / ridge name along the feature (the tile's
    label path); the UI lays the text along this segment (west-to-east ordered)."""
    import math
    rings = geom['coordinates'] if geom['type'] == 'Polygon' else max(geom['coordinates'], key=lambda p: len(p[0]))
    ring = max(rings, key=len)
    pts = [(float(x), float(y)) for x, y in (r[:2] for r in ring)]
    if len(pts) < 3:
        return None
    cx = sum(x for x, _ in pts) / len(pts); cy = sum(y for _, y in pts) / len(pts)
    k = math.cos(math.radians(cy))
    xs = [(x - cx) * k for x, _ in pts]; ys = [y - cy for _, y in pts]
    sxx = sum(x * x for x in xs); syy = sum(y * y for y in ys); sxy = sum(x * y for x, y in zip(xs, ys))
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(ang), math.sin(ang)
    t = [x * ux + y * uy for x, y in zip(xs, ys)]
    t0, t1 = min(t), max(t)
    a = [round(cx + t0 * ux / k, 3), round(cy + t0 * uy, 3)]; b = [round(cx + t1 * ux / k, 3), round(cy + t1 * uy, 3)]
    return [a, b] if a[0] <= b[0] else [b, a]


def main():
    out, counts = [], {}
    for layer, src in ((0, 'point'), (1, 'line'), (2, 'polygon')):
        for f in fetch_layer(layer):
            p = f['properties']
            cls = CLASS.get(p['TYPE'])
            if not cls or not f.get('geometry'):
                continue
            rep = [round(v, 4) for v in representative(f['geometry'])]
            geom = f['geometry']
            if src == 'point':
                geom = {'type': 'Point', 'coordinates': rep}
            elif src == 'polygon':
                geom = {'type': 'Point', 'coordinates': rep}
                axis = label_axis(f['geometry'])          # long axis of the polygon: the baseline for spread text
            else:
                geom = {'type': geom['type'], 'coordinates': json.loads(json.dumps(geom['coordinates']), parse_float=lambda s: round(float(s), 3))}
            props = {'name': p['NAME'], 'type': p['TYPE'], 'label': f"{p['NAME']} {p['TYPE']}",
                     'cls': cls, 'feature_id': p['FEATURE_ID'], 'geom_src': src, 'rep': rep}
            if src == 'polygon' and axis:
                props['axis'] = axis
            out.append({'type': 'Feature', 'geometry': geom, 'properties': props})
            counts[p['TYPE']] = counts.get(p['TYPE'], 0) + 1
    out.sort(key=lambda f: (f['properties']['cls'], f['properties']['type'], f['properties']['name']))
    fc = {'type': 'FeatureCollection',
          'source': {'name': 'GEBCO Gazetteer of Undersea Feature Names (IHO-IOC GEBCO, hosted by NOAA NCEI)',
                     'url': SERVICE, 'landing': 'https://www.gebco.net/data-products/undersea-feature-names',
                     'license': 'public (GEBCO gazetteer data are freely available)', 'generator': 'pipeline/basemap/undersea.py',
                     'classes': {'1': 'Trench, Deep, Rise, Seamount Chain, Seamounts, Fracture Zone', '2': 'Ridge, Plateau, Basin, Trough, Abyssal Plain, Escarpment'}},
          'features': out}
    json.dump(fc, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(out)} features -> {OUT} ({os.path.getsize(OUT)//1024} KB)')
    print('by type:', dict(sorted(counts.items(), key=lambda x: -x[1])))
    want = ('Ramapo', 'Challenger', 'Emperor', 'Shatsky', 'Japan Trench', 'Mariana', 'Kuril', 'Izu', 'Ryukyu', 'Philippine')
    print('checks:', [f"{f['properties']['name']} ({f['properties']['type']}, {f['properties']['geom_src']}) rep={f['properties']['rep']}" for f in out if any(w in f['properties']['name'] for w in want)])


if __name__ == '__main__':
    main()
