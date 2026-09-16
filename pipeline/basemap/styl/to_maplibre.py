#!/usr/bin/env python3
"""Generate MapLibre style JSON from Apple's flat style sheet (default-*.styl) — numbers straight from the decode,
nothing hand-tuned.

  to_maplibre.py ~/Money/styl-work/default-iosmac-11358.styl map/style-flat-light.json map/style-flat-dark.json [--lum] [--flat] [--zoom-offset -1]

Variants: by default the "-Elevated" leaf styles are used (Maps on the Mac and MKMapSnapshotter with
elevationStyle .realistic draw those: elevated expressways purple (185,174,209), ground Landcover-Ground (247,246,242));
--flat picks the plain Explore/Light variants (elevationStyle .flat).

Which .styl: use the iOS `default-56689.styl`.  The Mac sheet `default-iosmac-*.styl` has the same colours and zoom bands
with every size x1.2987 (= 100/77), but the Mac renders it at 77 %: measured on the acceptance render (Hanshin expressway
~5 px = iOS 3.75 + 2x0.5; ward caps 12 px = iOS 16 pt; rail 1-2 px = iOS 1.0), so the iOS numbers ARE the Mac pixels.

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
  labelInfo.height / heightCurveLimit-> text-size: linear from height at the band start to the curve limit at its end
  textColor(24) / labelHaloColor(25) -> text-color / text-halo-color
  fontSpec(23)                       -> Noto Sans Regular | Bold | Italic (OpenFreeMap serves only these three)
  buildingFlatColor(86)              -> building fill
  dashPattern 279 / 280              -> line-dasharray on the fill / casing line, per zoom band (step expression):
                                        each unit is DASH_PT = 0.2 pt on the Mac's output (three measurements, RENDER-PIPELINE
                                        §7.16), divided by the band's line width because MapLibre dash units are line widths
v6 (2026-09-16, RENDER-PIPELINE §7.12): dashes by zoom band; coastline glow (Coastline-Glow-*, width prop 55, colour 57,
  on the water side of the ocean polygons); fonts by zoom band; expressways below Apple z8 from the Line-LowZoom-Connection
  rows (§7.15) instead of the JPN width table the resolver picks; Geolines-Tropics/-Equator from map/data/graticule.geojson.
With --lum the *ColorLumAdjustment values (463/464/470/471) are applied as an HSL lightness offset of adj/100.
Off by default and measured to be wrong for labels: the ward text sampled on the Mac render is (90,93,93) = the sheet's
(90,94,94) although the style carries labelColorLumAdjustment -15, and dark wards went white with +10.
"""
import colorsys
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve import Resolver

TILES = 'https://tiles.openfreemap.org/planet'
ZOFF = -1.0     # Apple zoom -> MapLibre zoom
ELEVATED = True  # prefer the "-Elevated" leaf variants: Maps on the Mac / MKMapSnapshotter(.realistic) draw those
GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
NAME = ['coalesce', ['get', 'name:ja'], ['get', 'name']]      # ja, else local name (acceptance 2026-09-16: no zh fallback)
ROAD_RANK = {'label-road-motorway': 1, 'label-road-primary': 2, 'label-road-secondary': 3, 'label-road-minor': 4}
ROAD_LABEL_MINZOOM = {'label-road-minor': 14.0}   # acceptance 2026-09-16: minor names from MapLibre 14 so only main roads are named at z12-13
DASH_PT = 0.2       # pt per dashPattern unit on the Mac's output (RENDER-PIPELINE §7.16: 0.19 / 0.203 / 0.215 measured)
# Expressways below Apple z8 (RENDER-PIPELINE §7.15): resolve.py (v6: diamond inheritance = last occurrence, conditional
# rows by context) now yields the Line-LowZoom-Connection-Base row itself — 0.5 px, no stroke, at Apple z6-7.  What it
# cannot know is the feature class: Apple shows only its curated low-zoom connection classes below z6 (feature:85 rows)
# and draws them 1 px grey (209,209,209) at z7-11; OpenMapTiles has no such class, so the layer starts at Apple z6 and
# the z7-8 band is set here.  (apple zmin, zmax, width, strokeWidth, fill rgb, stroke rgba, fillColorLumAdjustment)
LOWZOOM_EXPRESSWAY_MINZOOM = 6.0
LOWZOOM_EXPRESSWAY = [(7.0, 8.0, 1.0, 0.0, (209, 209, 209), None, 0)]

# (id, kind, source-layer, filter, apple style template ({m} = Light/Dark, {e} = Explore-Light/Explore-Dark), note)
# kind: bg | fill | road | rail | line | boundary | place | roadname | watername
MAPPING = [
    ('background', 'bg', None, None, 'LandPolygon.{e}', 'land fill = background (OpenMapTiles has no land polygon)'),
    ('landcover-wood', 'fill', 'landcover', ['in', 'class', 'wood'], 'Landcover-Forest.{m}-Explore', 'OpenMapTiles wood ~ Apple Forest (inferred)'),
    ('landcover-grass', 'fill', 'landcover', ['in', 'class', 'grass', 'farmland'], 'Landcover-Herbaceous.{m}-Explore', 'grass/farmland ~ Herbaceous (inferred)'),
    ('landcover-sand', 'fill', 'landcover', ['in', 'class', 'sand'], 'Landcover-Sand.{m}-Explore', ''),
    ('landuse-commercial', 'fill', 'landuse', ['in', 'class', 'commercial', 'retail'], 'CommercialPolygon.{e}', ''),
    ('landuse-hospital', 'fill', 'landuse', ['in', 'class', 'hospital'], 'HospitalPolygon.{e}', ''),
    ('landuse-school', 'fill', 'landuse', ['in', 'class', 'school', 'university', 'college'], 'UniversityPolygon.{e}', 'school ~ University (inferred)'),
    ('landuse-cemetery', 'fill', 'landuse', ['in', 'class', 'cemetery'], 'CemeteryPolygon.{e}', ''),
    ('landuse-stadium', 'fill', 'landuse', ['in', 'class', 'stadium', 'pitch', 'playground'], 'StadiumPolygon.{e}', 'pitch/playground ~ Stadium (inferred)'),
    ('park', 'fill', 'park', None, 'ParkPolygon.{e}', ''),
    ('landuse-park', 'fill', 'landuse', ['in', 'class', 'park', 'recreation_ground', 'garden'], 'ParkPolygon.{e}', ''),
    ('aeroway', 'fill', 'aeroway', ['in', 'class', 'aerodrome', 'apron'], 'AirportPolygon.{e}', ''),
    ('water', 'fill', 'water', None, 'Landcover-Water.{m}-Explore', ''),
    ('coast-glow', 'glow', 'water', ['==', 'class', 'ocean'], 'Coastline-Glow-{m}-Base', 'glow on the water side of the ocean polygon edge: width prop 55 (Coastline-Glow-Base), colour prop 57; OpenMapTiles has no coastline line, the ocean polygon outline stands in'),
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
    ('road-kokudo', 'road', 'transportation_name', ['all', ['in', ['get', 'class'], ['literal', ['trunk', 'primary', 'secondary', 'tertiary']]], ['==', ['slice', ['coalesce', ['get', 'name'], ''], 0, 2], '国道']], 'Line-Highway.{m}-JPN-ClassOne', '国道 (national routes) drawn from transportation_name geometry: OpenMapTiles transportation has no ref; ClassOne purple = Apple JPN-ClassOne (inferred name-prefix test)'),
    # railways come from tiles/transit.pmtiles (国土数値情報 N02-24 RailroadSection, one centre line per route section,
    # pipeline/japan/build_transit2.py) instead of OpenMapTiles rail, which carries one line per OSM track (double
    # track = two lines, yards/sidings too) and so drew 2-3 px where Maps draws one 1 px line.  cls = shinkansen/jr/
    # private/sector3/subway/tram/mono/cable/public/other (N02 鉄道区分 x 事業者種別); subway/cable/mono are not drawn
    # on Maps' standard map, so they are left out.
    ('rail', 'rail', 'rail', ['in', 'cls', 'jr', 'private', 'sector3', 'public', 'other', 'tram'], 'Railway-Japan.{m}', 'N02 centre lines via transit.pmtiles; surface railways'),
    ('rail-shinkansen', 'rail', 'rail', ['==', 'cls', 'shinkansen'], 'Railway-Japan.Bullet-{m}', 'N02 新幹線 -> Apple Bullet variant (white core, blue dashed edge)'),
    ('geoline-tropics', 'geoline', 'graticule', ['!=', ['get', 'lat'], 0], 'Geolines-Tropics.{e}-Elevated', 'tropics from map/data/graticule.geojson; the globe sheet has no line style, the flat sheet Geolines-* draws them (RENDER-PIPELINE §7.13)'),
    ('geoline-equator', 'geoline', 'graticule', ['==', ['get', 'lat'], 0], 'Geolines-Equator.{e}-Elevated', 'equator, same source'),
    ('boundary-state', 'boundary', 'boundary', ['all', ['==', 'admin_level', 4], ['!=', 'maritime', 1]], 'Border-State.{e}', 'alpha from fillColor; prop 12 not used (v6)'),
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
    ('label-state', 'place', 'place', ['in', 'class', 'state', 'province'], 'State-Label-Small.{m}', 'Japanese prefectures ~ Small size class: visible Apple z7-10 (Medium z6-9 would show 41 names at the Japan view where Maps shows none) (inferred)'),
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


# Cascade context (resolve.py v6): client:69 = 2 is the map style the Mac/Elevated render matches (RENDER-PIPELINE §7.15),
# client:1 (TimePeriod) 0 = day / 1 = night, feature:4 (Country) 10 = Japan.  Feature classes we cannot know (road
# LineType 1, low-zoom connection class 85 ...) are left out, so their conditional rows are skipped.
CONTEXT = {'light': {'client': {69: 2, 1: 0}, 'feature': {4: 10}}, 'dark': {'client': {69: 2, 1: 1}, 'feature': {4: 10}}}


class Gen:
    def __init__(self, path, lum):
        self.src = path
        self.resolvers = {m: Resolver(path, context=CONTEXT[m]) for m in ('light', 'dark')}
        self.r = self.resolvers['light']
        self.lum = lum
        self.rows = []

    def adj(self, name, pid):
        return self.r.value_at(name, pid, 12) or 0.0 if self.lum else 0.0

    def zoom_range(self, name, pid=0, hidden=lambda v: v is False):
        """(minzoom, maxzoom) from a property's bands: a hidden band touching z0 sets minzoom, one touching z24 sets maxzoom."""
        lo, hi = None, None
        for a, b, v in self.r.bands(name, pid):
            if hidden(v) and a == 0.0:
                lo = max(0.0, b + ZOFF)
            if hidden(v) and b == 24.0:
                hi = max(0.0, a + ZOFF)
        return lo, hi

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
        """dashPattern (279 fill / 280 casing) per zoom band -> line-dasharray step expression.  Each unit is DASH_PT pt on
        screen; MapLibre wants multiples of the line width, so every band is divided by its own (casing) width."""
        dbands = [(a, b, v['dash']) for a, b, v in self.r.bands(name, pid) if isinstance(v, dict) and v.get('dash')]
        if not dbands:
            return None
        edges = sorted({e for a, b, _ in dbands for e in (a, b)} | {a for a, b, _ in self.r.bands(name, 3)} | {a for a, b, _ in self.r.bands(name, 6)})
        bands = []
        for a, b in zip(edges, edges[1:]):
            v = self.r.value_at(name, pid, a)
            pairs = v.get('dash') if isinstance(v, dict) else None
            w = (self.r.value_at(name, 3, a) or 0.0) + (2 * (self.r.value_at(name, 6, a) or 0.0) if casing else 0.0)
            if not pairs or w <= 0 or len(pairs) < 2 or all(x == 0 for x in pairs[1::2]):
                arr = None                                # (4, 0) = solid
            else:
                arr = [round(x * DASH_PT / w, 2) for x in pairs]
            if bands and bands[-1][2] == arr:
                bands[-1] = (bands[-1][0], b, arr)
            else:
                bands.append((a, b, arr))
        if all(arr is None for _, _, arr in bands):
            return None
        bands = [(a, b, arr if arr is not None else [1, 0]) for a, b, arr in bands]      # solid band = dash 1 gap 0
        return step(bands, lambda v: ['literal', v])

    @staticmethod
    def font_of(spec):
        """OpenFreeMap serves Noto Sans Regular / Bold / Italic only.  semibold at width<=60 (condensed, e.g. ward names)
        reads lighter than Noto Bold, so it maps to Regular; other semibold/bold -> Bold; italic -> Italic."""
        spec = spec or ''
        if 'italic' in spec:
            return ['Noto Sans Italic']
        if 'semibold' in spec and 'width=60' in spec:
            return ['Noto Sans Regular']
        if 'bold' in spec or 'semibold' in spec:
            return ['Noto Sans Bold']
        return ['Noto Sans Regular']

    def font(self, name):
        """fontSpec(23) per zoom band -> text-font step expression (cities: medium -> semibold -> bold -> semibold by zoom)."""
        bands = []
        for a, b, v in self.r.bands(name, 23):
            f = self.font_of(v)
            if bands and bands[-1][2] == f:
                bands[-1] = (bands[-1][0], b, f)
            else:
                bands.append((a, b, f))
        return step(bands, lambda v: ['literal', v]) if len(bands) > 1 else (bands[0][2] if bands else ['Noto Sans Regular'])

    def note(self, lid, kind, style, text):
        self.rows.append((lid, kind, style, text))

    def layer(self, lid, kind, src, flt, style, mode):
        r = self.r
        if style not in r.by_name:
            self.note(lid, kind, style, 'MISSING style')
            return []
        base = {'id': lid, 'source': 'transit' if kind == 'rail' else 'openmaptiles', 'source-layer': src}
        if flt:
            base['filter'] = flt
        lo, hi = self.zoom_range(style)
        # labelTextVisibility(33) is NOT used as a gate: freeways carry 33=0 at every zoom yet Maps labels them
        # (HANSHIN EXPRESSWAY ... in the acceptance render), so 0 does not mean hidden.
        lo = max(lo or 0, ROAD_LABEL_MINZOOM.get(lid, 0)) or None
        if lo:
            base['minzoom'] = lo
        if hi is not None and hi < 24:
            base['maxzoom'] = hi
        out = []
        if kind == 'bg':
            return [{'id': lid, 'type': 'background', 'paint': {'background-color': self.color_expr(style, 1, 470)}}]
        if kind == 'fill':
            c = self.color_expr(style, 1, 470)
            if c is None:
                self.note(lid, kind, style, 'no fillColor')
                return []
            return [{**base, 'type': 'fill', 'paint': {'fill-color': c, 'fill-antialias': False}}]
        if kind == 'glow':
            wb = [(a, b, v) for a, b, v in self.r.bands('Coastline-Glow-Base', 55)]
            cb = self.color_expr(style, 57)
            if not wb or cb is None:
                self.note(lid, kind, style, 'no glow width/colour')
                return []
            first = min((a for a, b, v in wb if v), default=None)
            l = {**base, 'type': 'line', 'layout': {'line-cap': 'round', 'line-join': 'round'},
                 'paint': {'line-color': cb, 'line-width': step(wb, lambda v: v), 'line-blur': step(wb, lambda v: round(v * 0.75, 2)),
                           'line-offset': step(wb, lambda v: round(-v / 2, 2)), 'line-opacity': 0.85}}
            if first is not None:
                l['minzoom'] = max(0.0, first + ZOFF)
            return [l]
        if kind == 'geoline':
            fc = self.color_expr(style, 1, 470)
            paint = {'line-color': fc, 'line-width': self.width_expr(style)}
            d = self.dash(style, 279)
            if d:
                paint['line-dasharray'] = d
            return [{**base, 'source': 'graticule', 'type': 'line', 'paint': paint}]
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
            if lid == 'road-motorway':
                out = self.lowzoom_expressway(out, base, layout)
            if kind == 'rail' and out:
                out[-1]['layout'] = {'line-join': 'round'}
                if lid == 'rail':
                    for l in out:
                        l.setdefault('minzoom', 6.0)      # N02 has every branch line; Maps hides surface rail below Apple z7
            return out
        if kind == 'boundary':
            fc = self.color_expr(style, 1, 470)
            paint = {'line-color': fc, 'line-width': self.width_expr(style)}
            # prop 12 (0.25 on borders) was applied as line-opacity up to v5; the Japan-view side-by-side (v6) shows Apple's
            # prefecture borders at the fillColor's own alpha (0.7-0.8), so 12 is not an opacity and is no longer used.
            d = self.dash(style, 279)
            if d:
                paint['line-dasharray'] = d
            return [{**base, 'type': 'line', 'paint': paint}]
        if kind in ('place', 'watername', 'roadname'):
            tc, hc = self.color_expr(style, 24, 463), self.color_expr(style, 25, 464)
            layout = {'text-field': NAME, 'text-font': self.font(style), 'text-size': self.text_size_expr(style)}
            if kind == 'roadname':
                layout.update({'symbol-placement': 'line', 'text-rotation-alignment': 'map', 'symbol-spacing': 400,
                               'symbol-sort-key': ROAD_RANK.get(lid, 9)})     # lower = placed first (freeway > trunk > ... )
            else:
                layout['text-max-width'] = 8
            if lid in ('label-ward', 'label-country', 'label-state'):
                layout.update({'text-transform': 'uppercase', 'text-letter-spacing': 0.1})   # Maps sets Latin ward/state/country names in caps with tracking
            paint = {'text-color': tc or '#000'}
            if hc:
                paint.update({'text-halo-color': hc, 'text-halo-width': 1.5})
            return [{**base, 'type': 'symbol', 'layout': layout, 'paint': paint}]
        return []

    def lowzoom_expressway(self, layers, base, layout):
        """Splice the LOWZOOM_EXPRESSWAY bands into the motorway casing/fill expressions and start the layer at
        LOWZOOM_EXPRESSWAY_MINZOOM (RENDER-PIPELINE §7.15)."""
        def splice(expr, low):
            hi = expr if isinstance(expr, list) and expr[0] == 'step' else ['step', ['zoom'], expr]
            stops = list(zip([None] + hi[3::2], [hi[2]] + hi[4::2]))          # (maplibre zoom or None, value)
            out = []
            for z, v in stops:
                za = 0.0 if z is None else z - ZOFF                          # apple zoom of this stop
                for a, b, w, sw, fc, sc, lum in LOWZOOM_EXPRESSWAY:
                    if a <= za < b:
                        v = low(w, sw, fc, sc, lum)
                out.append((z, v))
            # insert the low bands' own edges
            for a, b, w, sw, fc, sc, lum in LOWZOOM_EXPRESSWAY:
                for edge, val in ((a, low(w, sw, fc, sc, lum)), (b, None)):
                    ml = max(0.0, edge + ZOFF)
                    if not any(z == ml for z, _ in out if z is not None):
                        if val is None:                                       # band end: back to the sheet value there
                            val = hi[2]
                            for zz, vv in zip(hi[3::2], hi[4::2]):
                                if ml >= zz:
                                    val = vv
                        out.append((ml, val))
            out = [(z, v) for z, v in out if z is None] + sorted([(z, v) for z, v in out if z is not None])
            res = ['step', ['zoom'], out[0][1]]
            for z, v in out[1:]:
                res += [z, v]
            return res
        for l in layers:
            casing = l['id'].endswith('-casing')
            l['minzoom'] = max(0.0, LOWZOOM_EXPRESSWAY_MINZOOM + ZOFF)
            l['paint']['line-width'] = splice(l['paint']['line-width'], lambda w, sw, fc, sc, lum: round(w + 2 * sw, 3) if casing else w)
            l['paint']['line-color'] = splice(l['paint']['line-color'],
                                              lambda w, sw, fc, sc, lum: (rgba({'rgba': list(sc)}) if sc else 'rgba(0,0,0,0)') if casing
                                              else rgba({'rgba': list(fc) + [255]}, lum))
        return layers

    def elevated_name(self, name):
        """The -Elevated variant of a leaf style when the sheet has one (Line-X.Light-JPN-Elevated, ParkPolygon.Elevated-Light,
        Landcover-X.Light-Elevated); LandPolygon has none: in elevated mode the ground is Landcover-Ground.{m}-Elevated."""
        if not ELEVATED:
            return name
        if name.startswith('LandPolygon.'):
            return 'Landcover-Ground.' + ('Light' if 'Light' in name else 'Dark') + '-Elevated'
        if '.' not in name:                 # non-leaf (e.g. Rivers-Light-Flat-Base): try the Elevated-Base sibling
            cand = name.replace('-Flat-Base', '-Elevated-Base')
            return cand if cand in self.r.by_name else name
        fam, var = name.split('.', 1)
        for cand in (f'{fam}.{var}-Elevated', f'{fam}.Elevated-{var}', f'{fam}.{var.replace("Explore-", "Elevated-")}',
                     f'{fam}.{var.replace("-Explore", "-Elevated")}'):
            if cand in self.r.by_name:
                return cand
        return name

    def style(self, mode):
        m, e = ('Light', 'Explore-Light') if mode == 'light' else ('Dark', 'Explore-Dark')
        self.r = self.resolvers[mode]
        layers = []
        roads_casing, roads_fill = [], []
        for lid, kind, src, flt, tpl, note in MAPPING:
            name = self.elevated_name(tpl.format(m=m, e=e))
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
        pre = [l for l in layers if l['type'] != 'symbol' and l['id'] not in ('boundary-state', 'boundary-country', 'geoline-tropics', 'geoline-equator')]
        bounds = [l for l in layers if l['id'] in ('geoline-tropics', 'geoline-equator', 'boundary-state', 'boundary-country')]
        labels = [l for l in layers if l['type'] == 'symbol']
        return {'version': 8, 'name': f'Apple flat {mode} (generated from {Path(self.src).name})',
                'metadata': {'generator': 'pipeline/basemap/styl/to_maplibre.py', 'apple_style_sheet': Path(self.src).name,
                             'zoom_offset': ZOFF, 'lum_adjustment_applied': self.lum, 'elevated_variants': ELEVATED,
                             'region': 'Japan road variants (.Light-JPN / .Dark-JPN), Explore areas'},
                'sources': {'openmaptiles': {'type': 'vector', 'url': TILES},
                            'graticule': {'type': 'geojson', 'data': 'data/graticule.geojson'},
                            'transit': {'type': 'vector', 'url': 'pmtiles://../tiles/transit.pmtiles', 'minzoom': 4, 'maxzoom': 14,
                                        'attribution': '鉄道: 国土数値情報 N02-24'}},
                'glyphs': GLYPHS, 'layers': pre + roads_casing + roads_fill + bounds + labels}


def main(argv):
    global ZOFF
    lum = '--lum' in argv
    global ELEVATED
    if '--flat' in argv:
        ELEVATED = False; argv = [a for a in argv if a != '--flat']
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
