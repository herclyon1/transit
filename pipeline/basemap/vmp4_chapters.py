"""List VMP4 chapter tags (container header only — nothing inside a chapter is decoded) per tile set in a copy of the
geod tile cache (~/Library/Containers/com.apple.geod/Data/Library/Caches/com.apple.geod/Vault/MapTiles/MapTiles.sqlitedb).
Tag -> reader names come from the immediates passed to geo::codec::chapterAt / chapterForTag inside each
geo::codec::_read* function of GeoServices (see RENDER-PIPELINE.md); tags without a reader hit are '?'.

    vmp4_chapters.py tiles.db > basemap/data/globe/vmp4-chapters.txt
"""
import sqlite3, struct, collections, sys
TAGNAME = {1: 'header/tile metadata', 10: 'labels', 11: 'labels (2nd chapter read by _readLabels)', 13: 'labels (3rd chapter of _readLabels)', 20: 'shared by _readPois/_readLines/_readCoastlines/_readPolygonsofType (unnamed)', 30: 'pois', 31: 'lines', 34: 'coastlines (2nd chapter of _readCoastlines)', 38: 'coastlines (_readCoastlines)',
           60: 'lines by tag (_readLines) / connectivity (_readConnectivity)', 80: 'lines by tag (_readLines)', 90: 'lines by tag (_readLines)', 93: 'tile references', 100: 'DaVinci 3D data', 101: 'elevation raster', 102: 'style attribute rasters(102)',
           103: 'DaVinci metadata', 112: 'transit MZR override', 119: 'coverage', 128: 'transit systems', 129: 'transit network', 135: 'road network', 136: 'venue MZR override', 137: 'venues',
           138: 'storefronts', 141: 'label placement metadata', 144: 'pois addendum', 145: 'lines extended', 146: 'DaVinci traffic skeleton(old)', 147: 'DaVinci landmarks', 148: 'line attributes(old)',
           151: 'POI MZR overrides', 152: 'DaVinci traffic skeleton', 153: 'line attributes', 154: 'style attribute rasters (landcover index / climate)', 155: 'material rasters + materials',
           156: 'DaVinci asset metadata', 157: 'running tracks', 158: 'hillshade raster', 159: 'live features', 160: 'annotation labels', 162: 'supplemental feature ids', 165: 'live features metadata',
           166: 'POI updates', 168: 'region metadata', 169: 'compressed polygons', 170: 'DTM raster'}
STYLE = {1: 'VECTOR_STANDARD', 20: 'VECTOR_ROADS', 30: 'VECTOR_VENUES', 37: 'VECTOR_TRANSIT', 53: 'VECTOR_ROAD_NETWORK', 56: 'VECTOR_STREET_POI', 57: 'MUNIN_METADATA', 58: 'VECTOR_SPR_MERCATOR',
         59: 'VECTOR_SPR_MODELS', 60: 'VECTOR_SPR_MATERIALS', 61: 'VECTOR_SPR_METADATA', 64: 'VECTOR_STREET_LANDMARKS', 66: 'VECTOR_SPR_ROADS', 67: 'VECTOR_SPR_STANDARD', 68: 'VECTOR_POI_V2',
         73: 'VECTOR_BUILDINGS_V2', 79: 'VECTOR_SPR_POLAR', 83: 'VECTOR_TOPOGRAPHIC', 84: 'VECTOR_POI_V2_UPDATE', 88: 'VECTOR_REGION_METADATA', 78: 'SPR_ASSET_METADATA', 18: 'VECTOR_REALISTIC', 92: 'VMAP4_ELEVATION', 54: 'VECTOR_LAND_COVER'}
db = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else 'tiles.db')
per = collections.defaultdict(collections.Counter)
sizes = collections.defaultdict(collections.Counter)
n = collections.Counter()
for tileset, blob in db.execute('select t.tileset, d.data from tiles t join data d on d.rowid=t.data_pk'):
    style = (tileset >> 8) & 0xff
    if not blob or blob[:4] != b'VMP4':
        n[(style, 'non-VMP4:' + (blob[:4].hex() if blob else 'empty'))] += 1
        continue
    ver, cnt = struct.unpack_from('<HH', blob, 4)
    n[(style, 'VMP4')] += 1
    for i in range(cnt):
        tag, off, ln = struct.unpack_from('<HII', blob, 8 + i * 10)
        per[style][tag] += 1
        sizes[style][tag] += ln
for style in sorted(per):
    total = n[(style, 'VMP4')]
    print(f'== style {style} {STYLE.get(style, "?")}: {total} VMP4 tiles')
    for tag, c in sorted(per[style].items()):
        print(f'   tag {tag:4} {TAGNAME.get(tag, "?"):45} in {c:4}/{total} tiles, {sizes[style][tag] / 1024:8.1f} KB')
print({k: v for k, v in n.items() if k[1] != 'VMP4'})
