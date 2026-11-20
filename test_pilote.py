"""Test du pilote automatique et de la boîte de réception : python3 test_pilote.py

Tout se passe dans un dossier temporaire, avec un moteur arrêté (aucun appel de modèle).
"""
import datetime, os, pathlib, shutil, sys, tempfile, time

TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["BUREAU_DATA"] = str(TMP)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import qg_log, moteur, qg_server as S  # noqa: E402

try:
    moteur.kick = lambda name: False  # pas de moteur : on vérifie seulement ce qui est écrit
    CC = {"provider": "claude-code", "model": "Claude Code (moteur actuel)"}

    # 1. Calcul du prochain lancement
    lundi_8h = datetime.datetime(2026, 11, 16, 8, 0)  # un lundi
    assert S.next_run({"frequence": "jour", "heure": "09:00"}, lundi_8h) == datetime.datetime(2026, 11, 16, 9, 0)
    assert S.next_run({"frequence": "jour", "heure": "07:30"}, lundi_8h) == datetime.datetime(2026, 11, 17, 7, 30)
    assert S.next_run({"frequence": "semaine", "heure": "18:00", "jour": 4}, lundi_8h) == datetime.datetime(2026, 11, 20, 18, 0)
    assert S.next_run({"frequence": "semaine", "heure": "07:00", "jour": 0}, lundi_8h) == datetime.datetime(2026, 11, 23, 7, 0)
    assert S.next_run({"frequence": "heures", "toutes_h": 6}, lundi_8h) == datetime.datetime(2026, 11, 16, 14, 0)

    # 2. Tâches invalides refusées
    for bad in [{}, {"titre": "x", "consigne": "y", "frequence": "jour", "heure": "25:00", "model": CC},
                {"titre": "x", "consigne": "y", "frequence": "mois", "model": CC},
                {"titre": "x", "consigne": "y", "frequence": "jour", "model": {"provider": "hermes", "model": "-x"}}]:
        try:
            S.valid_job(bad)
            raise AssertionError(f"accepté : {bad}")
        except ValueError:
            pass

    # 3. Création, lancement : une discussion dédiée, puis réutilisée au lancement suivant
    job = S.save_job({"titre": "Veille du lundi", "consigne": "Fais la veille de la semaine.", "frequence": "semaine", "heure": "09:00", "jour": 0, "model": CC})
    assert job["prochain"] > time.time() and not S.pilote_due()
    assert S.pilote_due(job["prochain"] + 1) == [job["id"]]
    name = S.run_job(job["id"])
    assert S.run_job(job["id"]) == name
    with S.LOCK:
        qg_log.use_project(name)
        live, msgs = qg_log.read(qg_log.LIVE, {}), [m["text"] for m in qg_log.unread()]
    assert live["topic"] == "🔁 Veille du lundi" and msgs == ["[Pilote automatique · Veille du lundi] Fais la veille de la semaine."] * 2
    j = qg_log.read(S.PILOTE, [])[0]
    assert j["discussion"] == name and j["dernier"] and j["prochain"] > time.time()

    # 4. Boîte de réception : une question ouverte, un blocage, un message en attente, une remise
    with S.LOCK:
        qg_log.use_project(name)
        qg_log.QUIET = True
        qg_log.main(["ask", "Quel périmètre ?", "France|Europe"])
        qg_log.main(["pdg", "client", "Voici le livrable.", "deliver"])
        qg_log.new_message("Et pour la Suisse ?")
    other = S.create_discussion("Une autre mission", {"provider": "openai", "model": "gpt-test"})
    with S.LOCK:
        qg_log.use_project(other)
        qg_log.unread()
        qg_log.main(["pdg", "client", "Le moteur s'est arrêté : aucune clé.", "ko"])
    box = S.inbox()
    assert [q["text"] for q in box["decider"]] == ["Quel périmètre ?"] and box["decider"][0]["options"] == ["France", "Europe"]
    assert [b["discussion"] for b in box["bloque"]] == [other]
    assert [a["discussion"] for a in box["attente"]] == [name]
    assert [l["discussion"] for l in box["livre"]] == [name]

    # 5. Tâche en pause : jamais lancée
    S.save_job({**job, "actif": False})
    assert not S.pilote_due(time.time() + 10 ** 9)
    print("test_pilote : OK")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
