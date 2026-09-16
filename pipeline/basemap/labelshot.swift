// Live MKMapView in a borderless window, screenshotted at the display's backing
// scale (2x on Retina) so label glyphs can be measured at sub-point precision.
// MKMapSnapshotter only ever returns 1x on macOS (checked 2026-09-16), hence this.
// The window is ours (not the Maps App); screencapture -l grabs only that window.
//
//   swiftc -O pipeline/basemap/labelshot.swift -o /tmp/labelshot
//   /tmp/labelshot <lat> <lng> <dlat> <dlng> <w> <h> <out.png> <out.json> [dark] [-AppleLanguages '(en)']
//
// out.json records the render args, time, window scale and the pixel position
// of the region centre/corners (MKMapView.convert) for coordinate registration.
import AppKit
import MapKit

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
// screencapture returns nothing while the display is asleep; -u asserts user activity
let caf = Process(); caf.executableURL = URL(fileURLWithPath: "/usr/bin/caffeinate"); caf.arguments = ["-u", "-t", "25"]; try! caf.run()
let iso = ISO8601DateFormatter()
let t0 = iso.string(from: Date())
let wait = Double(ProcessInfo.processInfo.environment["LABELSHOT_WAIT"] ?? "14") ?? 14
DispatchQueue.main.asyncAfter(deadline: .now() + wait) {
  let p = Process(); p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
  p.arguments = ["-x", "-o", "-l", String(win.windowNumber), outPNG]; try! p.run(); p.waitUntilExit()
  if !FileManager.default.fileExists(atPath: outPNG) {
    FileHandle.standardError.write("screencapture produced no file (display asleep?)\n".data(using: .utf8)!)
    exit(1)
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
