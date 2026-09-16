#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""English names for the N02 railway lines in tiles/transit.pmtiles (layer `rail`, fields cls / n / op): adds `name_en`
so the UI can label lines in English (Japan-Railway-Label-Base / Bullet-Label-Base — the App writes "Sanyo Shinkansen").

    python3 pipeline/japan/rail_name_en.py            # from the repo root; OSM fetch cached in pipeline/japan/raw/

Source of the English: OpenStreetMap railway ways in Japan with `name:en` (121 000 ways, 1 238 distinct `name`s; ODbL,
Overpass, tags only).  N02 names are the operator's own short names (西日本旅客鉄道 「山陽線」, 阪急電鉄 「京都線」, 阪神
「本線」, 大阪市高速電気軌道 「1号線(御堂筋線)」) while OSM way names carry the operator and the 本 (「JR山陽本線」, 「阪急京都線」,
「阪神本線」, 「Osaka Metro御堂筋線」), so both sides are normalised: OSM names lose a leading operator prefix (PREFIXES or the
way's own operator tag), N02 names lose the 「N号線(…)」 wrapper, and 「X線」 / 「X本線」 are tried both ways; the operator
must agree when the OSM way carries one (N02 「東京都」 = OSM 「東京都交通局」 by prefix).  Each match takes the majority
`name:en` of the matching ways, macrons removed (Sanyō → Sanyo, as the App writes it); a leading "JR " is dropped for
shinkansen only (the App's "Sanyo Shinkansen").  The wording is OSM's, not Apple's — Apple's own transit label text is not
decoded yet (RENDER-PIPELINE §7.6).

The English is split into `op_en` (operator brand: JR, Hankyu, Osaka Metro, Kobe Electric Railway — OP_EN, else the
company part OSM wrote) and `name_en` (the line: Kyoto Line, Midosuji Line, Tokaido Main Line), so the UI composes every
label the same way — op_en + " " + name_en, or name_en alone where the App does (Sanyo Shinkansen).

Outputs: pipeline/japan/rail-name-en.tsv (every N02 line: op, n, cls, op_en, name_en, osm_name, how — the review sheet, in
the repo) and tiles/transit.pmtiles rewritten in place with `name_en` / `op_en` on every rail feature that has one
(mvt_retag.py; all other bytes of every tile are copied verbatim, the archive is re-serialised with the pmtiles package).
"""
import gzip
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mvt_retag as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'pipeline', 'japan', 'raw')
TILES = os.path.join(ROOT, 'tiles', 'transit.pmtiles')
TSV = os.path.join(ROOT, 'pipeline', 'japan', 'rail-name-en.tsv')
UA = 'transit-basemap/1.0 (github herclyon; railway line english names)'
BOX = '(24,122,46,154)'

# N02 operator -> short forms OSM puts in front of line names (only the ones N02 has; others fall back to the operator tag)
SHORT = {
    '東日本旅客鉄道': ['JR東日本', 'JR'], '西日本旅客鉄道': ['JR西日本', 'JR'], '東海旅客鉄道': ['JR東海', 'JR'], '九州旅客鉄道': ['JR九州', 'JR'],
    '北海道旅客鉄道': ['JR北海道', 'JR'], '四国旅客鉄道': ['JR四国', 'JR'], 'JR東海交通事業': ['JR東海交通事業'],
    '近畿日本鉄道': ['近鉄'], '阪急電鉄': ['阪急'], '阪神電気鉄道': ['阪神'], '南海電気鉄道': ['南海'], '京阪電気鉄道': ['京阪'],
    '名古屋鉄道': ['名鉄'], '東武鉄道': ['東武'], '西武鉄道': ['西武'], '京王電鉄': ['京王'], '京浜急行電鉄': ['京急', '京浜急行'],
    '京成電鉄': ['京成'], '東急電鉄': ['東急'], '小田急電鉄': ['小田急'], '相模鉄道': ['相鉄'], '西日本鉄道': ['西鉄'],
    '東京地下鉄': ['東京メトロ'], '東京都': ['都営地下鉄', '都営', '都電', '東京都交通局'],
    '大阪市高速電気軌道': ['Osaka Metro', '大阪メトロ', '大阪市営地下鉄', '大阪市交通局'],
    '名古屋市': ['名古屋市営地下鉄', '名古屋市交通局', '名古屋市営'], '京都市': ['京都市営地下鉄', '京都市交通局'], '神戸市': ['神戸市営地下鉄', '神戸市交通局'],
    '横浜市': ['横浜市営地下鉄', '横浜市交通局'], '福岡市': ['福岡市地下鉄', '福岡市営地下鉄', '福岡市交通局'], '仙台市': ['仙台市地下鉄', '仙台市営地下鉄', '仙台市交通局'],
    '札幌市': ['札幌市営地下鉄', '札幌市交通局'], '一般社団法人札幌市交通事業振興公社': ['札幌市電'], '熊本市': ['熊本市電', '熊本市交通局'],
    '鹿児島市': ['鹿児島市電', '鹿児島市交通局'], '函館市': ['函館市電', '函館市企業局'], '山陽電気鉄道': ['山陽電鉄', '山陽'],
    '神戸電鉄': ['神鉄'], '広島電鉄': ['広電'], '伊予鉄道': ['伊予鉄'], '富山地方鉄道': ['富山地鉄', '地鉄'], '京福電気鉄道': ['嵐電', '京福'],
    '叡山電鉄': ['叡電'], '能勢電鉄': ['能勢電'], '北大阪急行電鉄': ['北大阪急行', '北急'], '泉北高速鉄道': ['泉北'], '大阪モノレール': ['大阪モノレール'],
    '高松琴平電気鉄道': ['ことでん', '琴電'], '長崎電気軌道': ['長崎電鉄'], '筑豊電気鉄道': ['筑鉄'], '静岡鉄道': ['静鉄'], '遠州鉄道': ['遠鉄'],
    '伊豆箱根鉄道': ['伊豆箱根'], '豊橋鉄道': ['豊鉄'], '福井鉄道': ['福鉄'], '北陸鉄道': ['北鉄'], '上田電鉄': ['上田電鉄'], '長野電鉄': ['長電'],
    '秩父鉄道': ['秩父'], '新京成電鉄': ['新京成'], '北総鉄道': ['北総'], '首都圏新都市鉄道': ['つくばエクスプレス'], '東京モノレール': ['東京モノレール'],
    '横浜高速鉄道': ['横浜高速'], '江ノ島電鉄': ['江ノ電'], '箱根登山鉄道': ['箱根登山'], '小田急箱根': ['箱根登山'], '富士山麓電気鉄道': ['富士急行', '富士急'],
    '一畑電車': ['一畑'], '岡山電気軌道': ['岡電'], 'とさでん交通': ['とさでん'], '土佐くろしお鉄道': ['土佐くろしお'], 'WILLER　TRAINS': ['京都丹後鉄道', '丹鉄'],
    # renamed / differently named operators on the OSM side
    '大阪モノレール': ['大阪高速鉄道', '大阪モノレール'], '神戸六甲鉄道': ['六甲摩耶鉄道'], '阪堺電気軌道': ['阪堺電車', '阪堺'], 'アルピコ交通': ['松本電鉄', 'アルピコ'],
    '岳南電車': ['岳南鉄道'], '皿倉登山鉄道': ['帆柱'], '湘南モノレール': ['湘南モノレール'], '神戸新交通': ['神戸新交通'],
}
# N02 lines whose OSM name is not derivable by the rules (brand names, renumbered subway lines)
ALIAS = {
    ('神戸新交通', 'ポートアイランド線'): 'ポートライナー', ('神戸新交通', '六甲アイランド線'): '六甲ライナー', ('大阪市高速電気軌道', '南港ポートタウン線'): 'ニュートラム',
    ('東京臨海高速鉄道', '臨海副都心線'): 'りんかい線', ('首都圏新都市鉄道', '常磐新線'): 'つくばエクスプレス', ('ゆりかもめ', '東京臨海新交通臨海線'): 'ゆりかもめ',
    ('東京モノレール', '東京モノレール羽田線'): '東京モノレール', ('多摩都市モノレール', '多摩都市モノレール線'): '多摩都市モノレール',
    ('大阪モノレール', '大阪モノレール線'): '大阪モノレール本線', ('大阪モノレール', '国際文化公園都市モノレール線(彩都線)'): '彩都線',
    ('横浜市', '1号線'): '横浜市営1号線', ('横浜市', '3号線'): '横浜市営3号線', ('横浜市', '4号線'): '横浜市営地下鉄グリーンライン',
    ('神戸市', '西神線'): '西神・山手線', ('神戸市', '西神延伸線'): '西神・山手線', ('神戸市', '山手線'): '西神・山手線',
    ('京阪電気鉄道', '鋼索線'): '石清水八幡宮参道ケーブル', ('筑波観光鉄道', '筑波山鋼索鉄道線'): '筑波山ケーブルカー', ('鞍馬寺', '鞍馬山鋼索鉄道'): '鞍馬寺ケーブル',
    ('丹後海陸交通', '天橋立鋼索鉄道'): '天橋立鋼索鉄道', ('小田急箱根', '鋼索線'): '小田急箱根鋼索線', ('十国峠', '十国鋼索線'): '十国鋼索線',
    ('東京地下鉄', '4号線丸ノ内線分岐線'): '丸ノ内線', ('名古屋臨海高速鉄道', '西名古屋港線'): 'あおなみ線', ('岳南電車', '岳南鉄道線'): '岳南電車岳南線',
    ('新京成電鉄', '新京成線'): '新京成線',
}
# keys that name nothing without an operator (「本線」 of which company?) — only operator-tagged OSM objects may match them
GENERIC = {'本線', '鋼索線', '支線', '線', '鉄道線', '空港線', 'ケーブルカー', 'ケーブル線', '東西線', '南北線', '山手線', '中央線', '1号線', '2号線', '3号線', '4号線'}
# OSM name:en spellings corrected on the way through (typos / missing "Line"); the TSV marks these rows
EN_FIX = {'Senchimae Line': 'Sennichimae Line', 'Nagahori Tsurumi-Ryokuchi': 'Nagahori Tsurumi-ryokuchi Line', 'Hokuriu Railway Asanogawa Line': 'Hokuriku Railway Asanogawa Line',
          'Keihan Electoric Railway Keishin line': 'Keihan Keishin Line', 'Keihan Electoric Railway Ishiyama-sakamoto line': 'Keihan Ishiyama-Sakamoto Line',
          'Nagoya City Subway Higashi-yama line': 'Nagoya City Subway Higashiyama Line', 'Kumamoto City Tram. Tasaki-line': 'Kumamoto City Tram Tasaki Line',
          'Blue Line Yokohama subway': 'Yokohama Municipal Subway Blue Line', 'JR Connector Line Tokaido-Aonami/Chuo': 'Aonami Line',
          'Connector line Sotetsu - Shin-Yokohama': 'Sotetsu Shin-Yokohama Line', 'Keihan Electric Railway Katano-Line': 'Keihan Katano Line',
          'Keihan Electric Railway Oto-Line': 'Keihan Oto Line', 'Toyama Chihou Railway Main Line': 'Toyama Chiho Railway Main Line'}
# operator -> English brand / short name, the prefix OSM's name:en puts before the line name (Hankyu Kyoto Line, Osaka Metro
# Midosuji Line, Tokyo Metro Ginza Line); JR for the six JR companies.  Split off into `op_en` so every line carries the same
# two parts and the UI composes the label one way (op_en + name_en; the App writes "Sanyo Shinkansen" without JR).
OP_EN = {
    '東日本旅客鉄道': 'JR', '西日本旅客鉄道': 'JR', '東海旅客鉄道': 'JR', '九州旅客鉄道': 'JR', '北海道旅客鉄道': 'JR', '四国旅客鉄道': 'JR',
    '近畿日本鉄道': 'Kintetsu', '阪急電鉄': 'Hankyu', '阪神電気鉄道': 'Hanshin', '南海電気鉄道': 'Nankai', '京阪電気鉄道': 'Keihan', '名古屋鉄道': 'Meitetsu',
    '東武鉄道': 'Tobu', '西武鉄道': 'Seibu', '京王電鉄': 'Keio', '京浜急行電鉄': 'Keikyu', '京成電鉄': 'Keisei', '東急電鉄': 'Tokyu', '小田急電鉄': 'Odakyu',
    '相模鉄道': 'Sotetsu', '西日本鉄道': 'Nishitetsu', '東京地下鉄': 'Tokyo Metro', '東京都': 'Toei', '大阪市高速電気軌道': 'Osaka Metro',
    '名古屋市': 'Nagoya City Subway', '京都市': 'Kyoto City Subway', '神戸市': 'Kobe City Subway', '横浜市': 'Yokohama Municipal Subway',
    '福岡市': 'Fukuoka City Subway', '仙台市': 'Sendai Subway', '札幌市': 'Sapporo Subway', '山陽電気鉄道': 'Sanyo Electric Railway',
    '神戸電鉄': 'Kobe Electric Railway', '広島電鉄': 'Hiroden', '伊予鉄道': 'Iyotetsu', '富山地方鉄道': 'Toyama Chiho Railway', '京福電気鉄道': 'Keifuku',
    '叡山電鉄': 'Eizan', '能勢電鉄': 'Noseden', '北大阪急行電鉄': 'Kita-Osaka Kyuko', '泉北高速鉄道': 'Semboku', '大阪モノレール': 'Osaka Monorail',
    '高松琴平電気鉄道': 'Kotoden', '長崎電気軌道': 'Nagasaki Electric Tramway', '静岡鉄道': 'Shizuoka Railway', '遠州鉄道': 'Enshu Railway',
    '伊豆箱根鉄道': 'Izuhakone Railway', '豊橋鉄道': 'Toyohashi Railroad', '福井鉄道': 'Fukui Railway', '北陸鉄道': 'Hokuriku Railway',
    '長野電鉄': 'Nagano Electric Railway', '秩父鉄道': 'Chichibu Railway', '新京成電鉄': 'Shin-Keisei', '北総鉄道': 'Hokuso', '東京モノレール': 'Tokyo Monorail',
    '横浜高速鉄道': 'Yokohama Minatomirai Railway', '江ノ島電鉄': 'Enoden', '小田急箱根': 'Hakone Tozan', '富士山麓電気鉄道': 'Fujikyu',
    '一畑電車': 'Ichibata Electric Railway', '岡山電気軌道': 'Okaden', 'とさでん交通': 'Tosaden Kotsu', '土佐くろしお鉄道': 'Tosa Kuroshio Railway',
    'WILLER　TRAINS': 'Kyoto Tango Railway', '阪堺電気軌道': 'Hankai Tramway', '近江鉄道': 'Ohmi Railway', '三岐鉄道': 'Sangi Railway', '養老鉄道': 'Yoro Railway',
    '水間鉄道': 'Mizuma Railway', '和歌山電鐵': 'Wakayama Electric Railway', '嵯峨野観光鉄道': 'Sagano Scenic Railway', '神戸新交通': 'Kobe New Transit',
    '熊本市': 'Kumamoto City Tram', '鹿児島市': 'Kagoshima City Tram', '函館市': 'Hakodate City Tram', '一般社団法人札幌市交通事業振興公社': 'Sapporo Streetcar',
    '熊本電気鉄道': 'Kumamoto Electric Railway', '筑豊電気鉄道': 'Chikuho Electric Railroad', '関東鉄道': 'Kanto Railway', '流鉄': 'Ryutetsu',
}
COMPANY = re.compile(r'^(.+?\b(?:Railway|Railroad|Railways|Tramway|Transit|Monorail|Metro|Subway|Kotsu|Transportation|Express|Streetcar|Tram))\s+(.+\b(?:Line|Shinkansen|Liner|Lines))$')
SERVICE = re.compile(r'\s*[（(].*?[)）]\s*$')          # "(下り)", "(貨物線)" — dropped from OSM names before matching
PAREN = re.compile(r'[（(]([^()（）]*線)[)）]')          # "JR万葉まほろば線(桜井線)" -> also indexed as 桜井線


def strip_macrons(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def overpass(q):
    req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=700) as r:
                return json.load(r)
        except Exception as e:
            print('overpass:', e, file=sys.stderr)
            time.sleep(20)
    raise SystemExit('overpass failed')


def fetch_ways():
    """Railway ways with name:en (primary) and route / route_master relations with name:en (secondary, e.g. Nagoya subway
    whose ways carry no name:en); both cached in raw/."""
    os.makedirs(RAW, exist_ok=True)
    out = []
    for kind, cache, q in (
            ('way', 'osm-rail-ways.json', f'[out:json][timeout:600];way["railway"~"^(rail|subway|light_rail|tram|monorail|funicular|narrow_gauge)$"]["name:en"]{BOX};out tags;'),
            ('relation', 'osm-rail-routes.json', f'[out:json][timeout:300];(relation["type"="route_master"]["route_master"~"^(railway|train|subway|light_rail|tram|monorail|funicular)$"]{BOX};'
                                                 f'relation["type"="route"]["route"~"^(railway|train|subway|light_rail|tram|monorail|funicular)$"]{BOX};);out tags;')):
        path = os.path.join(RAW, cache)
        if os.path.exists(path):
            els = json.load(open(path))
        else:
            data = overpass(q)
            els = [{'name': e['tags'].get('name'), 'en': e['tags'].get('name:en'), 'op': e['tags'].get('operator')} for e in data['elements'] if e.get('tags', {}).get('name:en')]
            json.dump(els, open(path, 'w'), ensure_ascii=False)
        for e in els:
            e['kind'] = kind
        out += els
    return out


def norm_op(op):
    if not op:
        return ''
    op = re.sub(r'\s*[（(].*?[)）]', '', op).replace('株式会社', '').strip()
    return op.split(';')[0]


def op_agree(n02, osm):
    if not osm:
        return True
    if osm == n02 or osm.startswith(n02) or n02.startswith(osm):
        return True
    return any(osm.startswith(s) or s.startswith(osm) for s in SHORT.get(n02, []))


def build_index(ways):
    """(stripped OSM name) -> list of (operator, Counter(name:en)).  Stripped = name minus operator prefix / service suffix."""
    prefixes = sorted({p for v in SHORT.values() for p in v} | set(SHORT), key=len, reverse=True)
    idx = defaultdict(lambda: defaultdict(Counter))
    for w in ways:
        nm = w['name']
        if not nm:
            continue
        op = norm_op(w['op'])
        base = SERVICE.sub('', nm).strip()
        keys = {base}
        for p in [op] + prefixes if op else prefixes:
            if p and base.startswith(p) and len(base) > len(p) + 1:          # never a bare 「線」
                keys.add(base[len(p):])
        for m in PAREN.finditer(nm):
            keys.add(m.group(1))
        weight = 1 if w.get('kind') == 'way' else 0.01          # relations only decide when no way has the name
        for k in keys:
            idx[k][op][w['en']] += weight
    return idx


def n02_keys(n, op):
    """Candidate normalised names for an N02 line."""
    keys = []
    if (op, n) in ALIAS:
        keys.append(ALIAS[(op, n)])
    m = re.match(r'^\d+号線[（(](.+?)[)）]$', n) or re.match(r'^\d+号線(.+線)$', n)
    core = m.group(1) if m else n
    cores = [core]
    for s_ in SHORT.get(op, []):                       # 阪神なんば線 -> なんば線, 相鉄本線 -> 本線
        if core.startswith(s_) and len(core) > len(s_):
            cores.append(core[len(s_):])
    m = PAREN.search(n)
    if m:
        cores.append(m.group(1))
    for c in cores + [n]:
        if c not in keys:
            keys.append(c)
        if c.endswith('線') and not c.endswith('本線') and len(c) > 1:
            keys.append(c[:-1] + '本線')
        if c.endswith('本線'):
            keys.append(c[:-2] + '線')
    # operator-qualified spellings (「本線」 alone is only meaningful with the operator)
    for s_ in SHORT.get(op, []) + [op]:
        for c in list(keys):
            keys.append(s_ + c)
    # last resort: the whole railway is named after its operator (伊豆急行, ゆりかもめ, 秩父鉄道)
    keys += [op] + SHORT.get(op, [])
    return keys


def match(n, op, cls, idx):
    for key in n02_keys(n, op):
        if key not in idx or len(key) < 2:
            continue
        cands = [(o, c) for o, c in idx[key].items() if op_agree(op, o) and (o or key not in GENERIC)]
        # an untagged way whose name:en is another operator's (神戸高速線: 阪急 / 阪神 / 神鉄 each have one) belongs to that operator
        others = {en for o, c in idx[key].items() if o and not op_agree(op, o) for en in c}
        cands = [(o, c) for o, c in cands if o or c.most_common(1)[0][0] not in others]
        if not cands:
            continue
        # most votes wins; ways without an operator tag count half
        cands.sort(key=lambda oc: -sum(oc[1].values()) * (1 if oc[0] else 0.5))
        en, votes = cands[0][1].most_common(1)[0]
        how = 'alias' if ALIAS.get((op, n)) == key else ('exact' if key == n else ('operator-named' if key in [op] + SHORT.get(op, []) else 'norm'))
        return en, key, how + ('' if cands[0][0] else ' (no operator on way)') + (' (relation)' if votes < 1 else '')
    return None, None, None


def clean_en(en, cls, n=''):
    """OSM name:en -> label text: macrons off, trailing parenthetical (directions, nicknames) off, a leading "JR " off
    unless the Japanese name itself carries it (JR東西線), known typos fixed."""
    en = strip_macrons(en)
    en = re.sub(r'\s*[（(].*?[)）]\s*$', '', en)
    en = re.sub(r'\s+', ' ', en).strip()
    fixed = en in EN_FIX
    en = EN_FIX.get(en, en)
    en = re.sub(r'\bline$', 'Line', en)
    if 'JR' not in n:
        en = re.sub(r'^JR\s+', '', en)
    return en, fixed


def split_op(en, op, cls=''):
    """(op_en, line) — the operator's English brand split off the front of the OSM name (Hankyu Kyoto Line -> Hankyu, Kyoto
    Line; Kobe Electric Railway Arima Line -> Kobe Electric Railway, Arima Line).  op_en is empty when the line's own name
    already carries the brand (Keihan Main Line, Tokyu-Toyoko Line, Hokuso Line), when the name is the whole railway
    (Tokyo Monorail), and for shinkansen (the App writes "Sanyo Shinkansen", no JR)."""
    brand = OP_EN.get(op, '')
    m = COMPANY.match(en)
    if m and m.group(2) not in ('Line', 'Main Line'):
        brand, en = (brand or m.group(1)), m.group(2)
    elif brand and en.lower().startswith(brand.lower() + ' ') and en[len(brand) + 1:] != 'Line':
        en = en[len(brand) + 1:]
    if not brand or en == brand or re.match(re.escape(brand) + r'[\s\-]', en, re.I) or cls == 'shinkansen':
        return '', en
    return brand, en


def main():
    from pmtiles.reader import Reader, MmapSource, all_tiles
    from pmtiles.writer import Writer
    from pmtiles.tile import zxy_to_tileid
    ways = fetch_ways()
    idx = build_index(ways)
    # the N02 line set, from the tiles themselves
    f = open(TILES, 'rb')
    r = Reader(MmapSource(f))
    header, meta = r.header(), r.metadata()
    lines = Counter()
    tiles = []
    for (z, x, y), data in all_tiles(r.get_bytes):
        tiles.append((zxy_to_tileid(z, x, y), data))
        for L in M.read_tile(gzip.decompress(data)):
            if L.name == 'rail':
                for ft in L.features:
                    p = L.props(ft)
                    lines[(p.get('op') or '', p.get('n') or '', p.get('cls') or '')] += 1
    table = {}
    rows = []
    for (op, n, cls), cnt in sorted(lines.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1])):
        en, key, how = match(n, op, cls, idx)
        op_en = OP_EN.get(op, '')
        if en:
            en, fixed = clean_en(en, cls, n)
            how += ' (spelling fixed)' if fixed else ''
            op_en, en = split_op(en, op, cls)
            table[(op, n)] = {'name_en': en, 'op_en': op_en} if op_en else {'name_en': en}
        rows.append((op, n, cls, op_en, en or '', key or '', how or 'unmatched', cnt))
    with open(TSV, 'w') as t:
        t.write('op\tn\tcls\top_en\tname_en\tosm_name\thow\tsegments_in_tiles\n')
        for row in rows:
            t.write('\t'.join(str(c) for c in row) + '\n')
    matched = sum(1 for r_ in rows if r_[4])
    print(f'{matched}/{len(rows)} lines matched; unmatched by class:', Counter(r_[2] for r_ in rows if not r_[4]))
    # rewrite the archive
    tmp = TILES + '.tmp'
    out = open(tmp, 'wb')
    w = Writer(out)
    changed = 0
    for tid, data in sorted(tiles, key=lambda t_: t_[0]):
        raw = gzip.decompress(data)
        layers = M.read_tile(raw)
        new = []
        for L in layers:
            if L.name != 'rail':
                new.append(None)
                continue
            nb, c = L.rewrite(lambda p: table.get((p.get('op') or '', p.get('n') or '')))
            new.append(nb if c else None)
            changed += c
        if any(nb is not None for nb in new):
            data = gzip.compress(M.write_tile(raw, new), mtime=0)
        w.write_tile(tid, data)
    for vl in meta.get('vector_layers', []):
        if vl['id'] == 'rail':
            vl['fields']['name_en'] = 'String'
            vl['fields']['op_en'] = 'String'
    meta['rail_name_en'] = {'source': 'OpenStreetMap railway ways name:en (ODbL), matched to N02 operator + line name by pipeline/japan/rail_name_en.py',
                            'matched_lines': matched, 'lines': len(rows), 'date': time.strftime('%Y-%m-%d')}
    w.finalize(header, meta)
    out.close()
    f.close()
    os.replace(tmp, TILES)
    print(f'{changed} rail features tagged; {TILES} rewritten')


if __name__ == '__main__':
    main()
