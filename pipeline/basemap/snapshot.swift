// Offscreen MKMapSnapshotter render (no window): snapshot.swift <lat> <lng> <dlat> <dlng> <w> <h> <scale> <out.png> [dark]
// Used only to verify decoded numbers against Apple's own renderer (standard map, realistic elevation).
import Foundation
import MapKit
import AppKit

let a = CommandLine.arguments
let lat = Double(a[1])!, lng = Double(a[2])!, dlat = Double(a[3])!, dlng = Double(a[4])!
let w = Double(a[5])!, h = Double(a[6])!, scale = Double(a[7])!
let out = a[8]
let dark = a.count > 9 && a[9] == "dark"

let opts = MKMapSnapshotter.Options()
opts.region = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: lat, longitude: lng), span: MKCoordinateSpan(latitudeDelta: dlat, longitudeDelta: dlng))
opts.size = CGSize(width: w, height: h)
let cfg = MKStandardMapConfiguration(elevationStyle: .realistic)
opts.preferredConfiguration = cfg
opts.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
let snap = MKMapSnapshotter(options: opts)
var done = false
snap.start(with: .main) { s, err in
    if let s = s {
        let img = s.image
        var rect = CGRect(origin: .zero, size: CGSize(width: w * scale, height: h * scale))
        let bmp = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(w * scale), pixelsHigh: Int(h * scale), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bmp)
        img.draw(in: rect)
        NSGraphicsContext.restoreGraphicsState()
        try? bmp.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
        print("wrote", out, rect.size)
    } else {
        print("error", err?.localizedDescription ?? "?")
    }
    done = true
}
let deadline = Date().addingTimeInterval(60)
while !done && Date() < deadline { RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.1)) }
if !done { print("timeout") }
