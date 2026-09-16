// Print GeoServices' tile-set table: style id -> enum name -> URL template, read from the live resource manifest
// (GEOResourceManifestConfiguration / GEOActiveTileGroup) through the private GeoServices API.
//   clang -fobjc-arc -framework Foundation -o /tmp/tilesets tilesets.m && /tmp/tilesets
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#import <objc/runtime.h>
#import <objc/message.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        if (!dlopen("/System/Library/PrivateFrameworks/GeoServices.framework/GeoServices", RTLD_NOW)) { fprintf(stderr, "%s\n", dlerror()); return 1; }
        Class cfg = NSClassFromString(@"GEOResourceManifestConfiguration");
        Class mgr = NSClassFromString(@"GEOResourceManifestManager");
        id manager = ((id (*)(id, SEL, id))objc_msgSend)(mgr, NSSelectorFromString(@"modernManagerForConfiguration:"), ((id (*)(id, SEL))objc_msgSend)(cfg, NSSelectorFromString(@"defaultConfiguration")));
        id group = ((id (*)(id, SEL))objc_msgSend)(manager, NSSelectorFromString(@"activeTileGroup"));
        if (!group) { fprintf(stderr, "no active tile group\n"); return 2; }
        Class ts = NSClassFromString(@"GEOActiveTileSet");
        NSArray *sets = ((id (*)(id, SEL))objc_msgSend)(group, NSSelectorFromString(@"tileSets"));
        printf("style\tname\tsize\tscale\tchecksum\turl\n");
        for (id s in sets) {
            long style = ((long (*)(id, SEL))objc_msgSend)(s, NSSelectorFromString(@"style"));
            NSString *name = ((id (*)(id, SEL, long))objc_msgSend)(s, NSSelectorFromString(@"styleAsString:"), style);
            long size = ((long (*)(id, SEL))objc_msgSend)(s, NSSelectorFromString(@"size"));
            long scale = ((long (*)(id, SEL))objc_msgSend)(s, NSSelectorFromString(@"scale"));
            long ck = ((long (*)(id, SEL))objc_msgSend)(s, NSSelectorFromString(@"checksumType"));
            NSString *ckn = ((id (*)(id, SEL, long))objc_msgSend)(s, NSSelectorFromString(@"checksumTypeAsString:"), ck);
            id url = nil;
            @try { url = [s valueForKey:@"baseURL"]; } @catch (id e) {}
            if (!url) { @try { url = [s valueForKey:@"urlTemplate"]; } @catch (id e) {} }
            printf("%ld\t%s\t%ld\t%ld\t%s\t%s\n", style, name.UTF8String, size, scale, ckn.UTF8String, [[url description] UTF8String] ?: "");
        }
        (void)ts;
    }
    return 0;
}
