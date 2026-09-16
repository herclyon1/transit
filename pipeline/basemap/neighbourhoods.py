#!/usr/bin/env python3
"""Neighbourhood names for the z11-13 flat map (the App's small uppercase names at Osaka z12: NAGASU, KANDA, JUSO, HONJO =
`Neighborhood-Base-Small`, Apple z12+ = MapLibre z11+) -> map/data/neighbourhoods.geojson.

    python3 pipeline/basemap/neighbourhoods.py            # run from the repo root (Overpass, cached in raw/osm/)

Source: OpenStreetMap `place=suburb|quarter|neighbourhood` in the Keihanshin box lat 34.3-35.1 / lng 135.0-135.9 (Osaka,
Kobe, Kyoto, Nara — the acceptance views).  OpenFreeMap's z12 `place` layer only carries `suburb` (OpenMapTiles adds
quarter / neighbourhood from z14), hence the direct query.  In Japan OSM tags every 町丁目 (chome block) as
place=neighbourhood (21 600 nodes in the box, 11 600 of them "N丁目"), while the App labels the 町 / district level, so
the nodes are folded in two steps and each output feature says which level it is:

  level "block"    = one 町 / 大字: chome nodes with the same base name (「N丁目」 stripped) within 2 km, centre = mean of
                     the members; quarters and non-chome neighbourhoods are blocks of one member.
  level "district" = blocks whose base names are a common stem + a directional / 町-type suffix (東/西/南/北/中/本町/元町/
                     東通 …, list SUFFIXES) within 2.5 km, e.g. 長洲東通+長洲本通+長洲中通+長洲西通 -> 長洲 NAGASU,
                     十三東+十三本町 -> 十三 JUSO, 本庄+本庄東+本庄中+本庄西 -> 本庄 HONJO — the App's z12 names.
  level "ward"     = place=suburb (区), kept for completeness (the UI has its own ward layer).

English: OSM name:en (23 016 of 23 018 have it), else name:ja-Latn / name:ja_rm; chome numbers stripped for blocks, the
common hyphen/space-separated stem for districts; macrons removed (the App writes Osaka / Kyoto / Juso without them).
Suggested zoom (MapLibre): district 11, block with >= 3 chome 12, other blocks 13 (Neighborhood-Base-Small is visible from
Apple z12 = MapLibre z11); `rank` = member count for collision priority.  The folding is this script's rule, not Apple's
data — it is checked against the four App names above, nothing more.
"""
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'pipeline', 'basemap', 'raw', 'osm')
OUT = os.path.join(ROOT, 'map', 'data', 'neighbourhoods.geojson')
BOX = (34.3, 135.0, 35.1, 135.9)          # S, W, N, E
OVERPASS = 'https://overpass-api.de/api/interpreter'
UA = 'transit-basemap/1.0 (github herclyon; neighbourhood names)'
CHOME_JA = re.compile('[一二三四五六七八九十百〇0-9０-９]+丁目?$')                 # 「三丁目」, Sakai's 「三丁」
CHOME_EN = re.compile(r'[\s\-]*\d+(?:[\s\-]*(?:ch[oō]me|cho))?$', re.I)      # "3-chome", "3 Chome", "3-cho", "3"
# 町-name suffix -> its romanisations (OSM name:en spells them with or without a hyphen)
SUFFIXES = {'東': ['higashi'], '西': ['nishi'], '南': ['minami'], '北': ['kita'], '中': ['naka'], '上': ['kami', 'ue'], '下': ['shimo'],
            '本町': ['honmachi'], '元町': ['motomachi'], '新町': ['shinmachi'], '東通': ['higashidori'], '西通': ['nishidori'],
            '中通': ['nakadori'], '南通': ['minamidori'], '北通': ['kitadori'], '本通': ['hondori'], '通': ['dori'],
            '東町': ['higashimachi'], '西町': ['nishimachi'], '南町': ['minamimachi'], '北町': ['kitamachi'], '中町': ['nakamachi'],
            '上町': ['uemachi', 'kamimachi'], '下町': ['shimomachi'], '町': ['machi', 'cho']}
BLOCK_KM, DISTRICT_KM = 2.0, 2.5


def fetch():
    os.makedirs(RAW, exist_ok=True)
    cache = os.path.join(RAW, 'places-keihanshin.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    sel = f'["place"~"^(suburb|quarter|neighbourhood)$"]["name"]({BOX[0]},{BOX[1]},{BOX[2]},{BOX[3]})'
    q = f'[out:json][timeout:120];(node{sel};way{sel};relation{sel};);out center tags;'
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
            json.dump(data, open(cache, 'w'))
            return data
        except Exception as e:
            print('overpass:', e, file=sys.stderr)
            time.sleep(10)
    raise SystemExit('overpass failed')


def ascii_name(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).strip()


def km(a, b):
    dx = (a[0] - b[0]) * 111.32 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot(dx, (a[1] - b[1]) * 111.32)


def cluster(items, key, limit_km):
    """Group items (dicts with 'key' and 'xy') that share `key` and lie within limit_km of a member (union-find)."""
    by = defaultdict(list)
    for it in items:
        by[key(it)].append(it)
    groups = []
    for k, its in by.items():
        parent = list(range(len(its)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i in range(len(its)):
            for j in range(i + 1, len(its)):
                if km(its[i]['xy'], its[j]['xy']) <= limit_km:
                    parent[find(i)] = find(j)
        g = defaultdict(list)
        for i, it in enumerate(its):
            g[find(i)].append(it)
        groups.extend(g.values())
    return groups


def stem(ja):
    """(stem, suffix) if `ja` = stem + one of SUFFIXES (stem >= 2 chars), else (ja, None)."""
    for s in sorted(SUFFIXES, key=len, reverse=True):
        if ja.endswith(s) and len(ja) - len(s) >= 2:
            return ja[:-len(s)], s
    return ja, None


def en_stem(en, suffix):
    """English stem of a block whose Japanese name is stem + suffix: the romanised suffix removed from the end, else None."""
    for r in SUFFIXES[suffix]:
        m = re.search(r'[\s\-]*' + r + '$', en, re.I)
        if m and m.start() >= 2:
            return en[:m.start()]
    return None


def common_stem(names):
    toks = [re.split(r'[\s\-]+', n) for n in names]
    out = []
    for parts in zip(*toks):
        if len(set(p.lower() for p in parts)) == 1:
            out.append(parts[0])
        else:
            break
    return '-'.join(out)


def main():
    data = fetch()
    nodes, counts = [], Counter()
    for el in data['elements']:
        t = el.get('tags', {})
        place = t.get('place')
        if place not in ('suburb', 'quarter', 'neighbourhood'):
            continue
        en = t.get('name:en') or t.get('name:ja-Latn') or t.get('name:ja_rm')
        if not en:
            counts['no english'] += 1
            continue
        lon, lat = (el['lon'], el['lat']) if el['type'] == 'node' else (el['center']['lon'], el['center']['lat'])
        ja = t['name']
        base_ja = CHOME_JA.sub('', ja) if place == 'neighbourhood' else ja
        base_en = ascii_name(CHOME_EN.sub('', en) if base_ja != ja else en)
        if not base_ja or not base_en:               # bare "1丁目" / "2-chome" nodes without a 町 name
            counts['no name'] += 1
            continue
        nodes.append({'place': place, 'ja': ja, 'en': ascii_name(en), 'key': base_ja, 'base_en': base_en, 'xy': (lon, lat),
                      'chome': base_ja != ja, 'id': f"{el['type'][0]}{el['id']}"})
        counts[place] += 1
    wards = [n for n in nodes if n['place'] == 'suburb']
    blocks = []
    for g in cluster([n for n in nodes if n['place'] != 'suburb'], lambda n: n['key'], BLOCK_KM):
        xs = [n['xy'][0] for n in g]
        ys = [n['xy'][1] for n in g]
        en = Counter(n['base_en'] for n in g).most_common(1)[0][0]
        key, suffix = stem(g[0]['key'])
        blocks.append({'ja': g[0]['key'], 'en': en, 'xy': (sum(xs) / len(xs), sum(ys) / len(ys)), 'members': len(g), 'chome': sum(n['chome'] for n in g),
                       'place': g[0]['place'], 'ids': [n['id'] for n in g], 'key': key, 'suffix': suffix})
    districts, used = [], set()
    for g in cluster(blocks, lambda b: b['key'], DISTRICT_KM):
        if len(g) < 2:
            continue
        # English stem: a member that is the bare stem (本庄), else the members' English with the romanised suffix removed
        # (Imazunaka - naka), else the common hyphen/space-separated head, else the first member's head token
        cands = [b['en'] for b in g if b['suffix'] is None] + [e for b in g if b['suffix'] for e in [en_stem(b['en'], b['suffix'])] if e]
        en = (Counter(cands).most_common(1)[0][0] if cands else '') or common_stem([b['en'] for b in g]) or re.split(r'[\s\-]+', g[0]['en'])[0]
        w = [b['members'] for b in g]
        xy = (sum(b['xy'][0] * m for b, m in zip(g, w)) / sum(w), sum(b['xy'][1] * m for b, m in zip(g, w)) / sum(w))
        districts.append({'ja': g[0]['key'], 'en': en, 'xy': xy, 'members': sum(w), 'blocks': [b['ja'] for b in g], 'ids': sum((b['ids'] for b in g), [])})
        used.update(id(b) for b in g)
    feats = []

    def feat(xy, props):
        feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(xy[0], 5), round(xy[1], 5)]}, 'properties': props})
    for w in wards:
        feat(w['xy'], {'name': w['en'], 'name_ja': w['ja'], 'level': 'ward', 'place': 'suburb', 'min_zoom': 10, 'rank': 0, 'osm': w['id']})
    for d in districts:
        feat(d['xy'], {'name': d['en'], 'name_ja': d['ja'], 'level': 'district', 'place': 'neighbourhood', 'min_zoom': 11, 'rank': d['members'],
                       'blocks': '|'.join(d['blocks']), 'osm': d['ids'][0]})
    for b in blocks:
        props = {'name': b['en'], 'name_ja': b['ja'], 'level': 'block', 'place': b['place'], 'min_zoom': 12 if b['chome'] >= 3 else 13, 'rank': b['members'], 'osm': b['ids'][0]}
        if id(b) in used:
            props['district'] = b['key']
        feat(b['xy'], props)
    feats.sort(key=lambda f: (f['properties']['min_zoom'], -f['properties']['rank'], f['properties']['name']))
    fc = {'type': 'FeatureCollection',
          'source': {'name': 'OpenStreetMap place=suburb/quarter/neighbourhood (nodes, way/relation centres), Keihanshin box, folded to 町 / district by pipeline/basemap/neighbourhoods.py',
                     'license': 'ODbL', 'url': OVERPASS, 'fetched': time.strftime('%Y-%m-%d'), 'box_swne': BOX,
                     'levels': {'ward': 'place=suburb', 'district': f'blocks sharing a stem + suffix in {list(SUFFIXES)} within {DISTRICT_KM} km',
                                'block': f'chome nodes with the same base name within {BLOCK_KM} km; quarters / plain neighbourhoods as they are'},
                     'counts': {'input': dict(counts), 'ward': len(wards), 'district': len(districts), 'block': len(blocks)}},
          'features': feats}
    json.dump(fc, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f"{len(feats)} features -> {OUT}; input {dict(counts)}; wards {len(wards)} districts {len(districts)} blocks {len(blocks)} "
          f"(z12 {sum(1 for b in blocks if b['chome'] >= 3)})")


if __name__ == '__main__':
    main()
