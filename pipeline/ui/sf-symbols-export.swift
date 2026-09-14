// 从 Mac 系统字体导出 SF Symbols 为 4x PNG 蒙版，供 ui/hig.css 用 mask-image 上色。
// 用法：swiftc -O pipeline/ui/sf-symbols-export.swift -o /tmp/sfx && (cd ui/sf && /tmp/sfx)
// 方法沿用 Claude/maa-automation/scripts/mac/sf-symbols-export.swift（2026-09-14）。
// SF Symbols 的许可写的是 Apple 平台；本站公开托管在 GitHub Pages，用户 2026-09-15 拍板照用。
import AppKit
let names = ["magnifyingglass","xmark","chevron.right","chevron.left","chevron.up","chevron.down","location.fill","location",
             "map","map.fill","house.fill","list.bullet","globe.asia.australia.fill","tram.fill","graduationcap.fill",
             "questionmark.circle","info.circle","slider.horizontal.3","yensign","banknote","clock","bolt.fill","cart","building.2",
             "plus","minus","arrow.counterclockwise","checkmark","xmark.circle.fill","square.stack.3d.up","mappin","mappin.and.ellipse",
             "figure.walk","person.fill","doc.text","link","ellipsis.circle","sidebar.leading","square.grid.2x2","star.fill","flag.fill",
             "chart.bar","circle.fill","circle","gauge.with.dots.needle.67percent","arrow.left","arrow.right","eye","eye.slash"]
for n in names {
    guard let img = NSImage(systemSymbolName: n, accessibilityDescription: nil) else { print("MISSING", n); continue }
    let cfg = NSImage.SymbolConfiguration(pointSize: 22, weight: .regular, scale: .medium)
    guard let sym = img.withSymbolConfiguration(cfg) else { continue }
    let scale: CGFloat = 4
    let w = Int(ceil(sym.size.width * scale)), h = Int(ceil(sym.size.height * scale))
    guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { continue }
    rep.size = sym.size
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSColor.black.set()
    sym.draw(in: NSRect(origin: .zero, size: sym.size), from: .zero, operation: .sourceOver, fraction: 1.0)
    NSGraphicsContext.restoreGraphicsState()
    let png = rep.representation(using: .png, properties: [:])!
    try! png.write(to: URL(fileURLWithPath: "\(n).png"))
    print("OK", n, Int(sym.size.width), Int(sym.size.height))
}
