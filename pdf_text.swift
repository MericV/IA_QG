// Extrait le texte d'un PDF avec PDFKit (macOS).
// Usage : swift pdf_text.swift FICHIER.pdf [--pages 1-3]
import Foundation
import PDFKit

func echec(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(1)
}

var args = Array(CommandLine.arguments.dropFirst())
var debut = 1, fin = Int.max
if let i = args.firstIndex(of: "--pages") {
    guard i + 1 < args.count else { echec("Erreur : --pages attend une plage, par ex. 1-3") }
    let p = args[i + 1].split(separator: "-").compactMap { Int($0) }
    guard p.count == 1 || p.count == 2, p[0] >= 1 else { echec("Erreur : plage de pages invalide « \(args[i + 1]) » (ex. 2 ou 1-3)") }
    debut = p[0]; fin = p.last!
    args.removeSubrange(i...i + 1)
}
guard args.count == 1 else { echec("Usage : swift pdf_text.swift FICHIER.pdf [--pages 1-3]") }
guard let doc = PDFDocument(url: URL(fileURLWithPath: args[0])) else {
    echec("Erreur : impossible d'ouvrir le PDF « \(args[0]) » (fichier absent ou illisible)")
}
let derniere = min(fin, doc.pageCount)
guard debut <= derniere else { echec("Erreur : le document n'a que \(doc.pageCount) page(s)") }
for n in debut...derniere {
    print("--- page \(n) ---")
    print(doc.page(at: n - 1)?.string ?? "")
}
