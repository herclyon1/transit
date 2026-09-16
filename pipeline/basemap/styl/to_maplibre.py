#!/usr/bin/env python3
"""Generate MapLibre style JSON from Apple's flat style sheet (default-*.styl) — numbers straight from the decode,
nothing hand-tuned.

  to_maplibre.py ~/Money/styl-work/default-iosmac-11358.styl map/style-flat-light.json map/style-flat-dark.json [--lum] [--zoom-offset -1]

Which .styl: `default-iosmac-*.styl` is what Maps on the Mac (and MKMapSnapshotter) renders — same colours and zoom bands
as the iOS `default-*.styl`, all sizes (widths, text) x1.2987 (= 100/77).  Use the iOS file for phone-sized numbers.

Zoom: Apple's zoom is 256-px-tile based, MapLibre's is 512-px based, so Apple z = MapLibre z + 1.  Every band edge,
minzoom and text-size stop is shifted by --zoom-offset (default -1).  Check: the acceptance render
ll=34.69,135.50 spn=0.12,0.2 at 1280x744 is Apple z12.8 (log2(360*744/(0.146*256))) and MapLibre z11.8.

Data source is OpenFreeMap's `planet` tiles (OpenMapTiles schema).  MAPPING below pairs each OpenMapTiles layer +
filter with the Apple leaf style whose values it should take (`.Light-JPN` / `.Dark-JPN` road variants for Japan,
`.Explore-Light` / `.Explore-Dark` for areas), and says which pairings are inferred.  The mapping table is also
written next to the style as map/style-flat-mapping.tsv.

What is taken from Apple (via resolve.Resolver, cascade + zoom bands):
  fillColor(1) / strokeColor(2)      -> fill-color / line-color, casing line-color
  width(3) / strokeWidth(6)          -> line-width; casing = width + 2 * strokeWidth (casing is drawn under the fill)
  visible(0) False bands             -> layer minzoom (first zoom where the style is not hidden)
  12 (border opacity, inferred)      -> line-opacity on boundaries
  labelInfo.height / heightCurveLimit-> text-size: linear from height at the band start to the curve limit at its end
  textColor(24) / labelHaloColor(25) -> text-color / text-halo-color
  fontSpec(23)                       -> Noto Sans Regular | Bold | Italic (OpenFreeMap serves only these three)
  buildingFlatColor(86)              -> building fill
  dashPattern 279 / 280              -> line-dasharray on the fill / casing line (LE u16 pairs dash,gap in pt, divided by
                                        the line width at Apple z13 because MapLibre dash units are line widths)
With --lum the *ColorLumAdjustment values (463/464/470/471) are applied as an HSL lightness offset of adj/100;
the exact function VectorKit uses is unknown, so this is off by default.
"""
import colorsys
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve import Resolver

TILES = 'https://tiles.openfreemap.org/planet'
ZOFF = -1.0     # Apple zoom -> MapLibre zoom
GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
NAME = ['coalesce', ['get', 'name:ja'], ['get', 'name:zh'], ['get', 'name']]

# (id, kind, source-layer, filter, apple style template ({m} = Light/Dark, {e} = Explore-Light/Explore-Dark), note)
# kind: bg | fill | road | rail | line | boundary | place | roadname | watername
MAPPING = [
    ('background', 'bg', None, None, 'LandPolygon.{e}', 'land fill = background (OpenMapTiles has no land polygon)'),
    ('landcover-wood', 'fill', 'landcover', ['in', 'class', 'wood'], 'Landcover-Forest.{m}-Explore', 'OpenMapTiles wood ~ Apple Forest (inferred)'),
    ('landcover-grass', 'fill', 'landcover', ['in', 'class', 'grass', 'farmland'], 'Landcover-Herbaceous.{m}-Explore', 'grass/farmland ~ Herbaceous (inferred)'),
    ('landcover-sand', 'fill', 'landcover', ['in', 'class', 'sand'], 'Landcover-Sand.{m}-Explore', ''),
    ('landuse-residential', 'fill', 'landuse', ['in', 'class', 'residential', 'suburb', 'neighbourhood'], 'ResidentialPolygon-TintBand.{e}', 'tint band only in Apple; used as flat fill (inferred)'),
    ('landuse-commercial', 'fill', 'landuse', ['in', 'class', 'commercial', 'retail'], 'CommercialPolygon.{e}', ''),
    ('landuse-hospital', 'fill', 'landuse', ['in', 'class', 'hospital'], 'HospitalPolygon.{e}', ''),
    ('landuse-school', 'fill', 'landuse', ['in', 'class', 'school', 'university', 'college'], 'UniversityPolygon.{e}', 'school ~ University (inferred)'),
    ('landuse-cemetery', 'fill', 'landuse', ['in', 'class', 'cemetery'], 'CemeteryPolygon.{e}', ''),
    ('landuse-stadium', 'fill', 'landuse', ['in', 'class', 'stadium', 'pitch', 'playground'], 'StadiumPolygon.{e}', 'pitch/playground ~ Stadium (inferred)'),
    ('park', 'fill', 'park', None, 'ParkPolygon.{e}', ''),
    ('landuse-park', 'fill', 'landuse', ['in', 'class', 'park', 'recreation_ground', 'garden'], 'ParkPolygon.{e}', ''),
    ('aeroway', 'fill', 'aeroway', ['in', 'class', 'aerodrome', 'apron'], 'AirportPolygon.{e}', ''),
    ('water', 'fill', 'water', None, 'Landcover-Water.{m}-Explore', ''),
    ('waterway', 'line', 'waterway', ['in', 'class', 'river', 'canal', 'stream'], 'Rivers-{m}-Flat-Base', 'no dotted leaf for rivers; Flat-Base variant (inferred)'),
    ('building', 'building', 'building', None, 'BuildingFootprint.{m}-Explore', 'fill = buildingFlatColor(86), outline = strokeColor'),
    ('road-path', 'road', 'transportation', ['in', 'class', 'path', 'track'], 'Line-PrivatePath.{m}', 'path/track ~ PrivatePath (inferred)'),
    ('road-service', 'road', 'transportation', ['in', 'class', 'service'], 'Line-ServiceRoad.{m}', ''),
    ('road-minor', 'road', 'transportation', ['in', 'class', 'minor'], 'Line-LocalRoad-MinorRoad.{m}-JPN', ''),
    ('road-tertiary', 'road', 'transportation', ['in', 'class', 'tertiary'], 'Line-LocalMajorRoad.{m}-JPN', 'tertiary ~ LocalMajorRoad (inferred)'),
    ('road-secondary', 'road', 'transportation', ['in', 'class', 'secondary'], 'Line-ConnectorRoad.{m}-JPN', 'secondary ~ ConnectorRoad (inferred)'),
    ('road-primary', 'road', 'transportation', ['in', 'class', 'primary'], 'Line-Highway.{m}-JPN', 'primary ~ Highway (inferred)'),
    ('road-trunk', 'road', 'transportation', ['in', 'class', 'trunk'], 'Line-MajorHighway.{m}-JPN', 'trunk ~ MajorHighway (inferred)'),
    ('road-motorway', 'road', 'transportation', ['in', 'class', 'motorway'], 'Line-FreewayControlled.{m}-JPN', 'motorway ~ FreewayControlled'),
    ('rail', 'rail', 'transportation', ['all', ['==', 'class', 'rail'], ['!=', 'brunnel', 'tunnel']], 'Railway-Japan.{m}', ''),
    ('boundary-state', 'boundary', 'boundary', ['all', ['==', 'admin_level', 4], ['!=', 'maritime', 1]], 'Border-State.{e}', '12 = opacity (inferred)'),
    ('boundary-country', 'boundary', 'boundary', ['all', ['==', 'admin_level', 2], ['!=', 'maritime', 1]], 'Border-Country.Non-Disputed-{m}', ''),
    ('label-road-minor', 'roadname', 'transportation_name', ['in', 'class', 'minor', 'service', 'tertiary'], 'Line-LocalRoad-MinorRoad.{m}-JPN', 'road label numbers come from the road style itself'),
    ('label-road-secondary', 'roadname', 'transportation_name', ['in', 'class', 'secondary'], 'Line-ConnectorRoad.{m}-JPN', ''),
    ('label-road-primary', 'roadname', 'transportation_name', ['in', 'class', 'primary', 'trunk'], 'Line-Highway.{m}-JPN', ''),
    ('label-road-motorway', 'roadname', 'transportation_name', ['in', 'class', 'motorway'], 'Line-FreewayControlled.{m}-JPN', ''),
    ('label-water-lake', 'watername', 'water_name', ['in', 'class', 'lake'], 'Lake-Label.Zoom9-{m}', 'Zoom9 variant for city-scale lakes (inferred)'),
    ('label-water-ocean', 'watername', 'water_name', ['in', 'class', 'ocean', 'sea', 'bay'], 'Ocean-Points.Large-Explore-{m}', 'Large size class (inferred)'),
    ('label-ward', 'place', 'place', ['in', 'class', 'suburb', 'quarter', 'neighbourhood'], 'SubMuni-Ward.{m}', 'suburb/quarter ~ 区 ward (inferred)'),
    ('label-village', 'place', 'place', ['in', 'class', 'village', 'hamlet'], 'City-Label-LMZ-12.{m}', 'LMZ = label min zoom; village ~ LMZ-12 (inferred)'),
    ('label-town', 'place', 'place', ['in', 'class', 'town'], 'City-Label-LMZ-09.{m}', 'town ~ LMZ-09 (inferred)'),
    ('label-city', 'place', 'place', ['all', ['==', 'class', 'city'], ['>', 'rank', 3]], 'City-Label-LMZ-07.{m}', 'city rank>3 ~ LMZ-07 (inferred)'),
    ('label-city-large', 'place', 'place', ['all', ['==', 'class', 'city'], ['<=', 'rank', 3]], 'City-Label-LMZ-05.{m}', 'city rank<=3 ~ LMZ-05 (inferred)'),
    ('label-state', 'place', 'place', ['in', 'class', 'state', 'province'], 'State-Label-Medium.{m}', ''),
    ('label-country', 'place', 'place', ['in', 'class', 'country'], 'Country-Label-Medium.{m}', ''),
]


def rgba(v, lum=0.0):
    r, g, b, a = v['rgba']
    if lum:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        l = min(1.0, max(0.0, l + lum / 100))
        r, g, b = (round(x * 255) for x in colorsys.hls_to_rgb(h, l, s))
    return f'rgba({r},{g},{b},{a / 255:.3g})'


def step(bands, conv, lo=0.0, hi=24.0):
    """Piecewise-constant bands -> MapLibre step expression (or a constant when there is one band)."""
    bands = [(a, b, v) for a, b, v in bands if v is not None and b > lo and a < hi]
    if not bands:
        return None
    if len(bands) == 1:
        return conv(bands[0][2])
    expr = ['step', ['zoom'], conv(bands[0][2])]
    for a, b, v in bands[1:]:
        expr += [max(0.0, a + ZOFF), conv(v)]
    return expr


class Gen:
    def __init__(self, path, lum):
        self.src = path
        self.r = Resolver(path)
        self.lum = lum
        self.rows = []

    def adj(self, name, pid):
        return self.r.value_at(name, pid, 12) or 0.0 if self.lum else 0.0

    def minzoom(self, name):
        """First zoom from which visible(0) is never False; None when never hidden."""
        vis = [(a, b, v) for a, b, v in self.r.bands(name, 0) if v is False]
        if not vis:
            return None
        return max(0.0, max(b for a, b, v in vis) + ZOFF)

    def color_expr(self, name, pid, adj_pid=None):
        lum = self.adj(name, adj_pid) if adj_pid else 0.0
        return step(self.r.bands(name, pid), lambda v: rgba(v, lum))

    def width_expr(self, name, casing=False):
        w = {(a, b): v for a, b, v in self.r.bands(name, 3)}
        s = {(a, b): v for a, b, v in self.r.bands(name, 6)}
        edges = sorted({e for k in list(w) + list(s) for e in k})
        bands = []
        for a, b in zip(edges, edges[1:]):
            wv = self.r.value_at(name, 3, a) or 0.0
            sv = self.r.value_at(name, 6, a) or 0.0
            v = round(wv + 2 * sv if casing else wv, 3)
            if bands and bands[-1][2] == v:
                bands[-1] = (bands[-1][0], b, v)
            else:
                bands.append((a, b, v))
        return step(bands, lambda v: v)

    def text_size_expr(self, name):
        """labelInfo.height with the in-band curve to heightCurveLimit -> interpolate expression."""
        bands = [(a, b, v) for a, b, v in self.r.bands(name, 172) if isinstance(v, dict) and 'height' in v]
        if not bands:
            fs = self.r.value_at(name, 21, 12)
            return fs if fs else 12
        stops = []
        for a, b, v in bands:
            h, lim = v['height'], v.get('heightCurveLimit')
            stops.append((max(0.0, a + ZOFF), h))
            if lim is not None and lim != h:
                stops.append((max(0.01, min(b, 24) + ZOFF - 0.01), lim))
        expr = ['interpolate', ['linear'], ['zoom']]
        last = None
        for z, v in stops:
            if last is not None and z <= last:
                z = last + 0.01
            expr += [round(z, 2), v]
            last = z
        return expr

    def dash(self, name, pid, casing=False):
        """dashPattern (279 fill / 280 casing): LE u16 (dash, gap) pairs in pt -> MapLibre line-dasharray (line widths)."""
        v = self.r.value_at(name, pid, 13)
        pairs = v.get('dash') if isinstance(v, dict) else None
        if not pairs:
            return None
        w = (self.r.value_at(name, 3, 13) or 0.0) + (2 * (self.r.value_at(name, 6, 13) or 0.0) if casing else 0.0)
        if w <= 0 or len(pairs) < 2 or all(x == 0 for x in pairs[1::2]):
            return None                                   # (4, 0) = solid
        return [round(x / w, 2) for x in pairs]

    def font(self, name):
        spec = self.r.value_at(name, 23, 12) or ''
        if 'italic' in spec:
            return ['Noto Sans Italic']
        if 'bold' in spec or 'semibold' in spec:
            return ['Noto Sans Bold']
        return ['Noto Sans Regular']

    def note(self, lid, kind, style, text):
        self.rows.append((lid, kind, style, text))

    def layer(self, lid, kind, src, flt, style, mode):
        r = self.r
        if style not in r.by_name:
            self.note(lid, kind, style, 'MISSING style')
            return []
        base = {'id': lid, 'source': 'openmaptiles', 'source-layer': src}
        if flt:
            base['filter'] = flt
        mz = self.minzoom(style)
        if mz:
            base['minzoom'] = mz
        out = []
        if kind == 'bg':
            return [{'id': lid, 'type': 'background', 'paint': {'background-color': self.color_expr(style, 1, 470)}}]
        if kind == 'fill':
            c = self.color_expr(style, 1, 470)
            if c is None:
                self.note(lid, kind, style, 'no fillColor')
                return []
            return [{**base, 'type': 'fill', 'paint': {'fill-color': c, 'fill-antialias': False}}]
        if kind == 'building':
            fill = self.color_expr(style, 86) or self.color_expr(style, 1)
            l = {**base, 'type': 'fill', 'paint': {'fill-color': fill}}
            oc = self.color_expr(style, 2, 471)
            if oc:
                l['paint']['fill-outline-color'] = oc
            return [l]
        if kind in ('road', 'rail', 'line'):
            fc, sc = self.color_expr(style, 1, 470), self.color_expr(style, 2, 471)
            layout = {'line-cap': 'round', 'line-join': 'round'}
            if sc and (self.r.value_at(style, 6, 14) or 0) > 0:
                paint = {'line-color': sc, 'line-width': self.width_expr(style, casing=True)}
                d = self.dash(style, 280, casing=True)
                if d:
                    paint['line-dasharray'] = d
                out.append({**base, 'id': lid + '-casing', 'type': 'line', 'layout': layout, 'paint': paint})
            if fc:
                paint = {'line-color': fc, 'line-width': self.width_expr(style)}
                d = self.dash(style, 279)
                if d:
                    paint['line-dasharray'] = d
                out.append({**base, 'type': 'line', 'layout': layout, 'paint': paint})
            if kind == 'rail' and out:
                out[-1]['layout'] = {'line-join': 'round'}
            return out
        if kind == 'boundary':
            fc = self.color_expr(style, 1, 470)
            paint = {'line-color': fc, 'line-width': self.width_expr(style)}
            op = self.r.value_at(style, 12, 12)
            if op is not None:
                paint['line-opacity'] = op
            d = self.dash(style, 279)
            if d:
                paint['line-dasharray'] = d
            return [{**base, 'type': 'line', 'paint': paint}]
        if kind in ('place', 'watername', 'roadname'):
            tc, hc = self.color_expr(style, 24, 463), self.color_expr(style, 25, 464)
            layout = {'text-field': NAME, 'text-font': self.font(style), 'text-size': self.text_size_expr(style)}
            if kind == 'roadname':
                layout.update({'symbol-placement': 'line', 'text-rotation-alignment': 'map', 'symbol-spacing': 400})
            else:
                layout['text-max-width'] = 8
            paint = {'text-color': tc or '#000'}
            if hc:
                paint.update({'text-halo-color': hc, 'text-halo-width': 1.5})
            return [{**base, 'type': 'symbol', 'layout': layout, 'paint': paint}]
        return []

    def style(self, mode):
        m, e = ('Light', 'Explore-Light') if mode == 'light' else ('Dark', 'Explore-Dark')
        layers = []
        roads_casing, roads_fill = [], []
        for lid, kind, src, flt, tpl, note in MAPPING:
            name = tpl.format(m=m, e=e)
            ls = self.layer(lid, kind, src, flt, name, mode)
            self.note(lid, kind, name, note)
            if kind == 'road':
                for l in ls:
                    (roads_casing if l['id'].endswith('-casing') else roads_fill).append(l)
            else:
                if kind == 'rail':
                    roads_fill += ls        # rail above roads, like Apple's renderOrder 13 vs 5-6
                else:
                    layers += ls
        # order: background, areas, water, waterway, building, then all road casings, all road fills, rail, boundaries, labels
        pre = [l for l in layers if l['type'] != 'symbol' and l['id'] not in ('boundary-state', 'boundary-country')]
        bounds = [l for l in layers if l['id'] in ('boundary-state', 'boundary-country')]
        labels = [l for l in layers if l['type'] == 'symbol']
        return {'version': 8, 'name': f'Apple flat {mode} (generated from {Path(self.src).name})',
                'metadata': {'generator': 'pipeline/basemap/styl/to_maplibre.py', 'apple_style_sheet': Path(self.src).name,
                             'zoom_offset': ZOFF, 'lum_adjustment_applied': self.lum,
                             'region': 'Japan road variants (.Light-JPN / .Dark-JPN), Explore areas'},
                'sources': {'openmaptiles': {'type': 'vector', 'url': TILES}},
                'glyphs': GLYPHS, 'layers': pre + roads_casing + roads_fill + bounds + labels}


def main(argv):
    global ZOFF
    lum = '--lum' in argv
    if '--zoom-offset' in argv:
        i = argv.index('--zoom-offset'); ZOFF = float(argv[i + 1]); del argv[i:i + 2]
    argv = [a for a in argv if a != '--lum']
    src, out_light, out_dark = argv[1], argv[2], argv[3]
    g = Gen(src, lum)
    for mode, out in (('light', out_light), ('dark', out_dark)):
        s = g.style(mode)
        Path(out).write_text(json.dumps(s, indent=1, ensure_ascii=False))
        print(f'{out}: {len(s["layers"])} layers')
    tsv = Path(out_light).with_name('style-flat-mapping.tsv')
    with open(tsv, 'w') as f:
        f.write('layer\tkind\tapple_style\tnote\n')
        seen = set()
        for row in g.rows:
            if row not in seen:
                seen.add(row)
                f.write('\t'.join(row) + '\n')
    print(f'{tsv}: {len(seen)} rows')


if __name__ == '__main__':
    main(sys.argv)
