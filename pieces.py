"""Pièces jointes du client : extraire le texte d'un document pour en faire une source du Bureau.

Rien à installer : outils du Mac (textutil pour Word, RTF, HTML ; PDFKit pour les PDF ; Vision pour le texte
des images) et bibliothèque standard de Python (PowerPoint, Excel, texte).
Usage : python3 pieces.py FICHIER   (affiche le texte extrait)
"""
import pathlib, re, subprocess, sys, zipfile, html

HERE = pathlib.Path(__file__).resolve().parent
TEXT = {".txt", ".md", ".csv", ".json"}
TEXTUTIL = {".docx", ".doc", ".rtf", ".odt", ".html", ".htm"}
IMAGES = {".png", ".jpg", ".jpeg", ".heic", ".tiff", ".gif", ".webp"}
OFFICE = {".pptx", ".xlsx"}
KINDS = TEXT | TEXTUTIL | IMAGES | OFFICE | {".pdf"}
MAX_BYTES = 15 * 1024 * 1024


class PieceErreur(Exception):
    pass


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise PieceErreur(r.stderr.strip()[:300] or "lecture impossible")
    return r.stdout


def office(path):
    """PowerPoint : le texte de chaque diapo ; Excel : les textes des cellules (chaînes partagées)."""
    with zipfile.ZipFile(path) as z:
        if path.suffix == ".pptx":
            slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
            parts = [f"--- diapo {i} ---\n" + " ".join(re.findall(r"<a:t>([^<]*)</a:t>", z.read(n).decode())) for i, n in enumerate(slides, 1)]
        else:
            parts = re.findall(r"<t[^>]*>([^<]*)</t>", z.read("xl/sharedStrings.xml").decode()) if "xl/sharedStrings.xml" in z.namelist() else []
    return html.unescape("\n".join(parts))


def extract(path):
    path = pathlib.Path(path)
    ext = path.suffix.lower()
    if ext not in KINDS:
        raise PieceErreur(f"format non pris en charge ({ext or 'sans extension'}) : PDF, Word, RTF, PowerPoint, Excel, image ou texte")
    if ext in TEXT:
        return path.read_text(encoding="utf-8", errors="replace")
    if ext in TEXTUTIL:
        return run(["textutil", "-convert", "txt", "-stdout", str(path)])
    if ext == ".pdf":
        return run(["swift", str(HERE / "pdf_text.swift"), str(path)])
    if ext in IMAGES:
        return run(["swift", str(HERE / "ocr.swift"), str(path)])
    try:
        return office(path)
    except (zipfile.BadZipFile, KeyError) as e:
        raise PieceErreur(f"fichier Office illisible : {e}") from None


if __name__ == "__main__":
    print(extract(sys.argv[1]))
