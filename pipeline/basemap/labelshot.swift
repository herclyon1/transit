// Live MKMapView in a borderless window, screenshotted at the display's backing
// scale (2x on Retina) so label glyphs can be measured at sub-point precision.
// MKMapSnapshotter only ever returns 1x on macOS (checked 2026-09-16), hence this.
// The window is ours (not the Maps App); screencapture -l grabs only that window.
//
//   swiftc -O pipeline/basemap/labelshot.swift -o /tmp/labelshot
//   caffeinate -d -u -i /tmp/labelshot <lat> <lng> <dlat> <dlng> <w> <h> <out.png> <out.json> [dark]
//
// Run the whole capture pipeline under `caffeinate -d -u -i`: this Mac's display
// sleeps every few minutes (pmset log 2026-09-16 12:27:59 off / 12:29:01 on /
// 12:36:42 off) and a window on a sleeping display renders nothing. A *locked*
// screen (CGSSessionScreenIsLocked) is a different condition: screencapture gets
// no window content at all — the tool refuses to run instead of producing a blank
// PNG, and the operator has to unlock.
//
// out.json records the render args, time, window scale and the pixel position
// of the region centre/corners (MKMapView.convert) for coordinate registration.
import AppKit
import CoreGraphics
import MapKit

if let session = CGSessionCopyCurrentDictionary() as? [String: Any],
   let locked = session["CGSSessionScreenIsLocked"] as? Int, locked != 0 {
  FileHandle.standardError.write("screen is locked (CGSSessionScreenIsLocked=1): screencapture cannot read window contents; unlock the Mac and retry\n".data(using: .utf8)!)
  exit(3)
}
if CGDisplayIsAsleep(CGMainDisplayID()) != 0 {
  FileHandle.standardError.write("display is asleep: run under `caffeinate -d -u -i` so it stays awake for the capture\n".data(using: .utf8)!)
  exit(4)
}

let args = CommandLine.arguments
guard args.count >= 9 else {
  FileHandle.standardError.write("usage: labelshot lat lng dlat dlng w h out.png out.json [dark]\n".data(using: .utf8)!)
  exit(2)
}
let lat = Double(args[1])!, lng = Double(args[2])!, dlat = Double(args[3])!, dlng = Double(args[4])!
let w = Double(args[5])!, h = Double(args[6])!, outPNG = args[7], outJSON = args[8]
let dark = args.dropFirst(9).contains("dark")

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let win = NSWindow(contentRect: NSRect(x: 40, y: 60, width: w, height: h), styleMask: [.borderless], backing: .buffered, defer: false)
win.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
let map = MKMapView(frame: win.contentView!.bounds)
map.preferredConfiguration = MKStandardMapConfiguration(elevationStyle: .realistic, emphasisStyle: .default)
map.showsCompass = false
map.showsZoomControls = false
map.showsScale = false
map.showsPitchControl = false
map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: lat, longitude: lng),
                                 span: MKCoordinateSpan(latitudeDelta: dlat, longitudeDelta: dlng)), animated: false)
win.contentView!.addSubview(map)
win.orderFrontRegardless()
let iso = ISO8601DateFormatter()
let t0 = iso.string(from: Date())
let wait = Double(ProcessInfo.processInfo.environment["LABELSHOT_WAIT"] ?? "14") ?? 14
DispatchQueue.main.asyncAfter(deadline: .now() + wait) {
  let p = Process(); p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
  p.arguments = ["-x", "-o", "-l", String(win.windowNumber), outPNG]; try! p.run(); p.waitUntilExit()
  if !FileManager.default.fileExists(atPath: outPNG) {
    FileHandle.standardError.write("screencapture produced no file\n".data(using: .utf8)!)
    exit(1)
  }
  // a blank (unrendered) map comes out as one flat colour: refuse it rather than measuring it
  if let img = NSImage(contentsOfFile: outPNG), let rep = img.representations.first as? NSBitmapImageRep {
    var seen = Set<UInt32>()
    for _ in 0..<400 {
      let x = Int.random(in: 0..<rep.pixelsWide), y = Int.random(in: 0..<rep.pixelsHigh)
      if let c = rep.colorAt(x: x, y: y) { seen.insert(UInt32(c.redComponent * 255) << 16 | UInt32(c.greenComponent * 255) << 8 | UInt32(c.blueComponent * 255)) }
    }
    if seen.count < 8 {
      FileHandle.standardError.write("capture is blank (\(seen.count) colours in 400 samples): map did not render — display asleep or locked during the wait\n".data(using: .utf8)!)
      try? FileManager.default.removeItem(atPath: outPNG)
      exit(5)
    }
  }
  let scale = win.backingScaleFactor
  var grid: [[String: Any]] = []
  let corners: [(String, Double, Double)] = [
    ("grid:c", lat, lng),
    ("grid:nw", lat + dlat/2, lng - dlng/2), ("grid:ne", lat + dlat/2, lng + dlng/2),
    ("grid:sw", lat - dlat/2, lng - dlng/2), ("grid:se", lat - dlat/2, lng + dlng/2),
  ]
  for c in corners {
    let pt = map.convert(CLLocationCoordinate2D(latitude: c.1, longitude: c.2), toPointTo: map)
    // MKMapView on macOS is flipped (origin top-left) — checked: NW corner lands above centre
    grid.append(["id": c.0, "lat": c.1, "lng": c.2, "px": pt.x * scale, "py": pt.y * scale, "grid": true])
  }
  let doc: [String: Any] = [
    "render": [
      "tool": "MKMapView live (macOS MapKit, VectorKit native style) + screencapture -l <window>",
      "config": "MKStandardMapConfiguration(elevationStyle: .realistic, emphasisStyle: .default)",
      "appearance": dark ? "darkAqua" : "aqua",
      "center": [lat, lng], "span": [dlat, dlng], "size_pt": [w, h], "scale": scale,
      "camera_altitude_m": map.camera.altitude,
      "image": outPNG, "rendered_at_utc": t0,
      "macos": ProcessInfo.processInfo.operatingSystemVersionString,
    ],
    "points": grid,
  ]
  try! JSONSerialization.data(withJSONObject: doc, options: [.prettyPrinted, .sortedKeys]).write(to: URL(fileURLWithPath: outJSON))
  print("ok scale=\(scale) alt=\(map.camera.altitude)")
  app.terminate(nil)
}
app.run()
