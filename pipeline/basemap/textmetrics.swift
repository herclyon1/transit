// CoreText reference metrics for label fitting: for each requested string and
// system-font weight (SF, the same font the renderer uses), the ink bounding box
// and ink area at 100 pt with zero tracking. labels.py divides a measured ink
// height by these to get the point size, then solves tracking from the width
// and picks the weight whose ink density matches.
//
//   swiftc -O pipeline/basemap/textmetrics.swift -o /tmp/textmetrics
//   /tmp/textmetrics '<json list of {"text":..., "italic":bool}>'   -> json on stdout
import AppKit
import CoreText
import Foundation

let weights: [(String, NSFont.Weight)] = [("regular", .regular), ("medium", .medium), ("semibold", .semibold), ("bold", .bold), ("heavy", .heavy), ("black", .black)]
let reqs = try! JSONSerialization.jsonObject(with: CommandLine.arguments[1].data(using: .utf8)!) as! [[String: Any]]
let size: CGFloat = 100

func font(_ w: NSFont.Weight, italic: Bool) -> NSFont {
  let f = NSFont.systemFont(ofSize: size, weight: w)
  if !italic { return f }
  // keep the weight: NSFontManager converts .SFNS-Semibold -> .SFNS-SemiboldItalic
  return NSFontManager.shared.convert(f, toHaveTrait: .italicFontMask)
}

func measure(_ text: String, _ f: NSFont) -> [String: Any] {
  let attr = NSAttributedString(string: text, attributes: [.font: f, .kern: 0, .foregroundColor: NSColor.white])
  let line = CTLineCreateWithAttributedString(attr)
  let W = 4096, H = 256
  let cs = CGColorSpaceCreateDeviceRGB()
  let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: W * 4, space: cs, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
  ctx.setShouldAntialias(true); ctx.setAllowsFontSmoothing(false); ctx.setShouldSmoothFonts(false)
  ctx.textPosition = CGPoint(x: 100, y: 100)
  CTLineDraw(line, ctx)
  let ink = CTLineGetImageBounds(line, ctx)   // ink bbox in context coords (origin bottom-left)
  let px = ctx.data!.assumingMemoryBound(to: UInt8.self)
  var area = 0.0
  for i in 0..<(W * H) { area += Double(px[i * 4 + 3]) / 255.0 }  // alpha coverage
  var asc: CGFloat = 0, desc: CGFloat = 0, lead: CGFloat = 0
  let adv = CTLineGetTypographicBounds(line, &asc, &desc, &lead)
  return [
    "ink_w": ink.width, "ink_h": ink.height,
    "ink_top_above_baseline": ink.maxY - 100, "ink_below_baseline": 100 - ink.minY,
    "ink_area": area, "advance": adv, "ascent": asc, "descent": desc,
    "glyph_count": CTLineGetGlyphCount(line),
    "font": f.fontName, "cap_height": f.capHeight, "x_height": f.xHeight,
  ]
}

var out: [[String: Any]] = []
for r in reqs {
  let text = r["text"] as! String, italic = (r["italic"] as? Bool) ?? false
  var byWeight: [String: Any] = [:]
  for (name, w) in weights {
    var m = measure(text, font(w, italic: italic))
    // stem widths of the two full-height straight letters, for weight fitting by stroke thickness
    m["stem_I_w"] = measure("I", font(w, italic: italic))["ink_w"]
    m["stem_l_w"] = measure("l", font(w, italic: italic))["ink_w"]
    byWeight[name] = m
  }
  out.append(["text": text, "italic": italic, "size_pt": size, "weights": byWeight])
}
print(String(data: try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys]), encoding: .utf8)!)
