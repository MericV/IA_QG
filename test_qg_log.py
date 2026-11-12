"""Test du circuit complet du QG : python3 test_qg_log.py

Rejoue des missions dans un dossier temporaire (rien n'est écrit dans projets/) : journal, validation
des saisies, consignes et questions du client, livrables (dont en parallèle et non texte), export,
archives et historique, et la sécurité du serveur (jeton, hôte, origine, liste blanche, iframe).
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
TMP = pathlib.Path(tempfile.mkdtemp())
WORK = TMP / "mon-projet"
WORK.mkdir()
ENV = {**os.environ, "BUREAU_DATA": str(TMP / "bureau")}
ROOT = TMP / "bureau" / "projets" / "test"


def qg(*args, ok=True):
    r = subprocess.run([sys.executable, str(HERE / "qg_log.py"), *args], cwd=WORK, env=ENV, capture_output=True, text=True)
    assert (r.returncode == 0) == ok, f"{args} → code {r.returncode}\n{r.stdout}{r.stderr}"
    assert "Traceback" not in r.stderr, f"{args} : trace Python brute\n{r.stderr}"
    return r.stdout + r.stderr


def http(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def start_server():
    srv = subprocess.Popen([sys.executable, str(HERE / "qg_server.py"), "8890"], cwd=WORK, env=ENV, stdout=subprocess.PIPE, text=True)
    url = re.search(r"http://127\.0\.0\.1:\d+/", srv.stdout.readline()).group(0)
    return srv, url + "d/test/"


def stop(srv):
    srv.terminate()
    srv.wait(timeout=5)


try:
    # Commandes avant toute mission : erreur claire, pas de trace ni d'écriture orpheline
    assert "aucune mission" in qg("stages", "A|B", ok=False)
    assert "aucune mission" in qg("ask", "Q ?", "A|B", ok=False)
    qg("inbox")

    # Mission et validation des saisies
    qg("init", "Mission A", "test")
    assert (ROOT / "missions" / "index.html").exists(), "l'historique existe dès le départ"
    qg("stages", "Cadrage|Sources|Rédaction")
    qg("pdg", "bib", "cherche des sources", "-", "sources")
    assert "rôle inconnu" in qg("bibl", "pdg", "faute de frappe", ok=False)
    assert "étape inconnue" in qg("aud", "-", "audit", "ok", "inexistante", ok=False)
    assert "type inconnu" in qg("aud", "-", "audit", "peut-etre", ok=False)
    assert "introuvable" in qg("dispatch", "9", "bib", "rien", ok=False)
    assert "déjà pris" in qg("hire", "bib", "Doublon", "bib", "x", ok=False)
    for bad in ["-", "a,b", "", "Bib2", "__proto__", "x" * 17]:
        assert "invalide" in qg("hire", bad, "Renfort", "bib", "x", ok=False), bad
    qg("hire", "bib2", "Bibliothécaire 2", "bib", "renfort")
    # Recrutement par le PDG : rôle du vivier ou rôle inventé, puis fin de mission du rôle
    qg("recruit", "recruteur", "Recruteur militaire", "Relire avec les yeux d'un jury", "Le livrable sera jugé par un jury")
    assert "déjà partie" in qg("recruit", "recruteur", "Doublon", "x", "y", ok=False)
    assert "déjà partie" in qg("recruit", "aud", "Auditeur bis", "x", "y", ok=False), "les permanents ne se recrutent pas"
    qg("recruteur", "pdg", "Deux objections du point de vue du jury")
    assert "pas dans l'équipe" in qg("release", "inconnu", "x", ok=False)
    qg("release", "recruteur", "Relecture faite")
    # Brief complet visible et fin de contrat (PDG)
    (WORK / "brief.md").write_text("Tu es l'Analyste. Compare A et B.")
    qg("recruit", "ana", "Analyste", "Comparer", "Besoin d'un tableau", f"@{WORK / 'brief.md'}")
    qg("dismiss", "ana", "Plus utile")
    assert "déjà terminé" in qg("dismiss", "ana", "encore", ok=False)
    m = [x for x in json.loads((ROOT / "qg-live.json").read_text())["team"] if x["id"] == "ana"][0]
    assert m["brief"].startswith("Tu es l'Analyste") and m["status"] == "parti" and m["end_by"] == "pdg"
    team = json.loads((ROOT / "qg-live.json").read_text())["team"]
    assert [m["id"] for m in team][:2] == ["bib2", "recruteur"] and team[1]["status"] == "terminé" and team[1]["bilan"] == "Relecture faite"
    qg("bib2", "pdg", "le renfort travaille")
    qg("aud", "-", "audit rejeté", "ko", "Sources")
    qg("aud", "-", "audit validé", "ok", "sources")
    qg("pdg", "bib", "Cherche la balise <!--<script> dans la doc HTML")
    live = json.loads((ROOT / "qg-live.json").read_text())
    assert all("ts" in e and "t" in e for e in live["events"]), "chaque échange doit être horodaté"

    # Livrables : versions, différences, fichier non texte, livraisons en parallèle
    doc = WORK / "section.md"
    doc.write_text("Ligne 1\nLigne 2\n")
    qg("livrable", str(doc), "ecr", "premier jet")
    doc.write_text("Ligne 1\nLigne 2 corrigée\n")
    assert "Version 2" in qg("livrable", str(doc), "ecr", "après audit")
    diff = (ROOT / "livrables" / "02-section.diff").read_text()
    assert "+Ligne 2 corrigée" in diff and "-Ligne 2" in diff
    (WORK / "dossier.docx").write_bytes(b"PK\x03\x04\xff\xfe binaire")
    assert "Version 1" in qg("livrable", str(WORK / "dossier.docx"))
    procs = []
    for i in range(12):
        (WORK / f"sec{i}.md").write_text(f"Section {i}\n")
        procs.append(subprocess.Popen([sys.executable, str(HERE / "qg_log.py"), "livrable", f"sec{i}.md"], cwd=WORK, env=ENV,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    assert all(p.wait() == 0 for p in procs), [p.stderr.read() for p in procs]
    index = json.loads((ROOT / "livrables" / "index.json").read_text())
    assert len(index) == 15 and sorted(v["n"] for v in index) == list(range(1, 16)), "aucune version perdue en parallèle"

    # Serveur : sécurité, message du client, question
    srv, url = start_server()
    try:
        base = url.split("d/test/")[0]
        status, page, headers = http(url)
        assert status == 200 and "__QG_TOKEN__" not in page
        assert headers["X-Frame-Options"] == "SAMEORIGIN" and "frame-ancestors 'self'" in headers["Content-Security-Policy"], "iframe : l'app seule"
        token = re.search(r"const TOKEN = '([^']+)'", page).group(1)
        port = url.split(":")[2].split("/")[0]
        # L'app à la racine, la liste des discussions et les fournisseurs (jamais de clé dans la réponse)
        status, app, _ = http(base)
        assert status == 200 and "Nouvelle discussion" in app and token in app
        assert any(d["id"] == "test" for d in json.loads(http(base + "api/discussions")[1]))
        provs = json.loads(http(base + "api/providers")[1])
        assert {"claude-code", "anthropic", "openai", "hermes"} <= {p["id"] for p in provs} and all("key" not in p for p in provs)
        assert http(base + "api/accounts", {"provider": "anthropic", "key": "sk-test-1234567890"}, {"Content-Type": "application/json"})[0] == 403, "comptes : jeton obligatoire"
        assert http(base + "api/accounts", {"provider": "inconnu", "key": "sk-test-1234567890"}, {"X-QG-Token": token})[0] == 400
        assert http(base + "d/..%2F..%2Fetc/", )[0] == 404 and http(base + "d/inexistante/")[0] == 404
        assert http(url + "model", {"provider": "anthropic", "model": "claude-opus-5-5"}, {"X-QG-Token": token})[0] == 204
        assert json.loads((ROOT / "qg-live.json").read_text())["model"]["model"] == "claude-opus-5-5"
        assert http(url + "model", {"provider": "pirate", "model": "x"}, {"X-QG-Token": token})[0] == 400
        assert http(url + "dismiss", {"id": "bib2"}, {"Content-Type": "application/json"})[0] == 403
        assert http(url + "dismiss", {"id": "bib2", "reason": "plus utile"}, {"X-QG-Token": token})[0] == 204
        assert "FIN AU CONTRAT" in qg("inbox"), "le PDG est prévenu"
        assert http(url + "dismiss", {"id": "bib2"}, {"X-QG-Token": token})[0] == 409
        # Nouvelle discussion depuis l'app : son premier message arrive au PDG
        status, body, _ = http(base + "api/discussions", {"text": "Une synthèse de deux pages sur le cloud souverain"}, {"X-QG-Token": token})
        new_id = json.loads(body)["id"]
        assert status == 201 and (TMP / "bureau" / "projets" / new_id / "consignes.json").exists()
        env_new = {**ENV, "BUREAU_PROJET": new_id}
        out = subprocess.run([sys.executable, str(HERE / "qg_log.py"), "inbox"], cwd=WORK, env=env_new, capture_output=True, text=True).stdout
        assert "cloud souverain" in out, "BUREAU_PROJET cible la discussion de l'app"
        shutil.rmtree(TMP / "bureau" / "projets" / new_id)
        assert http(url + "say", {"text": "sans jeton"}, {"Content-Type": "application/json"})[0] == 403
        assert http(url + "say", {"text": "mauvais hôte"}, {"X-QG-Token": token, "Host": f"evil.example:{port}"})[0] == 403
        assert http(url + "say", {"text": "autre site"}, {"X-QG-Token": token, "Origin": "https://evil.example"})[0] == 403
        assert http(url, method="HEAD", headers={"Host": "evil.example"})[0] in (403, 405)
        for hidden in [".port", "%2Eport", ".token", "%2Etoken", "inbox.jsonl", "inbox%2Ejsonl", "%2Everrou",
                       "qg-live.json", "consignes.json", "livrables/index.json", "livrables/%2E%2E/qg-live.json"]:
            assert http(url + hidden)[0] == 404, f"{hidden} ne doit pas être servi"
        for hidden in [".token", "%2Etoken", ".port", "intro/..%2F.token", "intro/%2E%2E/qg_log.py", "qg_log.py", "projets.json"]:
            assert http(base + hidden)[0] == 404, f"racine : {hidden} ne doit pas être servi"
        assert http(url + "livrables/01-section.md")[0] == 200 and http(url + "missions/")[0] == 200
        assert http(url + "say", {"text": "Ajoute la source X"}, {"X-QG-Token": token})[0] == 204
        out = qg("inbox")
        assert "MESSAGE DU CLIENT n° 1" in out and "Ajoute la source X" in out
        qg("ack", "1", "Bien reçu")
        assert "pas été transmise" in qg("applied", "1", "bib", "x", ok=False)
        qg("dispatch", "1", "bib", "ajoute la source X")
        qg("applied", "1", "bib", "source ajoutée")
        assert json.loads((ROOT / "consignes.json").read_text())[0]["status"] == "appliqué"
        qg("ask", "Format du rendu ?", "PDF|Word")
        assert http(url + "answer", {"id": 1, "choice": "Excel"}, {"X-QG-Token": token})[0] == 409
        assert http(url + "answer", {"id": 1, "choice": "PDF"}, {"X-QG-Token": token})[0] == 204
        assert http(url + "answer", {"id": 1, "choice": "Word"}, {"X-QG-Token": token})[0] == 409, "une seule réponse"
        assert "RÉPONSE DU CLIENT" in qg("inbox")
        # Réponse libre, et question close parce que déjà réglée autrement
        qg("ask", "Ton ton préféré ?", "Sobre|Enthousiaste")
        assert http(url + "answer", {"id": 2, "choice": "Plutôt direct"}, {"X-QG-Token": token})[0] == 409, "hors choix sans « other »"
        assert http(url + "answer", {"id": 2, "choice": "Plutôt direct", "other": True}, {"X-QG-Token": token})[0] == 204
        qg("ask", "Longueur ?", "Courte|Longue")
        assert "déjà une réponse" in qg("close", "2", "x", ok=False)
        qg("close", "3", "Réglé par ton message : 500 caractères.")
        assert http(url + "answer", {"id": 3, "choice": "Courte"}, {"X-QG-Token": token})[0] == 409, "question close"
        qs = json.loads((ROOT / "questions.json").read_text())
        assert qs[1]["answer"] == "Plutôt direct" and qs[2]["closed"]
        ev = json.loads((ROOT / "qg-live.json").read_text())["events"]
        assert any(e.get("msg") == 1 for e in ev) and any(e.get("answer_to") == 2 for e in ev), "liens message ↔ consigne"
        qg("inbox")
        state = json.loads(http(url + "state")[1])
        assert state["questions"][0]["answer"] == "PDF" and len(state["livrables"]) == 15
        assert all("source" not in v for v in state["livrables"]), "le chemin local du livrable ne doit pas être exposé"
    finally:
        stop(srv)
    assert not (TMP / "bureau" / ".port").exists(), ".port doit disparaître à l'arrêt (SIGTERM)"

    # Redémarrage : le jeton du projet ne change pas, une page ouverte reste valable
    srv, url = start_server()
    try:
        assert http(url + "say", {"text": "après redémarrage"}, {"X-QG-Token": token})[0] == 204
    finally:
        stop(srv)
    qg("inbox")

    # Export : le bloc JSON ne peut pas casser la page, et le livrable non texte est signalé
    qg("pdg", "client", "livré", "deliver", "rédaction")
    html = (pathlib.Path(qg("export").split("exportée : ")[1].strip())).read_text()
    block = re.search(r'<script id="session" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert "<" not in block, "aucun « < » brut dans le bloc JSON"
    data = json.loads(block)
    assert data["topic"] == "Mission A" and any("<!--<script>" in e["text"] for e in data["events"])
    assert any(v.get("binary") and "content" not in v for v in data["livrables"])
    assert html.count("<script") == 2, "le script de la page doit rester intact"

    # Deux missions du même jour au même sujet : deux archives distinctes
    qg("init", "Synthese")
    qg("pdg", "bib", "première mission")
    qg("init", "Synthese")
    qg("pdg", "bib", "deuxième mission")
    qg("init", "Autre")
    texts = [" ".join(e["text"] for e in json.loads(f.read_text())["events"]) for f in (ROOT / "missions").glob("*synthese.json")]
    assert len(texts) == 2 and any("première" in t for t in texts) and any("deuxième" in t for t in texts)

    # Historique : « Sources » rejetée une fois avant d'être validée → 0 étape validée du premier coup sur 1
    history = (ROOT / "missions" / "index.html").read_text()
    assert "Mission A" in history and "<td>0/1</td>" in history
    assert json.loads((ROOT / "qg-live.json").read_text())["events"] == [] and not (ROOT / "livrables").exists()

    print("test_qg_log : OK")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
