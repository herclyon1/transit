// Instantiate AppKit's system materials in-process and dump the CoreAnimation layer trees they produce:
// every NSVisualEffectMaterial (light + dark appearance, behindWindow / withinWindow) and NSGlassEffectView
// (macOS 26) — layer class, backdrop filters (CAFilter name + parameters), background/tint colours, opacity,
// compositing filter, luminance settings.  Reads the material definitions through the public views; nothing is
// sampled from the screen.
//
//   clang -fobjc-arc -framework AppKit -framework QuartzCore -o /tmp/dump_appkit_materials dump_appkit_materials.m
//   /tmp/dump_appkit_materials out.json
#import <AppKit/AppKit.h>
#import <QuartzCore/QuartzCore.h>
#import <objc/runtime.h>

static id jsonable(id v, int depth);

static id colorJSON(CGColorRef c) {
    if (!c) return [NSNull null];
    const CGFloat *k = CGColorGetComponents(c);
    size_t n = CGColorGetNumberOfComponents(c);
    NSMutableArray *a = [NSMutableArray array];
    for (size_t i = 0; i < n; i++) [a addObject:@(k[i])];
    CGColorSpaceRef cs = CGColorGetColorSpace(c);
    NSString *name = cs ? (__bridge_transfer NSString *)CGColorSpaceCopyName(cs) : nil;
    return @{@"components": a, @"space": name ?: @"?"};
}

static id jsonable(id v, int depth) {
    if (!v || v == [NSNull null]) return [NSNull null];
    if ([v isKindOfClass:[NSNumber class]]) { double d = [v doubleValue]; return isfinite(d) ? v : @"nan"; }
    if ([v isKindOfClass:[NSString class]]) return v;
    if ([v isKindOfClass:[NSArray class]]) { NSMutableArray *a = [NSMutableArray array]; for (id x in v) [a addObject:jsonable(x, depth + 1)]; return a; }
    if ([v isKindOfClass:[NSDictionary class]]) { NSMutableDictionary *d = [NSMutableDictionary dictionary]; for (id k in v) d[[k description]] = jsonable(v[k], depth + 1); return d; }
    if ([v isKindOfClass:[NSColor class]]) return colorJSON([(NSColor *)v CGColor]);
    if (CFGetTypeID((__bridge CFTypeRef)v) == CGColorGetTypeID()) return colorJSON((__bridge CGColorRef)v);
    if ([v isKindOfClass:[NSData class]] && [(NSData *)v length] % 4 == 0 && [(NSData *)v length] <= 4096) {
        NSMutableArray *a = [NSMutableArray array];
        const float *f = [(NSData *)v bytes];
        for (NSUInteger i = 0; i < [(NSData *)v length] / 4; i++) [a addObject:isfinite(f[i]) ? @(f[i]) : @"nan"];
        return a;
    }
    if ([v isKindOfClass:[NSValue class]]) {                    // CAColorMatrix etc.: struct of floats
        NSUInteger sz = 0; NSGetSizeAndAlignment([(NSValue *)v objCType], &sz, NULL);
        if (sz % 4 == 0 && sz <= 1024) {
            float buf[256]; [(NSValue *)v getValue:buf size:sz];
            NSMutableArray *a = [NSMutableArray array];
            for (NSUInteger i = 0; i < sz / 4; i++) [a addObject:isfinite(buf[i]) ? @(buf[i]) : @"nan"];
            return a;
        }
        return [v description];
    }
    return [NSString stringWithFormat:@"<%@>", NSStringFromClass([v class])];
}

// CAFilter is private: read its name and every input via KVC
static id filterJSON(id f) {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    d[@"class"] = NSStringFromClass([f class]);
    @try { d[@"name"] = [f valueForKey:@"name"] ?: @""; } @catch (id e) {}
    @try { d[@"type"] = [f valueForKey:@"type"] ?: @""; } @catch (id e) {}
    @try { d[@"enabled"] = [f valueForKey:@"enabled"]; } @catch (id e) {}
    NSArray *keys = nil;
    @try { keys = [[f class] performSelector:NSSelectorFromString(@"inputKeysForFilterType:") withObject:d[@"type"]]; } @catch (id e) {}
    if (!keys) { @try { keys = [f valueForKey:@"inputKeys"]; } @catch (id e) {} }
    NSMutableDictionary *inputs = [NSMutableDictionary dictionary];
    for (NSString *k in keys) { @try { inputs[k] = jsonable([f valueForKey:k], 0); } @catch (id e) {} }
    // also the well-known keys, in case inputKeys is not exposed
    for (NSString *k in @[@"inputRadius", @"inputAmount", @"inputColorMatrix", @"inputSaturation", @"inputBrightness", @"inputContrast", @"inputOpacity", @"inputColor", @"inputHardEdges", @"inputNormalizeEdges", @"inputQuality", @"inputBounds", @"inputScale", @"inputCurvature", @"inputHeight", @"inputAngle", @"inputSpread", @"inputMaskOffset", @"inputGlobal"]) {
        if (inputs[k]) continue;
        @try { id v = [f valueForKey:k]; if (v) inputs[k] = jsonable(v, 0); } @catch (id e) {}
    }
    d[@"inputs"] = inputs;
    return d;
}

static id layerJSON(CALayer *l, int depth) {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    d[@"class"] = NSStringFromClass([l class]);
    d[@"name"] = l.name ?: @"";
    d[@"frame"] = NSStringFromRect(l.frame);
    d[@"opacity"] = @(l.opacity);
    d[@"hidden"] = @(l.hidden);
    d[@"cornerRadius"] = @(l.cornerRadius);
    if (l.backgroundColor) d[@"backgroundColor"] = colorJSON(l.backgroundColor);
    if (l.compositingFilter) d[@"compositingFilter"] = [l.compositingFilter isKindOfClass:[NSString class]] ? l.compositingFilter : filterJSON(l.compositingFilter);
    if (l.filters.count) { NSMutableArray *a = [NSMutableArray array]; for (id f in l.filters) [a addObject:filterJSON(f)]; d[@"filters"] = a; }
    if (l.backgroundFilters.count) { NSMutableArray *a = [NSMutableArray array]; for (id f in l.backgroundFilters) [a addObject:filterJSON(f)]; d[@"backgroundFilters"] = a; }
    if (l.contents) d[@"contents"] = [NSString stringWithFormat:@"<%@>", NSStringFromClass([l.contents class])];
    // CABackdropLayer and friends: dump the private properties that define the material
    for (NSString *k in @[@"scale", @"backdropScale", @"blurRadius", @"saturation", @"brightness", @"luminanceAmount", @"luminanceValues", @"captureOnly", @"disablesOccludedBackdropBlurs", @"marginWidth", @"reducesCaptureBitDepth", @"statisticsEnabled", @"windowServerAware", @"groupName", @"groupNamespace", @"colorMatrix", @"tintColor", @"tintAmount", @"style", @"materialName", @"weighting", @"zoom", @"blurInputQuality", @"averageColorEnabled", @"allowsGroupBlending", @"allowsGroupOpacity", @"allowsEdgeAntialiasing", @"blendMode"]) {
        @try {
            if ([l respondsToSelector:NSSelectorFromString(k)]) { id v = [l valueForKey:k]; if (v) d[k] = jsonable(v, 0); }
        } @catch (id e) {}
    }
    // CAFilter-like objects attached via KVC ("filters" covers most); also dump SDF effects on the layer if any
    @try { id eff = [l valueForKey:@"effects"]; if (eff) d[@"effects"] = jsonable(eff, 0); } @catch (id e) {}
    if (depth < 12 && l.sublayers.count) {
        NSMutableArray *subs = [NSMutableArray array];
        for (CALayer *s in l.sublayers) [subs addObject:layerJSON(s, depth + 1)];
        d[@"sublayers"] = subs;
    }
    return d;
}

static NSDictionary *dumpView(NSView *v, NSWindow *win) {
    [win.contentView addSubview:v];
    [win layoutIfNeeded];
    [v layoutSubtreeIfNeeded];
    [CATransaction flush];
    [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.15]];
    NSDictionary *r = layerJSON(v.layer, 0);
    [v removeFromSuperview];
    return r;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyAccessory];
        NSMutableDictionary *out = [NSMutableDictionary dictionary];
        NSDictionary *materials = @{@"titlebar": @(NSVisualEffectMaterialTitlebar), @"selection": @(NSVisualEffectMaterialSelection), @"menu": @(NSVisualEffectMaterialMenu),
                                    @"popover": @(NSVisualEffectMaterialPopover), @"sidebar": @(NSVisualEffectMaterialSidebar), @"headerView": @(NSVisualEffectMaterialHeaderView),
                                    @"sheet": @(NSVisualEffectMaterialSheet), @"windowBackground": @(NSVisualEffectMaterialWindowBackground), @"hudWindow": @(NSVisualEffectMaterialHUDWindow),
                                    @"fullScreenUI": @(NSVisualEffectMaterialFullScreenUI), @"toolTip": @(NSVisualEffectMaterialToolTip), @"contentBackground": @(NSVisualEffectMaterialContentBackground),
                                    @"underWindowBackground": @(NSVisualEffectMaterialUnderWindowBackground), @"underPageBackground": @(NSVisualEffectMaterialUnderPageBackground)};
        for (NSString *appearanceName in @[NSAppearanceNameAqua, NSAppearanceNameDarkAqua]) {
            NSWindow *win = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 400, 300) styleMask:NSWindowStyleMaskTitled backing:NSBackingStoreBuffered defer:NO];
            win.appearance = [NSAppearance appearanceNamed:appearanceName];
            [win orderFrontRegardless];
            NSMutableDictionary *perAppearance = [NSMutableDictionary dictionary];
            for (NSString *name in materials) {
                for (NSNumber *mode in @[@(NSVisualEffectBlendingModeBehindWindow), @(NSVisualEffectBlendingModeWithinWindow)]) {
                    NSVisualEffectView *v = [[NSVisualEffectView alloc] initWithFrame:NSMakeRect(20, 20, 300, 200)];
                    v.material = [materials[name] integerValue];
                    v.blendingMode = [mode integerValue];
                    v.state = NSVisualEffectStateActive;
                    v.wantsLayer = YES;
                    perAppearance[[NSString stringWithFormat:@"visualEffect.%@.%@", name, [mode integerValue] == NSVisualEffectBlendingModeBehindWindow ? @"behindWindow" : @"withinWindow"]] = dumpView(v, win);
                }
            }
            Class glassCls = NSClassFromString(@"NSGlassEffectView");
            if (glassCls) {
                for (NSNumber *style in @[@0, @1]) {           // NSGlassEffectViewStyle regular / clear
                    NSView *g = [[glassCls alloc] initWithFrame:NSMakeRect(20, 20, 300, 200)];
                    @try { [g setValue:style forKey:@"style"]; } @catch (id e) {}
                    @try { [g setValue:@12 forKey:@"cornerRadius"]; } @catch (id e) {}
                    NSView *content = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 300, 200)];
                    @try { [g setValue:content forKey:@"contentView"]; } @catch (id e) {}
                    perAppearance[[NSString stringWithFormat:@"glass.style%@", style]] = dumpView(g, win);
                    NSView *g2 = [[glassCls alloc] initWithFrame:NSMakeRect(20, 20, 300, 200)];
                    @try { [g2 setValue:style forKey:@"style"]; [g2 setValue:[NSColor colorWithRed:0.2 green:0.5 blue:1 alpha:1] forKey:@"tintColor"]; } @catch (id e) {}
                    perAppearance[[NSString stringWithFormat:@"glass.style%@.tinted", style]] = dumpView(g2, win);
                }
            }
            // NSPopover (what a Catalyst UIPopoverPresentationController becomes on the Mac) and an NSMenu-style window
            NSPopover *pop = [[NSPopover alloc] init];
            NSViewController *pvc = [[NSViewController alloc] init];
            pvc.view = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 240, 160)];
            pop.contentViewController = pvc;
            pop.behavior = NSPopoverBehaviorApplicationDefined;
            [pop showRelativeToRect:NSMakeRect(100, 100, 10, 10) ofView:win.contentView preferredEdge:NSRectEdgeMaxY];
            [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.4]];
            NSWindow *pw = pvc.view.window;
            if (pw) {
                NSView *frameView = pw.contentView.superview;
                perAppearance[@"popover.NSPopover"] = @{@"frameViewClass": NSStringFromClass([frameView class]), @"layers": layerJSON(frameView.layer ?: pw.contentView.layer, 0)};
            }
            [pop close];
            out[appearanceName] = perAppearance;
            [win orderOut:nil];
        }
        // QuartzCore SDF glass effect defaults
        NSMutableDictionary *sdf = [NSMutableDictionary dictionary];
        for (NSString *cn in @[@"CASDFGlassHighlightEffect", @"CASDFGlassDisplacementEffect"]) {
            Class c = NSClassFromString(cn);
            if (!c) continue;
            NSMutableDictionary *e = [NSMutableDictionary dictionary];
            @try { e[@"defaultValues"] = jsonable([c performSelector:@selector(defaultValues)], 0); } @catch (id ex) {}
            @try { e[@"CA_attributes"] = jsonable([c performSelector:NSSelectorFromString(@"CA_attributes")], 0); } @catch (id ex) {}
            @try { e[@"name"] = [c performSelector:@selector(name)]; } @catch (id ex) {}
            sdf[cn] = e;
        }
        out[@"QuartzCore.SDFGlassEffects"] = sdf;
        NSData *json = [NSJSONSerialization dataWithJSONObject:out options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys error:nil];
        [json writeToFile:[NSString stringWithUTF8String:argv[1]] atomically:YES];
        printf("wrote %s\n", argv[1]);
    }
    return 0;
}
