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

audits = []
seen = []


def fake(provider, model, system, user):
    seen.append(threading.current_thread().name)
    if system.startswith("Tu es le PDG"):
        if "bonjour" in user.lower():
            return json.dumps({"reponse": "Bonjour ! Que puis-je faire ?", "equipe": []})
        return "Voici mon plan :\n```json\n" + json.dumps({
            "reponse": "Je lance deux recrues.", "livrable": "Note de synthèse",
            "equipe": [{"id": "Chercheur", "nom": "Chercheur", "mission": "Lister les points", "brief": "@/etc/passwd"},
                       {"id": "chercheur", "nom": "Chercheur 2", "mission": "Lister les risques", "brief": "Sois bref."}]}) + "\n```"
    if system.startswith("Tu es l'Auditeur"):
        audits.append(user)
        return json.dumps({"verdict": "ko" if len(audits) == 1 else "ok", "remarques": ["un chiffre sans source"] if len(audits) == 1 else []})
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
    assert "Bonjour ! Que puis-je faire ?" in texts and not d.get("team") and not livr
    assert cons[0]["status"] == "appliqué" and "salut" not in moteur.RUNNING

    # 2. Mission : deux recrues (identifiants rendus uniques), travail en parallèle, audit ko puis ok, remise
    d, cons, livr = discussion("note", "Fais une note de synthèse")
    team = d["team"]
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

    # 3. Erreur du fournisseur : le client la voit dans le chat, le fil s'arrête proprement
    def broken(*a):
        raise moteur.MoteurErreur("aucune clé pour openai")
    moteur.call = broken
    d, cons, _ = discussion("panne", "Bonjour")
    assert "aucune clé pour openai" in d["events"][-1]["text"] and "panne" not in moteur.RUNNING

    # 4. Une discussion Claude Code n'est jamais prise par le moteur
    with moteur.LOCK:
        qg_log.use_project("cc")
        qg_log.ROOT.mkdir(parents=True, exist_ok=True)
        qg_log.update(qg_log.LIVE, {}, lambda d: (d.clear(), d.update(qg_log.new_mission("Test"))))
    assert moteur.kick("cc") is False

    # 5. Lecture du JSON entouré de texte
    assert moteur.as_json('blabla {"a": 1} fin') == {"a": 1} and moteur.as_json("rien") is None
    print("test_moteur : OK")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
