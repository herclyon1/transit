// Mac Catalyst probe: the Maps app is a Catalyst app (it links /System/iOSSupport UIKit, SwiftUI, MapsUI), so its
// materials are UIKit's.  This app instantiates every UIBlurEffect system style, UIGlassEffect (regular / clear /
// tinted / interactive), a UISplitViewController sidebar column, a popover and a navigation bar, and dumps the
// CoreAnimation layer trees UIKit builds for them on this Mac (backdrop filters, CoreMaterial recipe names, tints).
//
//   build.sh  (see next to this file)  →  probe.app ; run probe.app/Contents/MacOS/probe out.json
#import <UIKit/UIKit.h>
#import <QuartzCore/QuartzCore.h>
#import <objc/runtime.h>
#import <objc/message.h>

static id jsonable(id v);

static id colorJSON(CGColorRef c) {
    if (!c) return [NSNull null];
    const CGFloat *k = CGColorGetComponents(c);
    NSMutableArray *a = [NSMutableArray array];
    for (size_t i = 0; i < CGColorGetNumberOfComponents(c); i++) [a addObject:@(k[i])];
    CGColorSpaceRef cs = CGColorGetColorSpace(c);
    NSString *name = cs ? (__bridge_transfer NSString *)CGColorSpaceCopyName(cs) : nil;
    return @{@"components": a, @"space": name ?: @"?"};
}

static id jsonable(id v) {
    if (!v || v == [NSNull null]) return [NSNull null];
    if ([v isKindOfClass:[NSNumber class]]) { double d = [v doubleValue]; return isfinite(d) ? v : @"nan"; }
    if ([v isKindOfClass:[NSString class]]) return v;
    if ([v isKindOfClass:[NSArray class]]) { NSMutableArray *a = [NSMutableArray array]; for (id x in v) [a addObject:jsonable(x)]; return a; }
    if ([v isKindOfClass:[NSDictionary class]]) { NSMutableDictionary *d = [NSMutableDictionary dictionary]; for (id k in v) d[[k description]] = jsonable(v[k]); return d; }
    if ([v isKindOfClass:[UIColor class]]) return colorJSON([(UIColor *)v CGColor]);
    if (CFGetTypeID((__bridge CFTypeRef)v) == CGColorGetTypeID()) return colorJSON((__bridge CGColorRef)v);
    if ([v isKindOfClass:[NSData class]] && [(NSData *)v length] % 4 == 0 && [(NSData *)v length] <= 4096) {
        NSMutableArray *a = [NSMutableArray array]; const float *f = [(NSData *)v bytes];
        for (NSUInteger i = 0; i < [(NSData *)v length] / 4; i++) [a addObject:isfinite(f[i]) ? @(f[i]) : @"nan"];
        return a;
    }
    if ([v isKindOfClass:[NSValue class]]) {
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

static id filterJSON(id f) {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    d[@"class"] = NSStringFromClass([f class]);
    @try { d[@"name"] = [f valueForKey:@"name"] ?: @""; } @catch (id e) {}
    @try { d[@"type"] = [f valueForKey:@"type"] ?: @""; } @catch (id e) {}
    NSArray *keys = nil;
    @try { keys = [[f class] performSelector:NSSelectorFromString(@"inputKeysForFilterType:") withObject:d[@"type"]]; } @catch (id e) {}
    NSMutableDictionary *inputs = [NSMutableDictionary dictionary];
    for (NSString *k in keys) { @try { id v = [f valueForKey:k]; if (v) inputs[k] = jsonable(v); } @catch (id e) {} }
    // glassBackground (DLCAFilter) does not answer inputKeysForFilterType:; its keys were enumerated from AppKit's NSGlassEffectView dump
    for (NSString *k in @[@"inputRadius", @"inputAmount", @"inputColorMatrix", @"inputSaturation", @"inputBrightness", @"inputQuality", @"inputNormalizeEdges", @"inputHardEdges",
                          @"inputAberrationAmount", @"inputAberrationAngle", @"inputAberrationHeight", @"inputAberrationOffset", @"inputBleedAmount", @"inputBleedBlurRadius", @"inputBleedColorMatrixBlack", @"inputBleedColorMatrixFillColor", @"inputBleedColorMatrixSaturation", @"inputBleedColorMatrixWhite", @"inputBleedDarkenBlend", @"inputBleedDistance0", @"inputBleedDistance1", @"inputBleedHeight", @"inputBleedOpacity", @"inputBlurDistance0", @"inputBlurDistance1", @"inputBlurDistance2", @"inputBlurDistance3", @"inputBlurDistance4", @"inputBlurFillBlurRadius", @"inputBlurFillDarkenOpacity", @"inputBlurFillLightenOpacity", @"inputBlurFillNormalOpacity", @"inputBlurOpacity0", @"inputBlurOpacity1", @"inputBlurOpacity2", @"inputBlurOpacity3", @"inputBlurOpacity4", @"inputBlurRadius", @"inputClamp", @"inputClampPreserveHue", @"inputFaceColorMatrixBlack", @"inputFaceColorMatrixFillColor", @"inputFaceColorMatrixMaxLuma", @"inputFaceColorMatrixMaxLumaSDR", @"inputFaceColorMatrixSaturation", @"inputFaceColorMatrixWhite", @"inputFaceOpacity", @"inputInnerRefractionAmount", @"inputInnerRefractionHeight", @"inputKeyFillHighlightAmount", @"inputKeyFillHighlightAngle", @"inputKeyFillHighlightColorBias", @"inputKeyFillHighlightEffectOffset", @"inputKeyFillHighlightHeight", @"inputKeyFillHighlightSpread", @"inputKeyFillHighlightSpreadSDR", @"inputMaxHeadroom", @"inputOuterRefractionAmount", @"inputOuterRefractionHeight", @"inputRefractionDistance0", @"inputRefractionDistance1", @"inputRefractionOpacity", @"inputRingShadowBlurRadius", @"inputRingShadowMask", @"inputRingShadowOffset", @"inputRingShadowOpacity", @"inputRingShadowStrokeWidth", @"inputSDRGradientDistance0", @"inputSDRGradientDistance1", @"inputSDRHoldingToneEnabled", @"inputSDRHoldingToneWhite", @"inputSDRShadowOpacity", @"inputShadowAmount", @"inputShadowBlurRadius", @"inputShadowColorMatrixBlack", @"inputShadowColorMatrixFillColor", @"inputShadowColorMatrixSaturation", @"inputShadowColorMatrixWhite", @"inputShadowDistanceOffset", @"inputShadowHeight", @"inputShadowOffset", @"inputShadowOpacity", @"inputShadowRadius", @"inputShadowVibrancyContribution", @"inputSourceSublayerName"]) {
        if (inputs[k]) continue;
        @try { id v = [f valueForKey:k]; if (v) inputs[k] = jsonable(v); } @catch (id e) {}
    }
    d[@"inputs"] = inputs;
    return d;
}

static id layerJSON(CALayer *l, int depth) {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    d[@"class"] = NSStringFromClass([l class]);
    d[@"name"] = l.name ?: @"";
    d[@"frame"] = NSStringFromCGRect(l.frame);
    d[@"opacity"] = @(l.opacity);
    d[@"hidden"] = @(l.hidden);
    d[@"cornerRadius"] = @(l.cornerRadius);
    if ([l.delegate isKindOfClass:[UIView class]]) d[@"view"] = NSStringFromClass([l.delegate class]);
    if (l.backgroundColor) d[@"backgroundColor"] = colorJSON(l.backgroundColor);
    if (l.compositingFilter) d[@"compositingFilter"] = [l.compositingFilter isKindOfClass:[NSString class]] ? l.compositingFilter : filterJSON(l.compositingFilter);
    if (l.filters.count) { NSMutableArray *a = [NSMutableArray array]; for (id f in l.filters) [a addObject:filterJSON(f)]; d[@"filters"] = a; }
    if (l.backgroundFilters.count) { NSMutableArray *a = [NSMutableArray array]; for (id f in l.backgroundFilters) [a addObject:filterJSON(f)]; d[@"backgroundFilters"] = a; }
    for (NSString *k in @[@"scale", @"blurRadius", @"saturation", @"brightness", @"luminanceAmount", @"luminanceValues", @"marginWidth", @"windowServerAware", @"groupName", @"groupNamespace", @"zoom", @"blurInputQuality", @"averageColorEnabled", @"allowsGroupBlending", @"allowsGroupOpacity", @"captureOnly", @"reducesCaptureBitDepth"]) {
        @try { if ([l respondsToSelector:NSSelectorFromString(k)]) { id v = [l valueForKey:k]; if (v) d[k] = jsonable(v); } } @catch (id e) {}
    }
    if (depth < 14 && l.sublayers.count) {
        NSMutableArray *subs = [NSMutableArray array];
        for (CALayer *s in l.sublayers) [subs addObject:layerJSON(s, depth + 1)];
        d[@"sublayers"] = subs;
    }
    return d;
}

// view tree with class names + the recipe name an MTMaterialView carries
static id viewJSON(UIView *v, int depth) {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    d[@"class"] = NSStringFromClass([v class]);
    d[@"frame"] = NSStringFromCGRect(v.frame);
    for (NSString *k in @[@"recipe", @"recipeName", @"recipeNamesByTraitCollection", @"visualStyleSetName", @"configuration", @"weighting", @"materialName", @"_effectiveRecipeName"]) {
        @try { if ([v respondsToSelector:NSSelectorFromString(k)]) { id x = [v valueForKey:k]; if (x) d[k] = jsonable(x); } } @catch (id e) {}
    }
    if ([v isKindOfClass:[UIVisualEffectView class]]) {
        d[@"effect"] = [[(UIVisualEffectView *)v effect] description] ?: @"";
    }
    if (depth < 14 && v.subviews.count) {
        NSMutableArray *subs = [NSMutableArray array];
        for (UIView *s in v.subviews) [subs addObject:viewJSON(s, depth + 1)];
        d[@"subviews"] = subs;
    }
    return d;
}

@interface ProbeDelegate : UIResponder <UIApplicationDelegate>
@end
@interface ProbeSceneDelegate : UIResponder <UIWindowSceneDelegate>
@property (strong) UIWindow *window;
@end

static void pump(double s) { [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:s]]; }

@implementation ProbeDelegate
- (UISceneConfiguration *)application:(UIApplication *)application configurationForConnectingSceneSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options {
    UISceneConfiguration *c = [[UISceneConfiguration alloc] initWithName:@"probe" sessionRole:session.role];
    c.delegateClass = [ProbeSceneDelegate class];
    return c;
}
@end

@implementation ProbeSceneDelegate
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)connectionOptions {
    NSString *out = [[NSProcessInfo processInfo] arguments].count > 1 ? [[NSProcessInfo processInfo] arguments][1] : @"/tmp/catalyst-materials.json";
    NSMutableDictionary *result = [NSMutableDictionary dictionary];
    UIWindow *win = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    win.frame = CGRectMake(0, 0, 900, 600);
    self.window = win;
    UIViewController *root = [UIViewController new];
    root.view.backgroundColor = [UIColor systemBackgroundColor];
    win.rootViewController = root;
    [win makeKeyAndVisible];
    pump(0.5);
    for (NSNumber *styleNum in @[@(UIUserInterfaceStyleLight), @(UIUserInterfaceStyleDark)]) {
        win.overrideUserInterfaceStyle = [styleNum integerValue];
        pump(0.2);
        NSMutableDictionary *per = [NSMutableDictionary dictionary];
        NSDictionary *blurStyles = @{@"systemUltraThinMaterial": @(UIBlurEffectStyleSystemUltraThinMaterial), @"systemThinMaterial": @(UIBlurEffectStyleSystemThinMaterial),
                                     @"systemMaterial": @(UIBlurEffectStyleSystemMaterial), @"systemThickMaterial": @(UIBlurEffectStyleSystemThickMaterial),
                                     @"systemChromeMaterial": @(UIBlurEffectStyleSystemChromeMaterial), @"regular": @(UIBlurEffectStyleRegular), @"prominent": @(UIBlurEffectStyleProminent),
                                     @"light": @(UIBlurEffectStyleLight), @"extraLight": @(UIBlurEffectStyleExtraLight), @"dark": @(UIBlurEffectStyleDark)};
        for (NSString *name in blurStyles) {
            UIVisualEffectView *v = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:[blurStyles[name] integerValue]]];
            v.frame = CGRectMake(40, 40, 300, 200);
            [root.view addSubview:v];
            pump(0.15);
            per[[@"blur." stringByAppendingString:name]] = @{@"views": viewJSON(v, 0), @"layers": layerJSON(v.layer, 0)};
            [v removeFromSuperview];
        }
        Class glassCls = NSClassFromString(@"UIGlassEffect");
        if (glassCls) {
            for (NSNumber *gs in @[@0, @1]) {
                for (NSNumber *variant in @[@0, @1, @2]) {         // plain / tinted / interactive
                    id eff = ((id (*)(id, SEL, NSInteger))objc_msgSend)(glassCls, @selector(effectWithStyle:), [gs integerValue]);
                    if ([variant integerValue] == 1) [eff setValue:[UIColor colorWithRed:0.2 green:0.5 blue:1 alpha:1] forKey:@"tintColor"];
                    if ([variant integerValue] == 2) [eff setValue:@YES forKey:@"interactive"];
                    UIVisualEffectView *v = [[UIVisualEffectView alloc] initWithEffect:eff];
                    v.frame = CGRectMake(40, 40, 300, 200);
                    v.layer.cornerRadius = 20;
                    @try { [v setValue:@20 forKey:@"cornerRadius"]; } @catch (id e) {}
                    [root.view addSubview:v];
                    pump(0.6);
                    per[[NSString stringWithFormat:@"glass.style%@.%@", gs, @[@"plain", @"tinted", @"interactive"][[variant integerValue]]]] = @{@"views": viewJSON(v, 0), @"layers": layerJSON(v.layer, 0), @"window": layerJSON(win.layer, 0)};
                    [v removeFromSuperview];
                }
            }
        }
        // sidebar: UISplitViewController column style
        UISplitViewController *split = [[UISplitViewController alloc] initWithStyle:UISplitViewControllerStyleDoubleColumn];
        UIViewController *side = [UIViewController new]; side.view.backgroundColor = [UIColor clearColor];
        UIViewController *detail = [UIViewController new]; detail.view.backgroundColor = [UIColor systemGreenColor];
        [split setViewController:side forColumn:UISplitViewControllerColumnPrimary];
        [split setViewController:detail forColumn:UISplitViewControllerColumnSecondary];
        split.preferredDisplayMode = UISplitViewControllerDisplayModeOneBesideSecondary;
        win.rootViewController = split;
        pump(0.6);
        per[@"splitView.sidebar"] = @{@"views": viewJSON(split.view, 0), @"layers": layerJSON(split.view.layer, 0)};
        win.rootViewController = root;
        pump(0.2);
        // navigation bar + toolbar
        UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:[UIViewController new]];
        nav.topViewController.title = @"Probe";
        nav.toolbarHidden = NO;
        win.rootViewController = nav;
        pump(0.5);
        per[@"navigationBar"] = @{@"views": viewJSON(nav.navigationBar, 0), @"layers": layerJSON(nav.navigationBar.layer, 0)};
        per[@"toolbar"] = @{@"views": viewJSON(nav.toolbar, 0), @"layers": layerJSON(nav.toolbar.layer, 0)};
        win.rootViewController = root;
        pump(0.2);
        // popover
        UIViewController *pop = [UIViewController new];
        pop.modalPresentationStyle = UIModalPresentationPopover;
        pop.preferredContentSize = CGSizeMake(240, 160);
        pop.popoverPresentationController.sourceView = root.view;
        pop.popoverPresentationController.sourceRect = CGRectMake(400, 300, 10, 10);
        [root presentViewController:pop animated:NO completion:nil];
        pump(0.8);
        UIView *popRoot = pop.view;
        while (popRoot.superview) popRoot = popRoot.superview;
        NSMutableArray *windows = [NSMutableArray array];
        for (UIWindow *w in ((UIWindowScene *)scene).windows) [windows addObject:@{@"class": NSStringFromClass([w class]), @"views": viewJSON(w, 0), @"layers": layerJSON(w.layer, 0)}];
        per[@"popover"] = @{@"views": viewJSON(popRoot, 0), @"layers": layerJSON(popRoot.layer, 0), @"windows": windows,
                            @"hostWindowClass": popRoot.window ? NSStringFromClass([popRoot.window class]) : @"(none)",
                            @"presentationController": NSStringFromClass([pop.presentationController class]),
                            @"popoverBackgroundViewClass": pop.popoverPresentationController.popoverBackgroundViewClass ? NSStringFromClass(pop.popoverPresentationController.popoverBackgroundViewClass) : @"(default)"};
        [pop dismissViewControllerAnimated:NO completion:nil];
        pump(0.3);
        // search bar
        UISearchBar *sb = [[UISearchBar alloc] initWithFrame:CGRectMake(40, 40, 400, 44)];
        [root.view addSubview:sb]; pump(0.2);
        per[@"searchBar"] = @{@"views": viewJSON(sb, 0), @"layers": layerJSON(sb.layer, 0)};
        [sb removeFromSuperview];
        // glass buttons: UIButton with glass configuration (iOS 26)
        Class cfg = NSClassFromString(@"UIButtonConfiguration");
        if ([cfg respondsToSelector:NSSelectorFromString(@"glassButtonConfiguration")]) {
            UIButtonConfiguration *c = [cfg performSelector:NSSelectorFromString(@"glassButtonConfiguration")];
            c.title = @"Glass";
            UIButton *b = [UIButton buttonWithConfiguration:c primaryAction:nil];
            b.frame = CGRectMake(40, 40, 120, 44);
            [root.view addSubview:b]; pump(0.3);
            per[@"button.glass"] = @{@"views": viewJSON(b, 0), @"layers": layerJSON(b.layer, 0)};
            [b removeFromSuperview];
        }
        result[[styleNum integerValue] == UIUserInterfaceStyleDark ? @"dark" : @"light"] = per;
    }
    NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys error:nil];
    [json writeToFile:out atomically:YES];
    printf("wrote %s\n", out.UTF8String);
    exit(0);
}
@end

int main(int argc, char *argv[]) {
    @autoreleasepool { return UIApplicationMain(argc, argv, nil, @"ProbeDelegate"); }
}
