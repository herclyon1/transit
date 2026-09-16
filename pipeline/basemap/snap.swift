import MapKit
import AppKit
let args = CommandLine.arguments
let lat = Double(args[1])!, lng = Double(args[2])!, dlat = Double(args[3])!, dlng = Double(args[4])!
let w = Double(args[5])!, h = Double(args[6])!, out = args[7], dark = args.count > 8 && args[8] == "dark"
let o = MKMapSnapshotter.Options()
o.region = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: lat, longitude: lng), span: MKCoordinateSpan(latitudeDelta: dlat, longitudeDelta: dlng))
o.size = CGSize(width: w, height: h)
let cfg = MKStandardMapConfiguration(elevationStyle: .realistic, emphasisStyle: .default)
o.preferredConfiguration = cfg
o.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
let snap = MKMapSnapshotter(options: o)
let sem = DispatchSemaphore(value: 0)
snap.start(with: DispatchQueue.global()) { s, e in
  if let e = e { print("error:", e); sem.signal(); return }
  let img = s!.image
  let tiff = img.tiffRepresentation!, rep = NSBitmapImageRep(data: tiff)!
  try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
  print("ok", img.size)
  sem.signal()
}
_ = sem.wait(timeout: .now() + 60)
