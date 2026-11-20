"""Test des pièces jointes et de l'export Word : python3 test_documents.py

Tout se passe dans un dossier temporaire : lecture d'un Word, d'un PowerPoint et d'un texte, refus d'un format inconnu,
pièce jointe enregistrée et annoncée au PDG, export Word avec de vraies notes de bas de page.
"""
import io, os, pathlib, re, shutil, subprocess, sys, tempfile, zipfile

TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["BUREAU_DATA"] = str(TMP / "bureau")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pieces, qg_log, word  # noqa: E402

try:
    # 1. Lecture : Word (fabriqué par textutil), PowerPoint (fabriqué à la main), texte ; format inconnu refusé
    html = TMP / "a.html"
    html.write_text('<meta charset="utf-8"><h1>Rapport</h1><p>La répétition espacée aide à retenir.</p>', encoding="utf-8")
    subprocess.run(["textutil", "-convert", "docx", str(html), "-output", str(TMP / "a.docx")], check=True)
    assert "répétition espacée" in pieces.extract(TMP / "a.docx")
    with zipfile.ZipFile(TMP / "b.pptx", "w") as z:
        z.writestr("ppt/slides/slide2.xml", "<p:sld><a:t>Deuxième diapo</a:t></p:sld>")
        z.writestr("ppt/slides/slide1.xml", "<p:sld><a:t>Première</a:t><a:t>diapo &amp; titre</a:t></p:sld>")
    assert pieces.extract(TMP / "b.pptx") == "--- diapo 1 ---\nPremière diapo & titre\n--- diapo 2 ---\nDeuxième diapo"
    (TMP / "c.exe").write_bytes(b"MZ")
    try:
        pieces.extract(TMP / "c.exe")
        raise AssertionError("format inconnu accepté")
    except pieces.PieceErreur:
        pass

    # 2. Pièce jointe : texte rangé dans pieces/, message court au PDG, liste dans le journal
    qg_log.QUIET = True
    qg_log.main(["init", "Essai", "essai"])
    qg_log.add_piece("Mon rapport.docx", (TMP / "a.docx").read_bytes())
    live = qg_log.read(qg_log.LIVE, {})
    assert live["pieces"][0]["name"] == "Mon rapport.docx" and live["pieces"][0]["words"] >= 5
    assert "répétition" in (qg_log.ROOT / "pieces" / live["pieces"][0]["file"]).read_text(encoding="utf-8")
    msg = [m["text"] for m in qg_log.unread()][-1]
    assert msg.startswith("📎 Pièce jointe « Mon rapport.docx »") and len(msg) < 400
    try:
        qg_log.add_piece("virus.exe", b"MZ")
        raise AssertionError("pièce jointe .exe acceptée")
    except qg_log.Erreur:
        pass

    # 3. Word : chaque [n] connu devient une note (complète puis « Voir note X »), [HYP] retiré, [9] inconnu gardé
    md = "# Titre\n\nUn fait [1]. Une hypothèse [HYP]. Deux sources [1, 2]. Inconnue [9].\n\n## Sources\n\n1. Dunlosky J. (2013). *Étude*.\n2. Ebbinghaus H. (1885).\n"
    z = zipfile.ZipFile(io.BytesIO(word.docx(md)))
    notes = re.findall(r'<w:t xml:space="preserve"> ([^<]*)</w:t>', z.read("word/footnotes.xml").decode())
    assert notes == ["Dunlosky J. (2013). Étude.", "Voir note 1.", "Ebbinghaus H. (1885)."], notes
    doc = z.read("word/document.xml").decode()
    assert "[HYP]" not in doc and "[9]" in doc and doc.count("<w:footnoteReference") == 3 and "Un fait</w:t>" in doc  # note collée au mot
    print("test_documents : OK")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
