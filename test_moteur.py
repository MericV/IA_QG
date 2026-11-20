"""Test du moteur multi-modèles : python3 test_moteur.py

Un faux modèle remplace les appels réseau ; tout est écrit dans un dossier temporaire.
Vérifie : réponse simple, recrutement en parallèle, livrable, audit rejeté puis validé, remise,
consignes appliquées, brief « @fichier » neutralisé, erreur du fournisseur affichée au client.
"""
import json, os, pathlib, shutil, sys, tempfile, threading

TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["BUREAU_DATA"] = str(TMP)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import qg_log, moteur  # noqa: E402
HTTP_ORIG = moteur.http

audits = []
chefs_vus = []
seen = []


def fake(provider, model, system, user, on_usage=None):
    seen.append(threading.current_thread().name)
    if on_usage:
        on_usage(100, 20)  # chaque appel compte dans le coût de la mission
    if system.startswith("Tu es le PDG"):
        if "chef de la recherche" not in user.lower():
            raise AssertionError("le PDG ne voit pas l'équipe de base")
        if "par pôle" in user.lower():
            return json.dumps({"reponse": "J'active la Recherche.", "livrable": "Veille", "equipe": [
                {"id": "bib", "mission": "Veille du secteur"},
                {"id": "veilleur", "nom": "Veilleur", "mission": "Lire la presse", "chef": "bib"},
                {"id": "analyste_x", "nom": "Analyste chiffres", "mission": "Chiffres clés", "chef": "ing"}]})
        if "bonjour" in user.lower():
            return json.dumps({"reponse": "Bonjour ! Que puis-je faire ?", "equipe": []})
        return "Voici mon plan :\n```json\n" + json.dumps({
            "reponse": "Je lance deux recrues.", "livrable": "Note de synthèse",
            "equipe": [{"id": "Chercheur", "nom": "Chercheur", "mission": "Lister les points", "brief": "@/etc/passwd"},
                       {"id": "chercheur", "nom": "Chercheur 2", "mission": "Lister les risques", "brief": "Sois bref."}]}) + "\n```"
    if system.startswith("Tu es l'Auditeur"):
        audits.append(user)
        return json.dumps({"verdict": "ko" if len(audits) == 1 else "ok", "remarques": ["un chiffre sans source"] if len(audits) == 1 else []})
    if "chef d'équipe" in system:
        chefs_vus.append(system.split(",")[0])
        return "Synthèse du pôle : " + user.split("Travail de ton équipe :")[1][:40]
    if system.startswith("Tu es l'Écrivain"):
        return "# Note\n\nVersion corrigée." if "Corrige-le" in user else "# Note\n\nPremier jet, 42 %."
    return f"Travail de {model} sur : " + system.split("Ta mission : ")[1].split("\n")[0]


def discussion(name, text):
    with moteur.LOCK:
        qg_log.use_project(name)
        qg_log.ROOT.mkdir(parents=True, exist_ok=True)
        qg_log.update(qg_log.LIVE, {}, lambda d: (d.clear(), d.update(qg_log.new_mission("Test", {"provider": "openai", "model": "gpt-test"}))))
        qg_log.new_message(text)
        moteur.RUNNING.add(name)
    moteur.boucle(name)
    with moteur.LOCK:
        qg_log.use_project(name)
        return qg_log.read(qg_log.LIVE, {}), qg_log.read(qg_log.CONS, []), qg_log.read(qg_log.LIVR / "index.json", [])


try:
    moteur.call = fake

    # 1. Simple discussion : une réponse, pas d'équipe, consigne appliquée
    d, cons, livr = discussion("salut", "Bonjour")
    texts = [e["text"] for e in d["events"]]
    assert "Bonjour ! Que puis-je faire ?" in texts and not [t for t in d["team"] if not t.get("chef")] and not livr
    assert all(t["status"] == "en veille" for t in d["team"])  # l'équipe de base est là, en veille
    assert cons[0]["status"] == "appliqué" and "salut" not in moteur.RUNNING

    # 2. Mission : deux recrues (identifiants rendus uniques), travail en parallèle, audit ko puis ok, remise
    d, cons, livr = discussion("note", "Fais une note de synthèse")
    team = [t for t in d["team"] if not t.get("chef")]
    assert [t["id"] for t in team] == ["chercheur", "chercheur2"], team
    assert not team[0]["brief"].startswith("@") and "root:" not in team[0]["brief"]  # aucun fichier local lu
    assert all(t["status"] == "terminé" for t in team)
    types = [e.get("type") for e in d["events"]]
    assert types.count("ko") == 1 and "ok" in types and "deliver" in types, [(e.get("from"), e.get("type"), e["text"][:60]) for e in d["events"]]
    assert [e for e in d["events"] if e.get("type") == "deliver"][0]["text"].startswith("Voici le livrable, validé")
    assert [v["version"] for v in livr] == [1, 2] and (qg_log.DATA / "projets" / "note" / "livrables").exists()
    assert sum(1 for e in d["events"] if e.get("type") == "work") >= 3  # avancement visible en direct
    assert cons[0]["status"] == "appliqué" and set(cons[0]["roles"]) == {"chercheur", "chercheur2"}
    assert len(audits) == 2
    assert d["usage"]["appels"] >= 6 and d["usage"]["entree"] == 100 * d["usage"]["appels"] and "gpt-test" in d["usage"]["modeles"]

    # 2 bis. Équipe par pôle : le PDG active un chef, deux experts rattachés à des chefs ; chaque chef fait la synthèse
    d, cons, livr = discussion("poles", "Organise une veille par pôle")
    team = {t["id"]: t for t in d["team"]}
    assert team["bib"]["status"] == "terminé" and team["ing"]["status"] == "terminé"   # chefs activés (ing par son expert)
    assert team["veilleur"]["equipe"] == "bib" and team["analyste_x"]["equipe"] == "ing"
    assert team["cor"]["status"] == "en veille"                                       # les autres chefs restent en veille
    assert sorted(chefs_vus) == ["Tu es Chef de la Recherche", "Tu es Chef technique"]
    assert any(e.get("from") == "bib" and e.get("type") == "hire" for e in d["events"])  # le chef recrute lui-même

    # 3. Erreur du fournisseur : le client la voit dans le chat, le fil s'arrête proprement
    def broken(*a):
        raise moteur.MoteurErreur("aucune clé pour openai")
    moteur.call = broken
    d, cons, _ = discussion("panne", "Bonjour")
    assert "aucune clé pour openai" in d["events"][-1]["text"] and "panne" not in moteur.RUNNING
    with moteur.LOCK:
        qg_log.use_project("panne")
        assert [m["text"] for m in qg_log.unread()] == ["Bonjour"]  # message remis en file, pas perdu

    # 4. Une discussion Claude Code n'est jamais prise par le moteur
    with moteur.LOCK:
        qg_log.use_project("cc")
        qg_log.ROOT.mkdir(parents=True, exist_ok=True)
        qg_log.update(qg_log.LIVE, {}, lambda d: (d.clear(), d.update(qg_log.new_mission("Test"))))
    assert moteur.kick("cc") is False

    # 5. Anthropic : recherche web + réflexion, reprise après pause_turn, repli sans outils si 400
    sent = []
    def fake_http(url, body=None, headers=None):
        sent.append(body)
        if len(sent) == 1:
            raise moteur.MoteurErreur("le fournisseur a refusé l'appel (400) : outil non activé")
        if len(sent) == 2:
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "sans outils"}]}
        if len(sent) == 3:
            return {"stop_reason": "pause_turn", "content": [{"type": "server_tool_use", "id": "x"}]}
        return {"stop_reason": "end_turn", "content": [{"type": "thinking"}, {"type": "text", "text": "avec recherche"}]}
    moteur.http, moteur.key = fake_http, lambda p: "cle-test"
    assert moteur.anthropic("claude-opus-5-5", moteur.AGENT, "x") == "sans outils"
    assert "tools" in sent[0] and "tools" not in sent[1] and moteur.SANS_WEB in sent[1]["system"]
    assert moteur.anthropic("claude-haiku-5-5", moteur.AGENT, "x") == "avec recherche"
    assert sent[2]["tools"][0]["type"] == "web_search_20250305" and moteur.AVEC_WEB in sent[2]["system"]
    assert sent[3]["messages"][-1]["role"] == "assistant"  # reprise sans nouveau message du client

    # 5 bis. Surcharge passagère (503) : nouvel essai automatique ; refus définitif (404) : pas de nouvel essai
    import io, urllib.error
    moteur.http = HTTP_ORIG
    tries, pauses = [], []
    def flaky(req, timeout=None):
        tries.append(1)
        if len(tries) < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b"surcharge"))
        return io.BytesIO(b'{"ok": true}')
    moteur.urllib.request.urlopen, moteur.time.sleep = flaky, pauses.append
    assert moteur.http("https://exemple.test", {}) == {"ok": True} and len(tries) == 3 and pauses == [3, 8]
    def gone(req, timeout=None):
        tries.append(1)
        raise urllib.error.HTTPError(req.full_url, 404, "gone", {}, io.BytesIO(b"plus disponible"))
    tries.clear(); moteur.urllib.request.urlopen = gone
    try:
        moteur.http("https://exemple.test", {})
        raise AssertionError("un 404 doit remonter")
    except moteur.MoteurErreur as e:
        assert "(404)" in str(e) and len(tries) == 1

    # 6. Lecture du JSON entouré de texte
    assert moteur.as_json('blabla {"a": 1} fin') == {"a": 1} and moteur.as_json("rien") is None
    print("test_moteur : OK")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
