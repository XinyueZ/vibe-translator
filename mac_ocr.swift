import Cocoa
import Vision

guard CommandLine.arguments.count > 1 else {
    print("Usage: swift mac_ocr.swift <image_path>")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("Failed to load image")
    exit(1)
}

let requestHandler = VNImageRequestHandler(cgImage: cgImage, options: [:])
let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }
    let recognizedText = observations.compactMap { observation in
        return observation.topCandidates(1).first?.string
    }.joined(separator: "\n")
    print(recognizedText)
}
request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US", "de-DE", "fr-FR", "es-ES"]
request.usesLanguageCorrection = true

do {
    try requestHandler.perform([request])
} catch {
    print("Error: \(error)")
}
