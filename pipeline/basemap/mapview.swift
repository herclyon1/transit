import AppKit
import MapKit
let args = CommandLine.arguments
let lat = Double(args[1])!, lng = Double(args[2])!, dlat = Double(args[3])!, dlng = Double(args[4])!, out = args[5]
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 744), styleMask: [.titled], backing: .buffered, defer: false)
let map = MKMapView(frame: win.contentView!.bounds)
map.preferredConfiguration = MKStandardMapConfiguration(elevationStyle: .realistic)
map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: lat, longitude: lng), span: MKCoordinateSpan(latitudeDelta: dlat, longitudeDelta: dlng)), animated: false)
win.contentView!.addSubview(map)
win.orderFrontRegardless()
DispatchQueue.main.asyncAfter(deadline: .now() + 12) {
  let p = Process(); p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
  p.arguments = ["-x", "-o", "-l", String(win.windowNumber), out]; try! p.run(); p.waitUntilExit()
  print("ok", map.camera.altitude, map.camera.centerCoordinate)
  app.terminate(nil)
}
app.run()
