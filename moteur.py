"""Moteur multi-modèles du Bureau : fait travailler une discussion de l'app avec le modèle choisi
(Anthropic, OpenAI, Google, Mistral, OpenRouter, Ollama, Hermes), sans Claude Code.

Lancé par qg_server.py dès qu'un message ou une réponse du client arrive dans une discussion dont le modèle
n'est pas « Claude Code ». Un fil par discussion. Chaque tour :
  1. le PDG (le modèle) lit la demande et décide : répondre, poser une question, recruter une équipe ;
  2. les recrues travaillent en parallèle (un appel au modèle chacune) et publient leur avancement ;
  3. l'Écrivain assemble le livrable, l'Auditeur le contrôle (deux corrections au plus), le PDG le remet.
Tout passe par qg_log : le QG affiche le travail comme pour une mission menée par Claude Code.
Les clés viennent du trousseau macOS (service « bureau-ia ») et ne sont jamais écrites ailleurs.
"""
import json, re, subprocess, threading, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

import qg_log

LOCK = threading.Lock()  # partagé avec qg_server : qg_log travaille sur une discussion à la fois
RUNNING = set()
KEYCHAIN = "bureau-ia"
TIMEOUT = 900  # une réponse longue (réflexion, recherches) peut prendre plusieurs minutes

OPENAI_LIKE = {"openai": "https://api.openai.com/v1", "mistral": "https://api.mistral.ai/v1",
               "openrouter": "https://openrouter.ai/api/v1", "ollama": "http://127.0.0.1:11434/v1"}
HERMES_DEFAULT = "défaut (config Hermes)"


class MoteurErreur(Exception):
    pass


# ---------- Appels aux modèles ----------

def key(provider):
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN, "-a", provider, "-w"], capture_output=True, text=True)
    if r.returncode:
        raise MoteurErreur(f"aucune clé pour {provider} : ajoute-la dans « Modèles et comptes »")
    return r.stdout.strip()


def http(url, body=None, headers=None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                 {"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise MoteurErreur(f"le fournisseur a refusé l'appel ({e.code}) : {detail}") from None
    except OSError as e:
        raise MoteurErreur(f"fournisseur injoignable : {e}") from None


def call(provider, model, system, user):
    """Un appel au modèle : consigne (system) + demande (user) → texte."""
    if provider == "anthropic":
        return anthropic(model, system, user)
    if provider == "google":
        r = http(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                 {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}]},
                 {"x-goog-api-key": key(provider)})
        return "".join(p.get("text", "") for c in r.get("candidates", [])[:1] for p in c.get("content", {}).get("parts", []))
    if provider in OPENAI_LIKE:
        auth = {} if provider == "ollama" else {"authorization": "Bearer " + key(provider)}
        r = http(OPENAI_LIKE[provider] + "/chat/completions",
                 {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, auth)
        return r["choices"][0]["message"]["content"] or ""
    if provider == "hermes":
        cmd = ["hermes", "-z", system + "\n\n" + user] + (["-m", model] if model and model != HERMES_DEFAULT else [])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT * 2)
        except FileNotFoundError:
            raise MoteurErreur("Hermes n'est pas installé (commande « hermes » introuvable)") from None
        if r.returncode not in (0,) or not r.stdout.strip():
            raise MoteurErreur(f"Hermes n'a pas répondu (code {r.returncode}) : {r.stderr.strip()[:300]}")
        return r.stdout.strip()
    raise MoteurErreur(f"fournisseur non pris en charge : {provider}")


def anthropic(model, system, user):
    """Claude avec réflexion adaptative et recherche web ; sans elles si le compte ou le modèle les refuse."""
    headers = {"x-api-key": key("anthropic"), "anthropic-version": "2023-06-01", "anthropic-beta": "server-side-fallback-2026-07-01"}
    search = "web_search_20260209" if model.startswith(("claude-opus", "claude-sonnet")) else "web_search_20250305"
    body = {"model": model, "max_tokens": 32000, "system": system.replace(SANS_WEB, AVEC_WEB), "fallbacks": "default",
            "thinking": {"type": "adaptive"}, "tools": [{"type": search, "name": "web_search", "max_uses": 8}],
            "messages": [{"role": "user", "content": user}]}
    try:
        r = http("https://api.anthropic.com/v1/messages", body, headers)
    except MoteurErreur as e:
        if "(400)" not in str(e):
            raise
        body = {k: v for k, v in body.items() if k not in ("thinking", "tools")} | {"system": system}
        r = http("https://api.anthropic.com/v1/messages", body, headers)
    for _ in range(5):  # recherche longue : l'API rend la main (pause_turn), on la relance telle quelle
        if r.get("stop_reason") != "pause_turn":
            break
        body["messages"] = [body["messages"][0], {"role": "assistant", "content": r["content"]}]
        r = http("https://api.anthropic.com/v1/messages", body, headers)
    if r.get("stop_reason") == "refusal":
        raise MoteurErreur("le modèle a refusé la demande")
    return "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")


def list_models(provider):
    """Modèles proposés par un fournisseur connecté (lus chez lui)."""
    if provider == "google":
        r = http("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key(provider)})
        return sorted(m["name"].removeprefix("models/") for m in r.get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))
    if provider == "anthropic":
        r = http("https://api.anthropic.com/v1/models?limit=100", headers={"x-api-key": key(provider), "anthropic-version": "2023-06-01"})
        return [m["id"] for m in r.get("data", [])]
    r = http(OPENAI_LIKE[provider] + "/models", headers={"authorization": "Bearer " + key(provider)})
    return sorted(m["id"] for m in r.get("data", []))


def as_json(text):
    """Premier objet JSON d'une réponse (les modèles l'entourent parfois de texte ou de ```)."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


# ---------- Consignes des rôles ----------

SANS_WEB = "Tu n'as pas accès au web : ne cite que des sources dont tu es certain qu'elles existent, et marque « (à vérifier) » tout fait précis que tu ne peux pas garantir."
AVEC_WEB = "Tu as un outil de recherche web : vérifie chaque fait précis en ligne et donne l'adresse (URL) de la source à côté ; marque « (à vérifier) » ce que tu n'as pas pu confirmer."

REGLES = """Règles de l'Auditeur, non négociables :
1. Zéro invention : aucun fait, chiffre, date, citation, nom ou référence inventé.
2. Tout est sourcé : chaque affirmation factuelle renvoie à une source identifiable ; avis et raisonnements sont présentés comme tels.
3. Si on ne sait pas : remplacer par une information vérifiable, retirer, ou signaler « (non vérifié) ». Jamais de supposition présentée comme un fait.
4. Respect de la consigne du client : format, longueur, public.
""" + SANS_WEB

PDG = """Tu es le PDG du Bureau, une petite équipe d'IA au service d'un client. Tu es son seul interlocuteur.
Tu réfléchis à sa demande, tu cadres, et tu recrutes les rôles nécessaires (inventés si besoin), qui travaillent en parallèle.
""" + REGLES + """
Réponds UNIQUEMENT par un objet JSON :
{"reponse": "ton message au client, court, en français",
 "question": null ou {"texte": "question au client", "choix": ["A", "B"]},
 "equipe": [] ou [{"id": "minuscules_sans_espace", "nom": "Nom du rôle", "mission": "une phrase", "brief": "instructions précises et complètes"}],
 "livrable": null ou "titre du livrable"}
- Pose une question seulement si une décision revient vraiment au client ; dans ce cas, pas d'équipe.
- Recrute une équipe (1 à 4 rôles aux tâches indépendantes) seulement quand il y a un livrable à produire ou à modifier.
- Pour une simple discussion, réponds sans équipe."""

AGENT = """Tu es {nom}, recruté par le PDG du Bureau pour une mission précise.
""" + REGLES + """
Ta mission : {mission}
Ton brief : {brief}
Rends directement ton travail, complet, en français, en Markdown."""

ECRIVAIN = """Tu es l'Écrivain du Bureau. Tu assembles le livrable final pour le client à partir des seuls travaux de l'équipe.
""" + REGLES + """
Rends uniquement le livrable, en Markdown, prêt à être lu par le client."""

AUDITEUR = """Tu es l'Auditeur du Bureau. Tu contrôles le livrable avant sa remise.
""" + REGLES + """
Réponds UNIQUEMENT par un objet JSON : {"verdict": "ok" ou "ko", "remarques": ["point précis à corriger", ...]}
« ko » seulement pour une infraction aux règles ou à la consigne du client, pas pour une préférence de style."""


# ---------- Journal (qg_log, sous verrou) ----------

def log(name, *args):
    with LOCK:
        qg_log.use_project(name)
        qg_log.QUIET = True
        try:
            qg_log.main([str(a) for a in args])
        except qg_log.Erreur as e:
            if "étape inconnue" not in str(e):  # mission aux étapes personnalisées : on journalise sans étape
                raise
            qg_log.main([str(a) for a in args[:4]])


def snapshot(name):
    with LOCK:
        qg_log.use_project(name)
        d = qg_log.read(qg_log.LIVE, {})
        index = qg_log.read(qg_log.LIVR / "index.json", [])
        last = None
        if index:
            f = qg_log.LIVR / index[-1]["file"]
            last = f.read_text(encoding="utf-8") if f.exists() else None
        return d, last


def chat_history(d, n=30):
    lines = [f"{'Client' if e['from'] == 'client' else 'PDG'} : {e['text']}" for e in d.get("events", [])
             if {e.get("from"), e.get("to")} <= {"client", "pdg"} and e.get("text")]
    return "\n".join(lines[-n:])


def describe(m):
    if m.get("kind") == "answer":
        return f"Réponse du client à « {m['question']} » : {m['text']}"
    if m.get("kind") == "dismiss":
        return f"Le client a mis fin au contrat de {m['name']} : {m['text']}"
    return f"Message n° {m['id']} du client : {m['text']}"


# ---------- Un tour de travail ----------

def tour(name, msgs):
    d, current = snapshot(name)
    provider, model = d["model"]["provider"], d["model"]["model"]
    ask = lambda system, user: call(provider, model, system, user)
    ids = [m["id"] for m in msgs if m.get("kind", "message") == "message"]
    for n in ids:
        log(name, "ack", n, f"Reçu. Je réfléchis avec {model}.")
    log(name, "pdg", "-", "Je lis la demande et je décide de la suite.", "work", "Cadrage")

    contexte = (f"Sujet de la discussion : {d.get('topic', '')}\n\nConversation jusqu'ici :\n{chat_history(d)}\n\n"
                + (f"Livrable actuel :\n{current[:20000]}\n\n" if current else "")
                + "Nouveau :\n" + "\n".join(describe(m) for m in msgs))
    raw = ask(PDG, contexte)
    plan = as_json(raw) or {"reponse": raw.strip()[:4000]}
    log(name, "pdg", "client", plan.get("reponse") or "Bien reçu.", "-", "Cadrage")
    q = plan.get("question")
    if isinstance(q, dict) and q.get("texte") and len(q.get("choix") or []) >= 2:
        log(name, "ask", q["texte"], "|".join(str(c) for c in q["choix"][:5]))

    team = []
    for i, m in enumerate((plan.get("equipe") or [])[:4]):
        if not isinstance(m, dict):
            continue
        rid = (re.sub(r"[^a-z0-9_]", "", qg_log.slug(str(m.get("id") or m.get("nom") or "agent")).replace("-", "_")) or "agent")[:12]
        known = qg_log.ROLES | qg_log.PERMANENT | {t["id"] for t in d.get("team", [])}
        base, k = rid if rid[0].isalpha() else "a" + rid, 2
        rid = base
        while rid in known or rid in {t["id"] for t in team}:
            rid, k = f"{base[:13]}{k}", k + 1
        # « @fichier » ferait lire un fichier local par qg_log : un brief venu du modèle n'y a pas droit
        member = {"id": rid, "nom": str(m.get("nom") or rid)[:60], "mission": str(m.get("mission") or "")[:300],
                  "brief": str(m.get("brief") or "").lstrip("@")}
        log(name, "recruit", rid, member["nom"], member["mission"], f"Recruté par {model} pour cette demande", member["brief"])
        team.append(member)
    for n in ids:
        for t in team or [{"id": "pdg"}]:
            log(name, "dispatch", n, t["id"], "Pris en compte dans le travail" if team else "Réponse du PDG")
    if not team:
        for n in ids:
            log(name, "applied", n, "pdg", "Réponse donnée au client")
        return

    def work(t):
        log(name, t["id"], "-", f"Je commence : {t['mission']}", "work", "Rédaction")
        try:
            out = ask(AGENT.format(**t), contexte)
        except MoteurErreur as e:
            log(name, t["id"], "pdg", f"Bloqué : {e}", "ko", "Rédaction")
            return t, ""
        log(name, t["id"], "pdg", f"Terminé ({len(out.split())} mots). " + out.strip()[:280], "-", "Rédaction")
        log(name, "release", t["id"], "Part terminée")
        return t, out
    with ThreadPoolExecutor(len(team)) as pool:  # les recrues travaillent en même temps
        results = list(pool.map(work, team))

    travaux = "\n\n".join(f"## Travail de {t['nom']} ({t['mission']})\n{out}" for t, out in results if out)
    if not travaux:
        log(name, "pdg", "client", "L'équipe n'a rien pu produire (voir les messages des recrues).", "ko")
        return
    log(name, "ecr", "-", "J'assemble le livrable à partir des travaux de l'équipe.", "work", "Rédaction")
    texte = ask(ECRIVAIN, f"{contexte}\n\nTravaux de l'équipe :\n{travaux}")
    titre = plan.get("livrable") or d.get("topic") or "livrable"
    fichier = qg_log.DATA / "projets" / name / "travail" / f"{qg_log.slug(str(titre))[:50] or 'livrable'}.md"
    for tour_audit in range(3):
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(texte, encoding="utf-8")
        log(name, "livrable", fichier, "ecr", "premier jet" if tour_audit == 0 else f"après audit {tour_audit}")
        log(name, "ecr", "aud", "Livrable prêt pour l'audit.", "-", "Audit final")
        verdict = as_json(ask(AUDITEUR, f"Demande du client et contexte :\n{contexte}\n\nLivrable à contrôler :\n{texte}")) or {}
        remarques = [str(r) for r in verdict.get("remarques") or []][:10]
        if verdict.get("verdict") != "ko":
            log(name, "aud", "pdg", "Audit validé." + (" Remarques : " + " ; ".join(remarques) if remarques else ""), "ok", "Audit final")
            break
        log(name, "aud", "ecr", "Rejeté : " + " ; ".join(remarques), "ko", "Audit final")
        if tour_audit == 2:
            break
        texte = ask(ECRIVAIN, f"{contexte}\n\nTravaux de l'équipe :\n{travaux}\n\nLivrable précédent :\n{texte}\n\n"
                              "Corrige-le selon ces remarques de l'Auditeur :\n- " + "\n- ".join(remarques))
    ok = verdict.get("verdict") != "ko"
    log(name, "pdg", "client", ("Voici le livrable, validé par l'Auditeur (onglet Rendu)." if ok else
                                "Voici le livrable (onglet Rendu). L'Auditeur a encore des réserves : " + " ; ".join(remarques)),
        "deliver", "Audit final")
    for n in ids:
        for t in team:
            log(name, "applied", n, t["id"], "Intégré au livrable")


def boucle(name):
    msgs = []
    try:
        while True:
            with LOCK:
                qg_log.use_project(name)
                msgs = qg_log.unread()
                if not msgs:
                    RUNNING.discard(name)
                    return
            tour(name, msgs)
    except Exception as e:  # le client doit voir l'erreur dans le chat, pas un bureau figé
        with LOCK:
            RUNNING.discard(name)
            qg_log.use_project(name)
            seen = int(qg_log.SEEN.read_text()) if qg_log.SEEN.exists() else 0
            qg_log.SEEN.write_text(str(max(0, seen - len(msgs))))  # messages remis en file : rien n'est perdu
        try:
            log(name, "pdg", "client", f"Le moteur s'est arrêté : {e}. Ton message est gardé : il sera repris "
                                       "à ton prochain message (ou au redémarrage de l'app).", "ko")
        except Exception:
            pass


def engine_of(name):
    with LOCK:
        qg_log.use_project(name)
        return qg_log.read(qg_log.LIVE, {}).get("model", qg_log.DEFAULT_MODEL).get("provider")


def kick(name):
    """Fait travailler la discussion si son modèle n'est pas Claude Code (un seul fil par discussion)."""
    if engine_of(name) in (None, "claude-code"):
        return False
    with LOCK:
        if name in RUNNING:
            return True
        RUNNING.add(name)
    threading.Thread(target=boucle, args=(name,), daemon=True).start()
    return True
