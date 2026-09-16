#!/usr/bin/env python3
"""Zoom-levelled bathymetry for the globe page: three GeoJSON files instead of one 12 MB file.

Same source and same output format as globe-data.py's bathy.geojson (12 features, one MultiPolygon per Natural
Earth depth level, property `depth`), only the simplification differs per level of detail:

  file                  for zoom   DP tolerance   min ring area   decimals   size
  bathy-z0.geojson      < 4        0.2 deg         0.1 deg^2       2          1.1 MB    (first screen, globe radius 536 px)
  bathy-z4.geojson      4-6        0.05 deg        0.005 deg^2     3          6.9 MB
  bathy.geojson         >= 6       0.02 deg        0.002 deg^2     3          12 MB     (globe-data.py, unchanged)

At the first-screen view (#ll=30,125&spn=50,60, zoom 3.1) one degree is ~9 px, so a 0.2 deg tolerance is
about 1.8 px: nothing visible is lost.  The page swaps the source by zoom (setData) — the three files share
depth values, so the 12 `bathy-<depth>` layers need no change.

Source: Natural Earth 10m Bathymetry (pipeline/basemap/raw/ne_bathy, from
https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip, public domain).
pmtiles was not used: tippecanoe/node are not installed on this Mac (the japan pipeline ran it on a Linux box),
and at globe zoom three GeoJSON levels reach the 3-second target without a tile server.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nelib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'pipeline', 'basemap', 'raw', 'ne_bathy')
OUT = os.path.join(ROOT, 'map', 'data')
NE_LEVELS = [('L', 0), ('K', 200), ('J', 1000), ('I', 2000), ('H', 3000), ('G', 4000),
             ('F', 5000), ('E', 6000), ('D', 7000), ('C', 8000), ('B', 9000), ('A', 10000)]
LEVELS = [('bathy-z0.geojson', 0.2, 0.1, 2), ('bathy-z4.geojson', 0.05, 0.005, 3)]


def build(name, tol, min_area, decimals):
    t0 = time.time()
    feats, total = [], 0
    for letter, depth in NE_LEVELS:
        base = os.path.join(RAW, f'ne_10m_bathymetry_{letter}_{depth}')
        coords = []
        for kind, rings, rec in nelib.read_layer(base):
            if kind != 'polygon':
                continue
            s = nelib.simplify_polygon(rings, tol, min_area)
            if s:
                coords += nelib.rings_to_geojson_polygons(s, decimals)
        feats.append({'type': 'Feature', 'properties': {'depth': depth}, 'geometry': {'type': 'MultiPolygon', 'coordinates': coords}})
        total += sum(len(p[0]) for p in coords)
    path = os.path.join(OUT, name)
    fc = {'type': 'FeatureCollection', 'features': feats,
          'source': {'name': 'Natural Earth 10m Bathymetry v' + open(os.path.join(RAW, 'ne_10m_bathymetry_L_0.VERSION.txt')).read().strip(),
                     'url': 'https://naciscdn.org/naturalearth/10m/physical/ne_10m_bathymetry_all.zip', 'license': 'public domain',
                     'generator': 'pipeline/basemap/bathy-levels.py', 'simplification': {'douglas_peucker_deg': tol, 'min_ring_area_deg2': min_area, 'decimals': decimals}}}
    json.dump(fc, open(path, 'w'), separators=(',', ':'))
    print(f'{name}: {total} outer vertices, {os.path.getsize(path)//1024} KB, {time.time()-t0:.0f}s')


if __name__ == '__main__':
    for args in LEVELS:
        build(*args)
