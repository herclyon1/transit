// Decode Apple's SPR (DaVinci ground) tiles from a copy of the geod tile cache with Apple's own decoder:
// GeoServices' GEOVectorTile (initWithVMP4:localizationData:tileKey:) parses the VMP4 chapters — the style-attribute
// rasters (chapter 154: land-cover class index / climate code, polygon-raster encoded), the elevation raster
// (chapter 101, 16-bit PNG), the material sheets (chapter 155) and the DaVinci mesh (chapter 100) — and we only
// read the decoded arrays back. No window, no network, nothing written outside the output directory.
//
//   clang -fobjc-arc -framework Foundation -lsqlite3 -o /tmp/spr_dump pipeline/basemap/spr_dump.m
//   /tmp/spr_dump tiles.db outdir [maxzoom]          (tiles.db = a copy of MapTiles.sqlitedb + its -wal/-shm)
//
// Outputs per tile z-x-y: <out>/<z>-<x>-<y>-attr<id>.pgm (8-bit raster), <z>-<x>-<y>-elev.png (the PNG as stored,
// 16-bit grey), <z>-<x>-<y>.json (attribute ids, sizes, elevation range, material sheet dump). GEOTileKey layout
// from GEOTileKeyMake: byte 0 = type (2 = standard xyz), u32 @6 = x<<6 | zoom, u32 @0xa = y | style<<26, byte
// @0xe = style>>6 (the cache's key_b/key_c are these two u32s).
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <sqlite3.h>

typedef struct { uint8_t b[16]; } GEOTileKey;

static GEOTileKey makeKey(uint32_t x, uint32_t y, uint32_t z, uint32_t style) {
    GEOTileKey k; memset(&k, 0, sizeof k);
    k.b[0] = 2;
    uint32_t a = (x << 6) | (z & 0x3f); memcpy(k.b + 6, &a, 4);
    uint32_t c = (y & 0x3ffffff) | ((style & 0x3f) << 26); memcpy(k.b + 10, &c, 4);
    k.b[14] = (uint8_t)(style >> 6);
    return k;
}

typedef struct {            // GeoCodecsDaVinciStyleAttributeRaster, stride 0x18 (from geo::codec::_readStyleAttributeRasters)
    uint8_t *data; uint32_t byteCount; uint32_t attributeId; uint8_t polygonEncoded; uint8_t pad; uint16_t width; uint16_t height; uint16_t pad2;
} AttrRaster;

static id msg(id o, const char *sel) { return ((id (*)(id, SEL))objc_msgSend)(o, sel_registerName(sel)); }
static long msgL(id o, const char *sel) { return ((long (*)(id, SEL))objc_msgSend)(o, sel_registerName(sel)); }
static double msgD(id o, const char *sel) { return ((double (*)(id, SEL))objc_msgSend)(o, sel_registerName(sel)); }
static void *msgP(id o, const char *sel) { return ((void *(*)(id, SEL))objc_msgSend)(o, sel_registerName(sel)); }

static void hexdump(FILE *f, const uint8_t *p, size_t n) { for (size_t i = 0; i < n; i++) fprintf(f, "%02x", p[i]); }

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 3) { fprintf(stderr, "usage: spr_dump tiles.db outdir [maxzoom]\n"); return 1; }
        int maxzoom = argc > 3 ? atoi(argv[3]) : 99;
        if (!dlopen("/System/Library/PrivateFrameworks/GeoServices.framework/GeoServices", RTLD_NOW)) { fprintf(stderr, "%s\n", dlerror()); return 1; }
        Class VT = NSClassFromString(@"GEOVectorTile");
        if (!VT) { fprintf(stderr, "no GEOVectorTile\n"); return 1; }
        sqlite3 *db; if (sqlite3_open_v2(argv[1], &db, SQLITE_OPEN_READONLY, NULL)) { fprintf(stderr, "sqlite: %s\n", sqlite3_errmsg(db)); return 1; }
        NSString *out = [NSString stringWithUTF8String:argv[2]];
        [[NSFileManager defaultManager] createDirectoryAtPath:out withIntermediateDirectories:YES attributes:nil error:nil];
        sqlite3_stmt *st;
        sqlite3_prepare_v2(db, "select key_b, key_c, tileset, d.data from tiles t join data d on d.rowid=t.data_pk where ((tileset>>8)&255) in (58,79)", -1, &st, NULL);
        int n = 0;
        while (sqlite3_step(st) == SQLITE_ROW) {
            uint32_t kb = (uint32_t)sqlite3_column_int64(st, 0), kc = (uint32_t)sqlite3_column_int64(st, 1);
            long tileset = sqlite3_column_int64(st, 2);
            const void *blob = sqlite3_column_blob(st, 3); int len = sqlite3_column_bytes(st, 3);
            uint32_t style = (tileset >> 8) & 0xff;
            uint32_t z = (kb >> 16) & 0x3f, x = ((kb >> 22) & 0x3ff) | ((kc & 0xffff) << 10), y = kc >> 16;
            if ((int)z > maxzoom) continue;
            GEOTileKey key = makeKey(x, y, z, style);
            NSData *data = [NSData dataWithBytes:blob length:len];
            id tile = ((id (*)(id, SEL, id, id, GEOTileKey *))objc_msgSend)([VT alloc], sel_registerName("initWithVMP4:localizationData:tileKey:"), data, nil, &key);
            if (!tile) { fprintf(stderr, "z%u x%u y%u style %u: init failed\n", z, x, y, style); continue; }
            NSString *base = [out stringByAppendingFormat:@"/%u-%u-%u", z, x, y];
            NSMutableString *js = [NSMutableString stringWithFormat:@"{\"z\":%u,\"x\":%u,\"y\":%u,\"style\":%u,\"bytes\":%d,", z, x, y, style, len];
            // elevation
            long elevBytes = msgL(tile, "elevationRasterByteCount");
            const void *png = msgP(tile, "elevationRasterPng");
            if (png && elevBytes > 0) [[NSData dataWithBytes:png length:elevBytes] writeToFile:[base stringByAppendingString:@"-elev.png"] atomically:YES];
            // accessor return types from their disassembly: min/max elevation ldrsh (int16), tileSizeInMeters ldr s0 (float),
            // metersToTileSize ldr d0 (double), zResolutionBits ldrh
            long minE = ((long (*)(id, SEL))objc_msgSend)(tile, sel_registerName("minElevationInMeters"));
            long maxE = ((long (*)(id, SEL))objc_msgSend)(tile, sel_registerName("maxElevationInMeters"));
            float tsz = ((float (*)(id, SEL))objc_msgSend)(tile, sel_registerName("tileSizeInMeters"));
            [js appendFormat:@"\"elev_png_bytes\":%ld,\"min_elev_m\":%ld,\"max_elev_m\":%ld,\"meters_to_tile\":%.10g,\"tile_size_m\":%.9g,\"z_res_bits\":%ld,",
                elevBytes, (long)(int16_t)minE, (long)(int16_t)maxE, msgD(tile, "metersToTileSize"), tsz, msgL(tile, "zResolutionBits")];
            // style attribute rasters
            long rc = msgL(tile, "daVinciStyleAttributeRasterCount");
            AttrRaster *rs = msgP(tile, "daVinciStyleAttributeRasters");
            [js appendFormat:@"\"attribute_rasters\":["];
            for (long i = 0; i < rc && rs; i++) {
                AttrRaster *r = &rs[i];
                [js appendFormat:@"%s{\"attribute\":%u,\"polygon_encoded\":%u,\"width\":%u,\"height\":%u,\"bytes\":%u}", i ? "," : "", r->attributeId, r->polygonEncoded, r->width, r->height, r->byteCount];
                if (r->data && r->width && r->height && r->byteCount >= (uint32_t)r->width * r->height) {
                    NSMutableData *pgm = [NSMutableData dataWithData:[[NSString stringWithFormat:@"P5\n%u %u\n255\n", r->width, r->height] dataUsingEncoding:NSASCIIStringEncoding]];
                    [pgm appendBytes:r->data length:(NSUInteger)r->width * r->height];
                    [pgm writeToFile:[base stringByAppendingFormat:@"-attr%u.pgm", r->attributeId] atomically:YES];
                }
            }
            [js appendString:@"],"];
            // counts of everything DaVinci for orientation
            const char *counts[] = {"daVinciMaterialSheetCount", "daVinciMeshCount", "daVinciVertexCount", "daVinciIndexCount", "daVinciRenderableCount", "daVinciSceneCount", "daVinciDecalCount", "daVinciExternalMaterialCount", "explicitTextureDataCount", "directionalXYTextureDataCount", "daVinciTileVersion", NULL};
            for (int i = 0; counts[i]; i++) [js appendFormat:@"\"%s\":%ld,", counts[i], msgL(tile, counts[i])];
            // material sheets: dump the raw struct bytes of the first sheet so the layout can be read off
            long msc = msgL(tile, "daVinciMaterialSheetCount");
            const uint8_t *ms = msgP(tile, "daVinciMaterialSheets");
            [js appendString:@"\"material_sheet_raw\":\""];
            if (ms && msc > 0) { NSMutableString *h = [NSMutableString string]; for (int i = 0; i < 256; i++) [h appendFormat:@"%02x", ms[i]]; [js appendString:h]; }
            [js appendString:@"\",\"external_material_ids\":["];
            long emc = msgL(tile, "daVinciExternalMaterialCount");
            const uint64_t *em = msgP(tile, "daVinciExternalMaterialIDs");
            for (long i = 0; i < emc && em && i < 64; i++) [js appendFormat:@"%s%llu", i ? "," : "", (unsigned long long)em[i]];
            [js appendString:@"],"];
            // chapter 155 material-raster records: VectorTile+0xb38 (array of 0x50-byte records), +0xb40 count
            // (offsets from geo::codec::_readMaterialRasters); record: +0x20 uint64 ids, +0x28 n; +0x30/+0x38 and
            // +0x40/+0x48 uint16 arrays; the raster itself in the first 0x20 bytes (layout read off the hexdump)
            const uint8_t *vt = *(const uint8_t *const *)((const uint8_t *)(__bridge const void *)tile + 8);   // ivar: the geo::codec::VectorTile*, as every accessor reads it
            fprintf(stderr, "z%u x%u y%u vt=%p mrc=%u\n", z, x, y, vt, vt ? *(const uint16_t *)(vt + 0xb40) : 0);
            uint16_t mrc = vt ? *(const uint16_t *)(vt + 0xb40) : 0;
            const uint8_t *mr = vt ? *(const uint8_t *const *)(vt + 0xb38) : NULL;
            [js appendFormat:@"\"material_rasters\":["];
            for (int i = 0; i < mrc && mr; i++) {
                const uint8_t *rec = mr + 0x50 * i;
                NSMutableString *h = [NSMutableString string]; for (int k = 0; k < 0x50; k++) [h appendFormat:@"%02x", rec[k]];
                fprintf(stderr, "  rec %d: %s\n", i, h.UTF8String);
                if (getenv("SPR_NOFOLLOW")) { [js appendFormat:@"%s{\"raw\":\"%@\"}", i ? "," : "", h]; continue; }
                const uint64_t *ids = *(const uint64_t *const *)(rec + 0x20); uint16_t nid = *(const uint16_t *)(rec + 0x28);
                const uint16_t *a = *(const uint16_t *const *)(rec + 0x30); uint16_t na = *(const uint16_t *)(rec + 0x38);
                const uint16_t *bb = *(const uint16_t *const *)(rec + 0x40); uint16_t nb = *(const uint16_t *)(rec + 0x48);
                [js appendFormat:@"%s{\"raw\":\"%@\",\"ids\":[", i ? "," : "", h];
                for (int k = 0; k < nid && ids && k < 512; k++) [js appendFormat:@"%s%llu", k ? "," : "", (unsigned long long)ids[k]];
                [js appendString:@"],\"a\":["];
                for (int k = 0; k < na && a && k < 512; k++) [js appendFormat:@"%s%u", k ? "," : "", a[k]];
                [js appendString:@"],\"b\":["];
                for (int k = 0; k < nb && bb && k < 512; k++) [js appendFormat:@"%s%u", k ? "," : "", bb[k]];
                [js appendString:@"]}"];
                // record (read off the hexdump): +0 u32 1, +8 data ptr, +0x10 u32 byteCount, +0x14 u16 1, +0x16 w, +0x18 h, +0x1a bpp
                const uint8_t *rd = *(const uint8_t *const *)(rec + 8); uint32_t rbytes = *(const uint32_t *)(rec + 0x10);
                uint16_t rw = *(const uint16_t *)(rec + 0x16), rh = *(const uint16_t *)(rec + 0x18), rbpp = *(const uint16_t *)(rec + 0x1a);
                if (rd && rw && rh && rbytes >= (uint32_t)rw * rh * (rbpp / 8)) {
                    NSMutableData *pgm = [NSMutableData dataWithData:[[NSString stringWithFormat:@"P5\n%u %u\n%u\n", rw, rh, rbpp == 16 ? 65535 : 255] dataUsingEncoding:NSASCIIStringEncoding]];
                    [pgm appendBytes:rd length:(NSUInteger)rw * rh * (rbpp / 8)];
                    [pgm writeToFile:[base stringByAppendingFormat:@"-mat%d.pgm", i] atomically:YES];
                }
            }
            [js appendString:@"],"];
            // mesh: raw bytes so the vertex / mesh-descriptor layouts can be read off (see README for the decoded layout)
            if (getenv("SPR_MESHRAW")) {
                long vc = msgL(tile, "daVinciVertexCount"), ic = msgL(tile, "daVinciIndexCount"), mc = msgL(tile, "daVinciMeshCount"), rc2 = msgL(tile, "daVinciRenderableCount");
                const uint8_t *vp = msgP(tile, "daVinciVertices"), *ip = msgP(tile, "daVinciIndices"), *mp = msgP(tile, "daVinciMeshes"), *rp = msgP(tile, "daVinciRenderables");
                // vertices are float3 (x, y in tile units 0..1, z = height / tile size); indices uint16 per mesh (mesh
                // descriptor stride 0x50: u32 vertexOffset @0, vertexCount @8, indexOffset @0x10, indexCount @0x14)
                if (vp) [[NSData dataWithBytes:vp length:vc * 12] writeToFile:[base stringByAppendingString:@"-verts.f32"] atomically:YES];
                if (ip) [[NSData dataWithBytes:ip length:ic * 2] writeToFile:[base stringByAppendingString:@"-idx.u16"] atomically:YES];
                if (mp) [[NSData dataWithBytes:mp length:mc * 128] writeToFile:[base stringByAppendingString:@"-meshes.bin"] atomically:YES];
                // mesh descriptor +0x40: pointer to the per-vertex attribute stream(s) (normals), +0x48 count — dump the first mesh's
                if (mp && getenv("SPR_ATTR")) {
                    // mesh descriptor: +0x30 pointer with +0x38 count == vertexCount: the per-vertex attribute data (normals?)
                    const uint8_t *ap = *(const uint8_t *const *)(mp + 0x30); uint32_t ac = *(const uint32_t *)(mp + 0x38);
                    uint32_t vcount = *(const uint32_t *)(mp + 8);
                    fprintf(stderr, "  mesh0 attr ptr %p count %u vcount %u\n", ap, ac, vcount);
                    if (ap && ac == vcount) [[NSData dataWithBytes:ap length:vcount * 16] writeToFile:[base stringByAppendingString:@"-mesh0-attr-data.bin"] atomically:YES];
                }
                if (rp) [[NSData dataWithBytes:rp length:rc2 * 128] writeToFile:[base stringByAppendingString:@"-renderables.bin"] atomically:YES];
                [js appendFormat:@"\"vertex_count\":%ld,\"index_count\":%ld,\"mesh_count\":%ld,\"renderable_count\":%ld,", vc, ic, mc, rc2];
            }
            [js appendString:@"\"end\":1}\n"];
            [js writeToFile:[base stringByAppendingString:@".json"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
            printf("z%u x%u y%u style %u: %ld rasters, elev %ld B, sheets %ld, meshes %ld, vertices %ld\n", z, x, y, style, rc, elevBytes, msc, msgL(tile, "daVinciMeshCount"), msgL(tile, "daVinciVertexCount"));
            n++;
        }
        sqlite3_finalize(st); sqlite3_close(db);
        printf("%d tiles\n", n);
    }
    return 0;
}
