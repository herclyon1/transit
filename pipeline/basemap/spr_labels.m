// Dump the physical-feature labels Apple ships in its VECTOR_SPR_STANDARD tiles (style 67, chapter 10/13 labels) at
// the globe zooms, through Apple's own decoder (GEOVectorTile) — names via the exported GEOFeatureGetNativeLabel /
// GEOFeatureGetLocalizedLabel, plus the raw feature struct so type / rank fields can be read off.
//   clang -fobjc-arc -framework Foundation -lsqlite3 -o /tmp/spr_labels pipeline/basemap/spr_labels.m
//   /tmp/spr_labels tiles.db maxzoom > labels.tsv        (tiles.db = copy of MapTiles.sqlitedb + -wal/-shm)
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <sqlite3.h>

typedef struct { uint8_t b[16]; } GEOTileKey;
static GEOTileKey makeKey(uint32_t x, uint32_t y, uint32_t z, uint32_t style) {
    GEOTileKey k; memset(&k, 0, sizeof k); k.b[0] = 2;
    uint32_t a = (x << 6) | (z & 0x3f); memcpy(k.b + 6, &a, 4);
    uint32_t c = (y & 0x3ffffff) | ((style & 0x3f) << 26); memcpy(k.b + 10, &c, 4);
    k.b[14] = (uint8_t)(style >> 6); return k;
}
static long msgL(id o, const char *sel) { return ((long (*)(id, SEL))objc_msgSend)(o, sel_registerName(sel)); }
static void *msgP(id o, const char *sel) { return ((void *(*)(id, SEL))objc_msgSend)(o, sel_registerName(sel)); }

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 2) { fprintf(stderr, "usage: spr_labels tiles.db [maxzoom] [style]\n"); return 1; }
        int maxzoom = argc > 2 ? atoi(argv[2]) : 4; int wantStyle = argc > 3 ? atoi(argv[3]) : 67;
        void *gs = dlopen("/System/Library/PrivateFrameworks/GeoServices.framework/GeoServices", RTLD_NOW);
        if (!gs) { fprintf(stderr, "%s\n", dlerror()); return 1; }
        bool (*getNative)(const void *, unsigned long, const char **, const char **) = dlsym(gs, "GEOFeatureGetNativeLabel");
        unsigned long (*locCount)(const void *) = dlsym(gs, "GEOFeatureGetLocalizedLabelCount");
        bool (*getLoc)(const void *, unsigned long, const char **, const char **) = dlsym(gs, "GEOFeatureGetLocalizedLabel");
        if (!getNative || !locCount || !getLoc) { fprintf(stderr, "symbols missing\n"); return 1; }
        Class VT = NSClassFromString(@"GEOVectorTile");
        sqlite3 *db; if (sqlite3_open_v2(argv[1], &db, SQLITE_OPEN_READONLY, NULL)) { fprintf(stderr, "sqlite: %s\n", sqlite3_errmsg(db)); return 1; }
        sqlite3_stmt *st;
        sqlite3_prepare_v2(db, "select key_b, key_c, tileset, d.data from tiles t join data d on d.rowid=t.data_pk", -1, &st, NULL);
        printf("z\tx\ty\tkind\tindex\tname\tw1\tw2\tgeom\traw\tattrs\n");
        while (sqlite3_step(st) == SQLITE_ROW) {
            uint32_t kb = (uint32_t)sqlite3_column_int64(st, 0), kc = (uint32_t)sqlite3_column_int64(st, 1);
            long tileset = sqlite3_column_int64(st, 2);
            uint32_t style = (tileset >> 8) & 0xff;
            if ((int)style != wantStyle) continue;
            uint32_t z = (kb >> 16) & 0x3f, x = ((kb >> 22) & 0x3ff) | ((kc & 0xffff) << 10), y = kc >> 16;
            if ((int)z > maxzoom) continue;
            const void *blob = sqlite3_column_blob(st, 3); int len = sqlite3_column_bytes(st, 3);
            GEOTileKey key = makeKey(x, y, z, style);
            NSData *data = [NSData dataWithBytes:blob length:len];
            id tile = ((id (*)(id, SEL, id, id, GEOTileKey *))objc_msgSend)([VT alloc], sel_registerName("initWithVMP4:localizationData:tileKey:"), data, nil, &key);
            if (!tile) { fprintf(stderr, "z%u x%u y%u: init failed\n", z, x, y); continue; }
            // physical features: 176-byte structs (physicalFeaturesCount = bytes / 176)
            long n = msgL(tile, "physicalFeaturesCount");
            const uint8_t *pf = msgP(tile, "physicalFeatures");
            fprintf(stderr, "z%u x%u y%u: %ld physical features, pois %ld, labelTextPlacements %ld, tileLabelLines %ld\n", z, x, y, n, msgL(tile, "poisCount"), msgL(tile, "labelTextPlacementsCount"), msgL(tile, "tileLabelLinesCount"));
            for (long i = 0; i < n && pf; i++) {
                const uint8_t *f = pf + 176 * i;
                if (getenv("SPR_RAWONLY")) { printf("%u\t%u\t%u\tphysical\t%ld\t\t\t\t0\t", z, x, y, i); for (int k = 0; k < 176; k++) printf("%02x", f[k]); printf("\n"); continue; }
                if (getenv("SPR_STR")) {   // the pointer at +0x10 of the feature struct points at the name inside the tile
                    const char *s10 = *(const char *const *)(f + 0x10);
                    // label path: physicalFeaturesVertices pool = {u32, float2 *verts @8, u32 nverts @0x10, float *perVertex @0x18,
                    // {u64 start, u64 count} *ranges @0x20, u32 nranges @0x28}; the feature's range index is the u32 at +0x5c;
                    // coordinates are tile-centred (-0.5..0.5, y up)
                    const uint8_t *pool = msgP(tile, "physicalFeaturesVertices");
                    NSMutableString *path = [NSMutableString string];
                    if (pool) {
                        const float *verts = *(const float *const *)(pool + 8); uint32_t nv = *(const uint32_t *)(pool + 0x10);
                        const uint64_t *ranges = *(const uint64_t *const *)(pool + 0x20); uint32_t nr = *(const uint32_t *)(pool + 0x28);
                        uint32_t ri = *(const uint32_t *)(f + 0x5c); if (getenv("SPR_DBG")) fprintf(stderr, "   ri %u nr %u nv %u verts %p ranges %p\n", ri, nr, nv, verts, ranges);
                        if (ranges && verts && ri < nr) {
                            uint32_t st = (uint32_t)ranges[2 * ri], cnt = (uint32_t)ranges[2 * ri + 1];
                            for (uint32_t k = 0; k < cnt && st + k < nv; k++) [path appendFormat:@"%s%.5f,%.5f", k ? ";" : "", verts[2 * (st + k)], verts[2 * (st + k) + 1]];
                        }
                    }
                    float w44 = *(const float *)(f + 0x44), wa4 = *(const float *)(f + 0xa4);
                    printf("%u\t%u\t%u\tphysical\t%ld\t%.80s\t%g\t%g\t%s\t", z, x, y, i, s10 ? s10 : "", w44, wa4, path.UTF8String);
                    for (int k = 0; k < 176; k++) printf("%02x", f[k]);
                    const void *attrs = *(const void *const *)(f + 0x18);   // shared_ptr<FeatureStyleAttributes>: object @0x18, control block @0x20
                    printf("\t");
                    if (attrs) {                                       // FeatureStyleAttributes: pairs (u32 key, u32 value) @0, count u8 @0x21
                        const uint32_t *pairs = *(const uint32_t *const *)attrs; unsigned cnt = ((const uint8_t *)attrs)[0x21];
                        for (unsigned k = 0; k < cnt && pairs; k++) printf("%s%u=%u", k ? " " : "", pairs[2 * k], pairs[2 * k + 1]);
                    }
                    printf("\n"); continue;
                }
                const char *t = NULL, *l = NULL; bool ok = getNative(f, 0, &t, &l);
                unsigned long nl = locCount(f); const char *lt = NULL, *ll = NULL; if (nl) getLoc(f, 0, &lt, &ll);
                printf("%u\t%u\t%u\tphysical\t%ld\t%s\t%s\t%s\t%lu\t", z, x, y, i, ok && t ? t : "", ok && l ? l : "", lt ? lt : "", nl);
                for (int k = 0; k < 176; k++) printf("%02x", f[k]);
                printf("\n");
            }
            if (getenv("SPR_POOL")) {   // vertex pool head + the words around the feature's vertex offset (+0x38)
                const uint8_t *pool = msgP(tile, "physicalFeaturesVertices");
                fprintf(stderr, "pool head: "); for (int k = 0; k < 64 && pool; k++) fprintf(stderr, "%02x", pool[k]); fprintf(stderr, "\n");
                for (int slot = 0x18; slot <= 0x20 && pool; slot += 8) {
                    const uint8_t *arr = *(const uint8_t *const *)(pool + slot);
                    fprintf(stderr, "  ptr@%#x:", slot); for (int k = 0; k < 80 && arr; k++) fprintf(stderr, "%02x%s", arr[k], (k % 4 == 3) ? " " : ""); fprintf(stderr, "\n");
                }
            }
            // point features with label text placements (cities etc.): pois array
            long np = msgL(tile, "poisCount");
            const uint8_t *po = msgP(tile, "pois");
            if (getenv("SPR_POIS") && np > 1 && po) {
                // POI stride: every GeoCodecsFeature starts with the VectorTile* (the same pointer as the physical features'
                // +0); the distance between repeats is the struct size
                const uint8_t *vt = *(const uint8_t *const *)(pf ? pf : po);
                int stride = 0;
                for (int k = 8; k < 1024 && !stride; k += 8) if (*(const uint8_t *const *)(po + k) == vt) stride = k;
                fprintf(stderr, "  poi stride %d\n", stride);
                const uint8_t *tile = vt; const uint8_t *labels = *(const uint8_t *const *)(tile + 0x420);
                for (long i = 0; stride && i < np; i++) {
                    const uint8_t *f = po + stride * i;
                    uint32_t li = *(const uint32_t *)(f + 0x38); unsigned lc = f[0x49];
                    const char *nm = (labels && lc) ? *(const char *const *)(labels + 24 * li) : NULL;
                    const void *attrs = *(const void *const *)(f + 0x18);
                    float px = *(const float *)(f + 0x58), py = *(const float *)(f + 0x5c), pw = *(const float *)(f + 0x60);
                    printf("%u\t%u\t%u\tpoi\t%ld\t%.80s\t%g\t%g\t%.5f,%.5f\t", z, x, y, i, nm ? nm : "", pw, (double)lc, px, py);
                    for (int k = 0; k < (stride < 176 ? stride : 176); k++) printf("%02x", f[k]);
                    printf("\t");
                    if (attrs) { const uint32_t *pairs = *(const uint32_t *const *)attrs; unsigned cnt = ((const uint8_t *)attrs)[0x21]; for (unsigned k = 0; k < cnt && pairs && k < 64; k++) printf("%s%u=%u", k ? " " : "", pairs[2 * k], pairs[2 * k + 1]); }
                    printf("\n");
                }
            }
        }
        sqlite3_finalize(st); sqlite3_close(db);
    }
    return 0;
}
