// Capture the uniform buffers and lookup textures VectorKit binds while MKMapView renders (realistic elevation),
// by hooking the concrete Metal encoder class in-process.  Everything is done with the public Metal + ObjC runtime
// APIs; no other process is touched.
//
//   clang -fobjc-arc -framework AppKit -framework MapKit -framework Metal -framework CoreGraphics -o /tmp/capture capture.m
//   /tmp/capture <lat> <lng> <dlat> <dlng> <outdir> [seconds] [pitch] [heading] [dark]
//
// Output: <outdir>/capture.json  — per fragment/vertex function and buffer index: byte length, hex of the first
//         512 bytes, float32 / float16 views; <outdir>/tex-<function>-<index>-<label>.raw + .json for the
//         textures we care about (gradient1Texture, gradient2Texture, styleTexture, styleIndexTexture, aridity,
//         temperature, irradiance cube) when their storage lets us read them back.
#import <AppKit/AppKit.h>
#import <MapKit/MapKit.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>

static NSMutableDictionary *pipelineNames;      // state pointer -> @{frag, vert}
static NSMutableDictionary *records;            // "frag|F|index" -> dict
static NSMutableDictionary *textureRecords;
static NSMutableSet *seenTextures;
static NSString *outDir;
static NSMapTable *currentPipeline;             // encoder -> state
static NSMapTable *lastBuffers;                 // encoder -> NSMutableDictionary "stage|index" -> buffer
static NSUInteger texCounter;
static id<MTLCommandQueue> blitQueue;           // our own queue for reading back private textures
static NSMutableDictionary *rawByPointer;       // "%p" -> raw file name of the last readback of that texture object
static NSMutableArray *draws;                   // per setFragmentTextures call covering 7..8: {styleIndex, styleTexture} raw names

static NSString *hexOf(const void *p, NSUInteger n) {
    NSMutableString *s = [NSMutableString stringWithCapacity:n * 2];
    for (NSUInteger i = 0; i < n; i++) [s appendFormat:@"%02x", ((const unsigned char *)p)[i]];
    return s;
}

static void recordBytes(id encoder, NSString *stage, NSUInteger index, const void *bytes, NSUInteger length, NSString *how) {
    id state = [currentPipeline objectForKey:encoder];
    NSDictionary *names = state ? pipelineNames[[NSValue valueWithPointer:(__bridge const void *)state]] : nil;
    NSString *fn = names ? (names[[stage isEqualToString:@"F"] ? @"frag" : @"vert"] ?: @"?") : @"?";
    if (![fn hasPrefix:@"DaVinci::ground"] && ![fn hasPrefix:@"GlobeAtmosphere"] && ![fn hasPrefix:@"Fog::"] && ![fn hasPrefix:@"Sky::"] && ![fn hasPrefix:@"GlobeStars"] && ![fn hasPrefix:@"Stars::"] && ![fn hasPrefix:@"DaVinci::globe"]) return;
    NSUInteger n = MIN(length, 512);
    NSString *hex = hexOf(bytes, n);
    NSString *key = [NSString stringWithFormat:@"%@|%@|%lu", fn, stage, (unsigned long)index];
    NSMutableArray *arr = records[key];
    if (!arr) { arr = [NSMutableArray array]; records[key] = arr; }
    for (NSDictionary *d in arr) if ([d[@"hex"] isEqualToString:hex]) { return; }
    if (arr.count >= 6) return;
    NSMutableArray *f32 = [NSMutableArray array], *f16 = [NSMutableArray array];
    for (NSUInteger i = 0; i + 4 <= n; i += 4) { float v; memcpy(&v, (const char *)bytes + i, 4); [f32 addObject:isfinite(v) ? @(v) : @"nan"]; }
    for (NSUInteger i = 0; i + 2 <= n; i += 2) { __fp16 v; memcpy(&v, (const char *)bytes + i, 2); float fv = (float)v; [f16 addObject:isfinite(fv) ? @(fv) : @"nan"]; }
    [arr addObject:@{@"length": @(length), @"hex": hex, @"f32": f32, @"f16": f16, @"how": how}];
}

static void recordTexture(id encoder, NSString *stage, NSUInteger index, id<MTLTexture> tex) {
    if (!tex) return;
    id state = [currentPipeline objectForKey:encoder];
    NSDictionary *names = state ? pipelineNames[[NSValue valueWithPointer:(__bridge const void *)state]] : nil;
    NSString *fn = names ? (names[[stage isEqualToString:@"F"] ? @"frag" : @"vert"] ?: @"?") : @"?";
    if (![fn hasPrefix:@"DaVinci::ground"] && ![fn hasPrefix:@"DaVinci::globe"]) return;
    NSString *key = [NSString stringWithFormat:@"%@|%@|%lu|%p|%lu", fn, stage, (unsigned long)index, (__bridge void *)tex, (unsigned long)tex.height];
    if ([seenTextures containsObject:key]) return;
    [seenTextures addObject:key];
    NSString *label = tex.label ?: @"";
    NSMutableDictionary *info = [@{@"function": fn, @"stage": stage, @"index": @(index), @"label": label, @"width": @(tex.width), @"height": @(tex.height),
                                   @"depth": @(tex.depth), @"pixelFormat": @(tex.pixelFormat), @"textureType": @(tex.textureType), @"storageMode": @(tex.storageMode),
                                   @"mipmaps": @(tex.mipmapLevelCount), @"arrayLength": @(tex.arrayLength)} mutableCopy];
    // read back 2D / cube textures; private storage goes through a blit into a shared copy on our own queue
    if (tex.width * tex.height <= 1024 * 1024 && (tex.textureType == MTLTextureType2D || tex.textureType == MTLTextureTypeCube)) {
        NSUInteger bpp = 0;
        switch (tex.pixelFormat) {
            case MTLPixelFormatRGBA8Unorm: case MTLPixelFormatRGBA8Unorm_sRGB: case MTLPixelFormatBGRA8Unorm: case MTLPixelFormatBGRA8Unorm_sRGB: case MTLPixelFormatR32Float: case MTLPixelFormatRG16Float: bpp = 4; break;
            case MTLPixelFormatRGBA16Float: case MTLPixelFormatRGBA16Unorm: bpp = 8; break;
            case MTLPixelFormatR8Unorm: case MTLPixelFormatA8Unorm: bpp = 1; break;
            case MTLPixelFormatR16Float: case MTLPixelFormatRG8Unorm: case MTLPixelFormatR16Unorm: bpp = 2; break;
            case MTLPixelFormatRGBA32Float: bpp = 16; break;
            default: bpp = 0;
        }
        id<MTLTexture> src = tex;
        if (bpp && tex.storageMode == MTLStorageModePrivate) {
            MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:tex.pixelFormat width:tex.width height:tex.height mipmapped:NO];
            d.textureType = tex.textureType; d.storageMode = MTLStorageModeShared; d.usage = MTLTextureUsageShaderRead;
            id<MTLTexture> copy = [tex.device newTextureWithDescriptor:d];
            id<MTLCommandBuffer> cb = [blitQueue commandBuffer];
            id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
            NSUInteger slices = tex.textureType == MTLTextureTypeCube ? 6 : 1;
            for (NSUInteger s = 0; s < slices; s++)
                [blit copyFromTexture:tex sourceSlice:s sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(tex.width, tex.height, 1)
                            toTexture:copy destinationSlice:s destinationLevel:0 destinationOrigin:MTLOriginMake(0, 0, 0)];
            [blit endEncoding]; [cb commit]; [cb waitUntilCompleted];
            src = copy;
            info[@"readback"] = @"blit";
        }
        if (bpp) {
            NSUInteger slices = tex.textureType == MTLTextureTypeCube ? 6 : 1;
            NSMutableData *data = [NSMutableData dataWithLength:tex.width * tex.height * bpp * slices];
            for (NSUInteger s = 0; s < slices; s++) {
                [src getBytes:(char *)data.mutableBytes + s * tex.width * tex.height * bpp bytesPerRow:tex.width * bpp bytesPerImage:tex.width * tex.height * bpp
                   fromRegion:MTLRegionMake2D(0, 0, tex.width, tex.height) mipmapLevel:0 slice:s];
            }
            NSString *base = [NSString stringWithFormat:@"tex-%@-%@%lu-%lu-%lux%lu-%@", [fn stringByReplacingOccurrencesOfString:@"::" withString:@"_"], stage, (unsigned long)index,
                              (unsigned long)texCounter++, (unsigned long)tex.width, (unsigned long)tex.height,
                              [[label stringByReplacingOccurrencesOfString:@"/" withString:@"_"] stringByReplacingOccurrencesOfString:@" " withString:@"_"]];
            [data writeToFile:[outDir stringByAppendingPathComponent:[base stringByAppendingString:@".raw"]] atomically:YES];
            info[@"raw"] = [base stringByAppendingString:@".raw"];
            info[@"bytesPerPixel"] = @(bpp);
            rawByPointer[[NSString stringWithFormat:@"%p", (__bridge void *)tex]] = info[@"raw"];
        }
    }
    textureRecords[key] = info;
}

typedef void (*SetBytesIMP)(id, SEL, const void *, NSUInteger, NSUInteger);
typedef void (*SetBufferIMP)(id, SEL, id, NSUInteger, NSUInteger);
typedef void (*SetTextureIMP)(id, SEL, id, NSUInteger);
typedef void (*SetStateIMP)(id, SEL, id);
typedef void (*SetBuffersIMP)(id, SEL, const id *, const NSUInteger *, NSRange);
typedef void (*SetTexturesIMP)(id, SEL, const id *, NSRange);
typedef void (*SetOffsetIMP)(id, SEL, NSUInteger, NSUInteger);

static void rememberBuffer(id encoder, NSString *stage, NSUInteger index, id<MTLBuffer> buf) {
    NSMutableDictionary *d = [lastBuffers objectForKey:encoder];
    if (!d) { d = [NSMutableDictionary dictionary]; [lastBuffers setObject:d forKey:encoder]; }
    NSString *k = [NSString stringWithFormat:@"%@|%lu", stage, (unsigned long)index];
    if (buf) d[k] = buf; else [d removeObjectForKey:k];
}

static void recordBuffer(id encoder, NSString *stage, NSUInteger index, id<MTLBuffer> buf, NSUInteger offset, NSString *how) {
    if (buf && buf.storageMode != MTLStorageModePrivate && buf.contents && offset < buf.length)
        recordBytes(encoder, stage, index, (const char *)buf.contents + offset, buf.length - offset, how);
}

static void hookEncoder(Class cls) {
    struct { SEL sel; NSString *stage; int kind; } hooks[] = {
        {@selector(setFragmentBytes:length:atIndex:), @"F", 0}, {@selector(setVertexBytes:length:atIndex:), @"V", 0},
        {@selector(setFragmentBuffer:offset:atIndex:), @"F", 1}, {@selector(setVertexBuffer:offset:atIndex:), @"V", 1},
        {@selector(setFragmentTexture:atIndex:), @"F", 2}, {@selector(setVertexTexture:atIndex:), @"V", 2},
        {@selector(setRenderPipelineState:), @"", 3},
        {@selector(setFragmentBuffers:offsets:withRange:), @"F", 4}, {@selector(setVertexBuffers:offsets:withRange:), @"V", 4},
        {@selector(setFragmentTextures:withRange:), @"F", 5}, {@selector(setVertexTextures:withRange:), @"V", 5},
        {@selector(setFragmentBufferOffset:atIndex:), @"F", 6}, {@selector(setVertexBufferOffset:atIndex:), @"V", 6},
    };
    for (int i = 0; i < 13; i++) {
        Method m = class_getInstanceMethod(cls, hooks[i].sel);
        if (!m) { NSLog(@"no method %@ on %@", NSStringFromSelector(hooks[i].sel), cls); continue; }
        IMP orig = method_getImplementation(m);
        NSString *stage = hooks[i].stage;
        SEL sel = hooks[i].sel;
        IMP repl = NULL;
        if (hooks[i].kind == 0) {
            repl = imp_implementationWithBlock(^(id self, const void *bytes, NSUInteger length, NSUInteger index) {
                recordBytes(self, stage, index, bytes, length, @"bytes"); ((SetBytesIMP)orig)(self, sel, bytes, length, index); });
        } else if (hooks[i].kind == 1) {
            repl = imp_implementationWithBlock(^(id self, id<MTLBuffer> buf, NSUInteger offset, NSUInteger index) {
                rememberBuffer(self, stage, index, buf); recordBuffer(self, stage, index, buf, offset, @"buffer");
                ((SetBufferIMP)orig)(self, sel, buf, offset, index); });
        } else if (hooks[i].kind == 2) {
            repl = imp_implementationWithBlock(^(id self, id<MTLTexture> tex, NSUInteger index) {
                recordTexture(self, stage, index, tex);
                if ([stage isEqualToString:@"F"] && (index == 7 || index == 8) && tex) {
                    NSMutableDictionary *d = [lastBuffers objectForKey:self];
                    if (!d) { d = [NSMutableDictionary dictionary]; [lastBuffers setObject:d forKey:self]; }
                    NSString *raw = rawByPointer[[NSString stringWithFormat:@"%p", (__bridge void *)tex]];
                    if (raw) d[[NSString stringWithFormat:@"T%lu", (unsigned long)index]] = raw;
                    if (index == 8 && d[@"T7"] && d[@"T8"]) {         // VectorKit binds 7 then 8 per draw
                        NSDictionary *pair = @{@"styleIndex": d[@"T7"], @"styleTexture": d[@"T8"]};
                        if (![draws.lastObject isEqualToDictionary:pair]) [draws addObject:pair];
                    }
                }
                ((SetTextureIMP)orig)(self, sel, tex, index); });
        } else if (hooks[i].kind == 3) {
            repl = imp_implementationWithBlock(^(id self, id state) {
                if (state) [currentPipeline setObject:state forKey:self]; ((SetStateIMP)orig)(self, sel, state); });
        } else if (hooks[i].kind == 4) {
            repl = imp_implementationWithBlock(^(id self, const id *bufs, const NSUInteger *offs, NSRange range) {
                for (NSUInteger j = 0; j < range.length; j++) { rememberBuffer(self, stage, range.location + j, bufs[j]); recordBuffer(self, stage, range.location + j, bufs[j], offs[j], @"buffers"); }
                ((SetBuffersIMP)orig)(self, sel, bufs, offs, range); });
        } else if (hooks[i].kind == 5) {
            repl = imp_implementationWithBlock(^(id self, const id *texs, NSRange range) {
                for (NSUInteger j = 0; j < range.length; j++) recordTexture(self, stage, range.location + j, texs[j]);
                if ([stage isEqualToString:@"F"] && range.location <= 7 && range.location + range.length > 8) {
                    id<MTLTexture> t7 = texs[7 - range.location], t8 = texs[8 - range.location];
                    NSString *r7 = t7 ? rawByPointer[[NSString stringWithFormat:@"%p", (__bridge void *)t7]] : nil;
                    NSString *r8 = t8 ? rawByPointer[[NSString stringWithFormat:@"%p", (__bridge void *)t8]] : nil;
                    if (r7 && r8) [draws addObject:@{@"styleIndex": r7, @"styleTexture": r8}];
                }
                ((SetTexturesIMP)orig)(self, sel, texs, range); });
        } else {
            repl = imp_implementationWithBlock(^(id self, NSUInteger offset, NSUInteger index) {
                NSMutableDictionary *d = [lastBuffers objectForKey:self];
                id<MTLBuffer> buf = d[[NSString stringWithFormat:@"%@|%lu", stage, (unsigned long)index]];
                recordBuffer(self, stage, index, buf, offset, @"offset");
                ((SetOffsetIMP)orig)(self, sel, offset, index); });
        }
        method_setImplementation(m, repl);
    }
}

typedef id (*NewPSOIMP)(id, SEL, MTLRenderPipelineDescriptor *, NSError **);
typedef id (*NewPSOOptIMP)(id, SEL, MTLRenderPipelineDescriptor *, MTLPipelineOption, id *, NSError **);

static void rememberPSO(id state, MTLRenderPipelineDescriptor *desc) {
    if (!state) return;
    pipelineNames[[NSValue valueWithPointer:(__bridge const void *)state]] = @{@"frag": desc.fragmentFunction.name ?: @"", @"vert": desc.vertexFunction.name ?: @""};
}

static void hookDevice(id<MTLDevice> device) {
    Class cls = object_getClass(device);
    Method m1 = class_getInstanceMethod(cls, @selector(newRenderPipelineStateWithDescriptor:error:));
    IMP o1 = method_getImplementation(m1);
    method_setImplementation(m1, imp_implementationWithBlock(^id(id self, MTLRenderPipelineDescriptor *desc, NSError **err) {
        id st = ((NewPSOIMP)o1)(self, @selector(newRenderPipelineStateWithDescriptor:error:), desc, err); rememberPSO(st, desc); return st; }));
    Method m2 = class_getInstanceMethod(cls, @selector(newRenderPipelineStateWithDescriptor:options:reflection:error:));
    IMP o2 = method_getImplementation(m2);
    method_setImplementation(m2, imp_implementationWithBlock(^id(id self, MTLRenderPipelineDescriptor *desc, MTLPipelineOption opt, id *refl, NSError **err) {
        id st = ((NewPSOOptIMP)o2)(self, @selector(newRenderPipelineStateWithDescriptor:options:reflection:error:), desc, opt, refl, err); rememberPSO(st, desc); return st; }));
    Method m3 = class_getInstanceMethod(cls, @selector(newRenderPipelineStateWithDescriptor:completionHandler:));
    if (m3) {
        IMP o3 = method_getImplementation(m3);
        method_setImplementation(m3, imp_implementationWithBlock(^(id self, MTLRenderPipelineDescriptor *desc, void (^handler)(id, NSError *)) {
            ((void (*)(id, SEL, id, id))o3)(self, @selector(newRenderPipelineStateWithDescriptor:completionHandler:), desc, ^(id st, NSError *e) { rememberPSO(st, desc); handler(st, e); }); }));
    }
    Method m4 = class_getInstanceMethod(cls, @selector(newRenderPipelineStateWithDescriptor:options:completionHandler:));
    if (m4) {
        IMP o4 = method_getImplementation(m4);
        method_setImplementation(m4, imp_implementationWithBlock(^(id self, MTLRenderPipelineDescriptor *desc, MTLPipelineOption opt, void (^handler)(id, id, NSError *)) {
            ((void (*)(id, SEL, id, MTLPipelineOption, id))o4)(self, @selector(newRenderPipelineStateWithDescriptor:options:completionHandler:), desc, opt, ^(id st, id r, NSError *e) { rememberPSO(st, desc); handler(st, r, e); }); }));
    }
}

int main(int argc, char **argv) {
    @autoreleasepool {
        double lat = atof(argv[1]), lng = atof(argv[2]), dlat = atof(argv[3]), dlng = atof(argv[4]);
        outDir = [NSString stringWithUTF8String:argv[5]];
        double seconds = argc > 6 ? atof(argv[6]) : 12;
        double pitch = argc > 7 ? atof(argv[7]) : 0, heading = argc > 8 ? atof(argv[8]) : 0;
        BOOL dark = argc > 9 && atoi(argv[9]);
        [[NSFileManager defaultManager] createDirectoryAtPath:outDir withIntermediateDirectories:YES attributes:nil error:nil];
        pipelineNames = [NSMutableDictionary dictionary]; records = [NSMutableDictionary dictionary];
        textureRecords = [NSMutableDictionary dictionary]; seenTextures = [NSMutableSet set];
        currentPipeline = [NSMapTable weakToStrongObjectsMapTable];
        lastBuffers = [NSMapTable weakToStrongObjectsMapTable];
        rawByPointer = [NSMutableDictionary dictionary]; draws = [NSMutableArray array];
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        hookDevice(device);
        blitQueue = [device newCommandQueue];
        // learn the concrete encoder class from a throwaway encoder on the same device
        id<MTLCommandQueue> q = [device newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget;
        id<MTLTexture> t = [device newTextureWithDescriptor:td];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = t; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        Class encCls = object_getClass(enc);
        NSLog(@"encoder class %@", encCls);
        [enc endEncoding]; [cb commit];
        hookEncoder(encCls);

        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyAccessory];
        NSWindow *win = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 1280, 744) styleMask:NSWindowStyleMaskTitled backing:NSBackingStoreBuffered defer:NO];
        MKMapView *map = [[MKMapView alloc] initWithFrame:win.contentView.bounds];
        map.preferredConfiguration = [[MKStandardMapConfiguration alloc] initWithElevationStyle:MKMapElevationStyleRealistic];
        [map setRegion:MKCoordinateRegionMake(CLLocationCoordinate2DMake(lat, lng), MKCoordinateSpanMake(dlat, dlng)) animated:NO];
        if (pitch || heading) {
            MKMapCamera *cam = [map.camera copy];
            cam.pitch = pitch; cam.heading = heading;
            [map setCamera:cam animated:NO];
        }
        if (dark) map.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
        [win.contentView addSubview:map];
        [win orderFrontRegardless];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(seconds * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            NSMutableDictionary *out = [NSMutableDictionary dictionary];
            out[@"pipelines"] = [pipelineNames allValues];
            out[@"buffers"] = records;
            out[@"textures"] = [textureRecords allValues];
            out[@"encoderClass"] = NSStringFromClass(encCls);
            out[@"draws"] = draws;
            NSData *json = [NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted error:nil];
            [json writeToFile:[outDir stringByAppendingPathComponent:@"capture.json"] atomically:YES];
            NSLog(@"wrote %@ (%lu buffer keys, %lu textures, %lu pipelines)", outDir, (unsigned long)records.count, (unsigned long)textureRecords.count, (unsigned long)pipelineNames.count);
            [app terminate:nil];
        });
        [app run];
    }
    return 0;
}
