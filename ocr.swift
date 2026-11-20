// Lit le texte d'une image avec Vision (macOS), sans service extérieur.
// Usage : swift ocr.swift IMAGE.(png|jpg|heic…)
import Foundation
import Vision

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write("Usage : swift ocr.swift IMAGE\n".data(using: .utf8)!)
    exit(1)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["fr-FR", "en-US"]
request.usesLanguageCorrection = true
do {
    try VNImageRequestHandler(url: url).perform([request])
} catch {
    FileHandle.standardError.write("Erreur : image illisible (\(error.localizedDescription))\n".data(using: .utf8)!)
    exit(1)
}
for line in request.results ?? [] {
    if let text = line.topCandidates(1).first?.string { print(text) }
}
