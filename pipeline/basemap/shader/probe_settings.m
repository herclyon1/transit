// Print VectorKit's VKDebugSettings defaults that feed the shader constants (names taken from the decompiled
// md::GlobeSkyRenderLayer::layout / md::LightingLogic::writeLogicContext).
//   clang -fobjc-arc -framework Foundation -o /tmp/probe_settings probe_settings.m && /tmp/probe_settings
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#import <objc/runtime.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        if (!dlopen("/System/Library/PrivateFrameworks/VectorKit.framework/VectorKit", RTLD_NOW)) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 1; }
        Class cls = NSClassFromString(@"VKDebugSettings");
        unsigned n = 0; Method *ms = class_copyMethodList(object_getClass(cls), &n);
        for (unsigned i = 0; i < n && argc > 1; i++) printf("+%s\n", sel_getName(method_getName(ms[i])));
        free(ms);
        id s = [cls performSelector:NSSelectorFromString(@"sharedSettingsExt")];
        NSArray *keys = @[@"daVinciAtmosphereMaxHeight", @"daVinciAtmosphereColorMidpoint", @"lightingEnableAmbient", @"lightingEnableLight1",
                          @"lightingCameraLocalTime", @"lightingAccelerateTime"];
        for (NSString *k in keys) {
            @try { printf("%s = %s\n", k.UTF8String, [[s valueForKey:k] description].UTF8String); }
            @catch (NSException *e) { printf("%s = <%s>\n", k.UTF8String, e.name.UTF8String); }
        }
    }
    return 0;
}
