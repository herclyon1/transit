// Render an Apple Maps snapshot (native VectorKit style, MKMapSnapshotter) and
// sample pixel colours at given coordinates. The renderer is used as a
// measuring instrument only; its output is never published.
//
// Usage:
//   swiftc -O pipeline/basemap/sample.swift -o /tmp/sample
//   /tmp/sample <lat> <lng> <dlat> <dlng> <w> <h> <out.png> <points.json> <out.json> [dark] [retina]
//
// points.json: [{"id": "...", "lat": 30.0, "lng": 140.0, ...}, ...] (extra keys are copied through)
// out.json:    {"render": {...}, "points": [{..., "px": 12.3, "py": 45.6, "rgb": [r,g,b]}]}
// px/py come from MKMapSnapshotter.point(for:), i.e. the renderer's own projection,
// not a hand-rolled Mercator. The 4 corners + centre of the requested region are
// added as "grid" points so a caller can solve the exact pixel<->coordinate mapping.
import MapKit
import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count >= 10 else {
  FileHandle.standardError.write("usage: sample lat lng dlat dlng w h out.png points.json out.json [dark] [retina]\n".data(using: .utf8)!)
  exit(2)
}
let lat = Double(args[1])!, lng = Double(args[2])!, dlat = Double(args[3])!, dlng = Double(args[4])!
let w = Double(args[5])!, h = Double(args[6])!, outPNG = args[7], ptsPath = args[8], outJSON = args[9]
let flags = Set(args.dropFirst(10))
let dark = flags.contains("dark"), retina = flags.contains("retina")

// A real NSApplication makes the snapshotter pick up the main display's backing
// scale (2x on Retina) instead of 1x; without it the PNG is always 1x.
if retina { _ = NSApplication.shared }

let ptsData = try! Data(contentsOf: URL(fileURLWithPath: ptsPath))
var pts = try! JSONSerialization.jsonObject(with: ptsData) as! [[String: Any]]

let o = MKMapSnapshotter.Options()
o.region = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: lat, longitude: lng),
                              span: MKCoordinateSpan(latitudeDelta: dlat, longitudeDelta: dlng))
o.size = CGSize(width: w, height: h)
o.preferredConfiguration = MKStandardMapConfiguration(elevationStyle: .realistic, emphasisStyle: .default)
o.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)

let iso = ISO8601DateFormatter()
let t0 = iso.string(from: Date())
let snap = MKMapSnapshotter(options: o)
let sem = DispatchSemaphore(value: 0)
var failed = false
snap.start(with: DispatchQueue.global()) { s, e in
  defer { sem.signal() }
  if let e = e { FileHandle.standardError.write("error: \(e)\n".data(using: .utf8)!); failed = true; return }
  let s = s!
  let img = s.image
  let tiff = img.tiffRepresentation!, rep = NSBitmapImageRep(data: tiff)!
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: outPNG))
  let pw = rep.pixelsWide, ph = rep.pixelsHigh
  let scale = Double(pw) / img.size.width   // pixels per point

  // grid points: region corners + centre, in the renderer's own projection
  let grid: [(String, Double, Double)] = [
    ("grid:c", lat, lng),
    ("grid:nw", lat + dlat/2, lng - dlng/2), ("grid:ne", lat + dlat/2, lng + dlng/2),
    ("grid:sw", lat - dlat/2, lng - dlng/2), ("grid:se", lat - dlat/2, lng + dlng/2),
  ]
  for g in grid { pts.append(["id": g.0, "lat": g.1, "lng": g.2, "grid": true]) }

  var outPts: [[String: Any]] = []
  for var p in pts {
    let c = CLLocationCoordinate2D(latitude: p["lat"] as! Double, longitude: p["lng"] as! Double)
    // macOS MKMapSnapshot.point(for:) is in AppKit flipped space (origin bottom-left):
    // verified 2026-09-16 — Tokyo (35.68 N) came back below the 30 N centre row.
    let pt = s.point(for: c)
    let px = pt.x * scale, py = (img.size.height - pt.y) * scale
    p["px"] = px; p["py"] = py
    let xi = Int(px.rounded(.down)), yi = Int(py.rounded(.down))
    if xi >= 0 && yi >= 0 && xi < pw && yi < ph, let col = rep.colorAt(x: xi, y: yi)?.usingColorSpace(.sRGB) {
      p["rgb"] = [Int((col.redComponent*255).rounded()), Int((col.greenComponent*255).rounded()), Int((col.blueComponent*255).rounded())]
    } else {
      p["rgb"] = NSNull()
    }
    outPts.append(p)
  }
  let render: [String: Any] = [
    "tool": "MKMapSnapshotter (macOS MapKit, VectorKit native style)",
    "config": "MKStandardMapConfiguration(elevationStyle: .realistic, emphasisStyle: .default)",
    "appearance": dark ? "darkAqua" : "aqua",
    "center": [lat, lng], "span": [dlat, dlng], "size_pt": [w, h],
    "size_px": [pw, ph], "scale": scale,
    "image": outPNG, "rendered_at_utc": t0,
    "macos": ProcessInfo.processInfo.operatingSystemVersionString,
  ]
  let doc: [String: Any] = ["render": render, "points": outPts]
  let data = try! JSONSerialization.data(withJSONObject: doc, options: [.prettyPrinted, .sortedKeys])
  try! data.write(to: URL(fileURLWithPath: outJSON))
  print("ok \(pw)x\(ph) scale=\(scale) points=\(outPts.count)")
}
_ = sem.wait(timeout: .now() + 120)
exit(failed ? 1 : 0)
