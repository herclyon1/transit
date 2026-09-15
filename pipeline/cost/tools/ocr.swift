// Offline OCR with Apple Vision (VNRecognizeTextRequest), Simplified Chinese + English.
// usage: ocr <image> [more images…]  → one JSON object per image on stdout:
//   {"file": …, "width": W, "height": H, "lines": [{"text": …, "x": px, "y": px (top), "w": px, "h": px, "conf": 0–1}, …]}
// Build once: swiftc -O -o pipeline/cost/tools/.build/ocr pipeline/cost/tools/ocr.swift  (wechat_ingest.py does it on first use)
import Foundation
import Vision
import AppKit

func recognize(_ path: String) -> [String: Any] {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return ["file": path, "error": "cannot read image"]
    }
    let W = cg.width, H = cg.height
    var lines: [[String: Any]] = []
    let req = VNRecognizeTextRequest { r, _ in
        for o in (r.results as? [VNRecognizedTextObservation]) ?? [] {
            guard let c = o.topCandidates(1).first else { continue }
            let b = o.boundingBox   // normalized, origin bottom-left
            lines.append(["text": c.string, "conf": Double(c.confidence),
                          "x": Double(b.minX) * Double(W), "y": (1 - Double(b.maxY)) * Double(H),
                          "w": Double(b.width) * Double(W), "h": Double(b.height) * Double(H)])
        }
    }
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch { return ["file": path, "error": "\(error)"] }
    lines.sort { ($0["y"] as! Double) < ($1["y"] as! Double) }
    return ["file": path, "width": W, "height": H, "lines": lines]
}

for p in CommandLine.arguments.dropFirst() {
    let obj = recognize(p)
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [])
    FileHandle.standardOutput.write(data); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}
