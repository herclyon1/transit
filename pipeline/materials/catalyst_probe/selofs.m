// Windowless Mac Catalyst helper: prints the shared-cache offsets of selectors (what a dylib's __objc_selrefs holds
// after dyld's selector uniquing), so call sites in an extracted iOSSupport dylib can be matched to selector names.
//   clang -fobjc-arc -target arm64-apple-ios26.0-macabi -isysroot $SDK -framework Foundation -o /tmp/selofs selofs.m
//   /tmp/selofs 'initWithBlurEffectStyle:' 'effectWithStyle:'
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import <dlfcn.h>

extern const void *_dyld_get_shared_cache_range(size_t *length);

int main(int argc, char **argv) {
    @autoreleasepool {
        dlopen("/System/iOSSupport/System/Library/PrivateFrameworks/MapsUI.framework/MapsUI", RTLD_NOW);
        size_t len = 0;
        const char *base = _dyld_get_shared_cache_range(&len);
        printf("cache base %p len %zx\n", base, len);
        for (int i = 1; i < argc; i++) {
            SEL s = sel_registerName(argv[i]);
            printf("%s\t%p\t%#lx\n", argv[i], (void *)s, (unsigned long)((const char *)s - base));
        }
    }
    return 0;
}
