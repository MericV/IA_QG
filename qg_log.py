"""Journal du QG du Bureau.

Les données sont centralisées dans le dossier du Bureau (celui de ce script, ou $BUREAU_DATA) :
  projets/<nom>/              QG en direct du projet (index.html, qg-live.json, consignes.json, questions.json)
  projets/<nom>/livrables/    versions successives des livrables, avec leurs différences
  projets/<nom>/missions/     missions terminées (JSON + page rejouable) et index.html (historique)
Le projet est reconnu par le dossier courant, associé à <nom> dans projets.json.

Mission
  init "Sujet" [nom-du-projet]        archive la mission précédente et en démarre une (nom : 1re fois seulement)
  stages "Cadrage|Sources|..."        déclare les étapes de la mission (par défaut : Cadrage|Sources|Rédaction|Forme|Audit final)
  FROM TO "texte" [type] [étape]      échange ; TO = "-" ou "a,b" ; type = ok|ko|deliver|work|-
  hire ID "Nom" ROLE_DE_BASE "raison" embauche d'un renfort
  livrable FICHIER [ROLE] ["libellé"] enregistre une version du livrable (et ses différences avec la précédente)
  export                              écrit la page rejouable de la mission dans missions/ et met à jour l'historique
  where                               dossier du projet et adresse du QG

Client
  ask "Question ?" "Choix A|Choix B"  le PDG pose une question au client (boutons dans le QG)
  ack N "réponse"                     le PDG accuse réception du message n° N
  dispatch N ROLE "consigne"          le PDG transmet le message N à un rôle
  applied N ROLE "ce qui a changé"    le rôle confirme qu'il a appliqué la consigne
  inbox                               messages et réponses non lus
  wait                                attend un message ou une réponse, l'affiche, puis s'arrête
Chaque écriture affiche aussi ce que le client a envoyé et qui n'a pas encore été lu.
"""
import difflib, fcntl, html, json, os, pathlib, re, shutil, sys, time, unicodedata
from contextlib import contextmanager

HOME = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get("BUREAU_DATA", HOME))
REGISTRY = DATA / "projets.json"
ROLES = {"pdg", "aud", "bib", "ecr", "cor", "client", "ana", "str", "avo", "des", "ing", "jur", "cdp"}
TYPES = {"ok", "ko", "deliver", "work"}
HIRE_ID = re.compile(r"[a-z][a-z0-9_]{0,15}")
DEFAULT_STAGES = ["Cadrage", "Sources", "Rédaction", "Forme", "Audit final"]


class Erreur(Exception):
    """Erreur d'utilisation : message clair, pas de trace Python."""


def set_root(name=None):
    global ROOT, LIVE, CONS, QUEST, LIVR, INBOX, SEEN
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    cwd = str(pathlib.Path.cwd().resolve())
    if name:
        reg[cwd] = name
        DATA.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    ROOT = DATA / "projets" / reg.get(cwd, pathlib.Path.cwd().name)
    LIVE, CONS, QUEST = ROOT / "qg-live.json", ROOT / "consignes.json", ROOT / "questions.json"
    LIVR = ROOT / "livrables"
    INBOX, SEEN = ROOT / "inbox.jsonl", ROOT / ".inbox-lu"


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:50] or "mission"


def now():
    return {"t": time.strftime("%H:%M:%S"), "ts": round(time.time(), 1)}


def read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


@contextmanager
def locked():
    """Verrou exclusif du projet, partagé entre les commandes et qg_server.py. Non réentrant : ne pas imbriquer."""
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / ".verrou", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def write_json(path, data):
    """Écriture atomique : un lecteur ne voit jamais un fichier à moitié écrit."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def update(path, default, fn):
    """Lecture-modification-écriture d'un JSON sous verrou."""
    with locked():
        data = read(path, default)
        result = fn(data)
        write_json(path, data)
        return result


def require_mission():
    if not LIVE.exists():
        raise Erreur('aucune mission en cours : lance d\'abord  python3 qg_log.py init "Sujet"')


def new_mission(topic):
    return {"mission": time.strftime("%Y%m%d-%H%M%S-") + os.urandom(2).hex(), "topic": topic, "label": "En direct", "note": "",
            "stages": [{"id": slug(s), "name": s} for s in DEFAULT_STAGES], "events": []}


def known_roles():
    hired = {e["hire"]["id"] for e in read(LIVE, {"events": []})["events"] if e.get("type") == "hire"}
    return ROLES | hired


def check_role(role, allowed=None):
    allowed = allowed or known_roles()
    if role not in allowed:
        raise Erreur(f"rôle inconnu « {role} ». Rôles possibles : {', '.join(sorted(allowed))}")
    return role


def check_stage(stage):
    stages = read(LIVE, {}).get("stages", [])
    for s in stages:
        if stage in (s["id"], s["name"]) or slug(stage) == s["id"]:
            return s["id"]
    raise Erreur(f"étape inconnue « {stage} ». Étapes : {' | '.join(s['name'] for s in stages)} (voir la commande stages)")


def append_event(ev):
    require_mission()
    ev.update(now())
    update(LIVE, {}, lambda d: d["events"].append(ev))


def message(n):
    msgs = read(CONS, [])
    if not 1 <= n <= len(msgs):
        raise Erreur(f"message n° {n} introuvable ({len(msgs)} message(s) reçu(s) dans cette mission)")
    return n


# ---------- Côté client (appelé par qg_server.py) ----------

def new_message(text):
    require_mission()

    def add(d):
        d.append({"id": len(d) + 1, "text": text, **now(), "status": "reçu", "roles": {}})
        return len(d)
    n = update(CONS, [], add)
    append_event({"from": "client", "to": "pdg", "text": text})
    inbox({"kind": "message", "id": n, "text": text})
    return n


def answer(qid, choice):
    require_mission()

    def set_answer(d):
        q = next((q for q in d if q["id"] == qid), None)
        if not q or q.get("answer") or choice not in q["options"]:
            return None
        q["answer"] = choice
        q.update({"answered_" + k: v for k, v in now().items()})
        return q["text"]
    question = update(QUEST, [], set_answer)
    if question is None:
        return False
    append_event({"from": "client", "to": "pdg", "text": f"Réponse à « {question} » : {choice}"})
    inbox({"kind": "answer", "id": qid, "text": choice, "question": question})
    return True


def inbox(entry):
    with locked(), open(INBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({**entry, **now()}, ensure_ascii=False) + "\n")


def unread():
    """Messages non lus. Le compteur n'avance que sur les lignes lues sans erreur : rien ne se perd."""
    with locked():
        lines = INBOX.read_text(encoding="utf-8").splitlines() if INBOX.exists() else []
        seen = int(SEEN.read_text()) if SEEN.exists() else 0
        msgs = []
        for line in lines[seen:]:
            try:
                msgs.append(json.loads(line))
            except ValueError:
                break
        SEEN.write_text(str(seen + len(msgs)))
    return msgs


def show(msgs):
    for m in msgs:
        if m.get("kind") == "answer":
            print(f"❓ RÉPONSE DU CLIENT [{m['t']}] à « {m['question']} » : {m['text']}")
        else:
            print(f"📨 MESSAGE DU CLIENT n° {m['id']} [{m['t']}] au PDG : {m['text']}")
            print(f"   → à traiter : ack {m['id']} \"...\" puis dispatch {m['id']} ROLE \"...\" pour chaque rôle concerné")


# ---------- Livrables ----------

def save_livrable(path, role, label):
    src = pathlib.Path(path)
    if not src.is_file():
        raise Erreur(f"fichier introuvable : {path}")
    require_mission()
    data = src.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = None  # .docx, .pdf… : on garde la version, sans comparaison
    # Tout le calcul (numéro, fichiers, index) sous verrou : plusieurs agents peuvent livrer en même temps.
    with locked():
        LIVR.mkdir(parents=True, exist_ok=True)
        index = read(LIVR / "index.json", [])
        same = [v for v in index if v["source"] == str(src.resolve())]
        n = len(index) + 1
        base = f"{n:02d}-{slug(src.stem)}"
        (LIVR / f"{base}{src.suffix}").write_bytes(data)
        prev = same[-1] if same else None
        if text is None:
            diff = "Fichier non texte : pas de comparaison possible.\n"
        else:
            old = (LIVR / prev["file"]).read_text(encoding="utf-8") if prev and not prev.get("binary") else ""
            diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), "version précédente", "cette version"))
        (LIVR / f"{base}.diff").write_text(diff, encoding="utf-8")
        entry = {"n": n, "name": src.name, "source": str(src.resolve()), "version": len(same) + 1, "label": label,
                 "file": f"{base}{src.suffix}", "diff": f"{base}.diff", "binary": text is None,
                 "words": len(text.split()) if text is not None else None, **now()}
        index.append(entry)
        write_json(LIVR / "index.json", index)
    size = f"{entry['words']} mots" if text is not None else f"{len(data) // 1024 + 1} Ko"
    append_event({"from": role, "type": "deliverable", "livrable": n,
                  "text": f"{src.name}, version {entry['version']}" + (f" : {label}" if label else "") + f" ({size})"})
    return entry


# ---------- État complet, export et historique ----------

def state(contents=False):
    data = read(LIVE, {"events": []})
    data["consignes"], data["questions"] = read(CONS, []), read(QUEST, [])
    livr = read(LIVR / "index.json", [])
    if contents:
        for v in livr:
            if not v.get("binary"):
                v["content"] = (LIVR / v["file"]).read_text(encoding="utf-8")
            v["diff_text"] = (LIVR / v["diff"]).read_text(encoding="utf-8")
    data["livrables"] = [{k: v for k, v in x.items() if k != "source"} for x in livr]
    return data


def mission_name(data):
    first = data["events"][0].get("ts") if data.get("events") else None
    day = time.strftime("%Y-%m-%d", time.localtime(first)) if first else data.get("date") or time.strftime("%Y-%m-%d")
    # l'identifiant (AAAAMMJJ-HHMMSS-xxxx) distingue deux missions du même jour au même sujet, même lancées dans la même seconde
    m = re.fullmatch(r"\d{8}-(\d{6}-[0-9a-f]{4})", data.get("mission", ""))
    return f"{day}-{m.group(1) + '-' if m else ''}{slug(data.get('topic', ''))}"


def export():
    data = state(contents=True)
    if not data.get("events"):
        return None
    data["label"] = "Mission terminée" if data["events"][-1].get("type") == "deliver" else "Mission en cours"
    out = ROOT / "missions" / mission_name(data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    page = (HOME / "qg.html").read_text(encoding="utf-8")
    # Aucun « < » brut dans le bloc JSON : ni </script> ni <!--<script ne peuvent en sortir
    block = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    page = re.sub(r'(<script id="session" type="application/json">).*?(</script>)', lambda m: m.group(1) + block + m.group(2), page, count=1, flags=re.S)
    out.with_suffix(".html").write_text(page, encoding="utf-8")
    write_history()
    return out.with_suffix(".html")


def stats(data):
    ev = data.get("events", [])
    ts = [e["ts"] for e in ev if "ts" in e]
    stages = {}
    for e in ev:
        if e.get("stage") and e.get("type") in ("ok", "ko"):
            s = stages.setdefault(e["stage"], {"ko": 0, "ok": False})
            s["ko"] += e["type"] == "ko"
            s["ok"] = s["ok"] or e["type"] == "ok"
    validated = [s for s in stages.values() if s["ok"]]
    return {"events": len(ev), "minutes": round((ts[-1] - ts[0]) / 60) if len(ts) > 1 else None,
            "renvois": sum(s["ko"] for s in stages.values()),
            "premier_coup": f"{sum(1 for s in validated if not s['ko'])}/{len(validated)}" if validated else "—",
            "agents": len({r for e in ev for r in [e["from"], *([e["to"]] if isinstance(e.get("to"), str) else e.get("to", []))]} - {"client"})}


def write_history():
    (ROOT / "missions").mkdir(parents=True, exist_ok=True)
    rows = []
    for f in sorted((ROOT / "missions").glob("*.json"), reverse=True):
        d = json.loads(f.read_text(encoding="utf-8"))
        s = stats(d)
        link = f'<a href="{html.escape(f.with_suffix(".html").name)}">{html.escape(d.get("topic") or f.stem)}</a>' if f.with_suffix(".html").exists() else html.escape(d.get("topic") or f.stem)
        rows.append(f"<tr><td>{f.stem[:10]}</td><td>{link}</td><td>{s['events']}</td><td>{s['agents']}</td>"
                    f"<td>{s['renvois']}</td><td>{s['premier_coup']}</td><td>{'' if s['minutes'] is None else str(s['minutes']) + ' min'}</td></tr>")
    (ROOT / "missions" / "index.html").write_text(HISTORY.format(projet=html.escape(ROOT.name), rows="\n".join(rows) or
        '<tr><td colspan="7">Aucune mission archivée pour l\'instant.</td></tr>'), encoding="utf-8")


HISTORY = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Historique · {projet}</title>
<style>
:root {{ --bg:#eceff4; --panel:#fff; --line:#dde2ea; --fg:#1a2130; --dim:#6b7587; --accent:#2f5bff; color-scheme: light; }}
body {{ background:var(--bg); color:var(--fg); font:14px/1.5 system-ui, sans-serif; margin:0; padding:24px max(16px, env(safe-area-inset-left, 0px)); }}
main {{ max-width:960px; margin:0 auto; }} h1 {{ font-size:20px; margin:0 0 4px; }} p {{ color:var(--dim); margin:0 0 16px; }}
.wrap {{ overflow-x:auto; background:var(--panel); border:1px solid var(--line); border-radius:12px; }}
table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }}
th {{ font:500 11px ui-monospace, Menlo, monospace; text-transform:uppercase; letter-spacing:.06em; color:var(--dim); }}
td:nth-child(2) {{ white-space:normal; }} a {{ color:var(--accent); font-weight:600; }}
</style>
<main><h1>Historique des missions</h1><p>Projet {projet} · chaque mission se rejoue dans le QG.</p>
<div class="wrap"><table><thead><tr><th>Date</th><th>Mission</th><th>Échanges</th><th>Agents</th><th>Renvois</th><th>Audits validés du 1er coup</th><th>Durée</th></tr></thead>
<tbody>
{rows}
</tbody></table></div></main>
"""


# ---------- Ligne de commande ----------

def main(a):
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "where":
        port = ROOT / ".port"
        print(ROOT)
        print(f"QG : http://127.0.0.1:{port.read_text()}/" if port.exists() else "QG : serveur non lancé")
        print("Mission en cours" if LIVE.exists() else "Aucune mission : vérifie que tu es à la racine du projet, puis lance init")
        return
    if cmd == "init":
        if len(a) < 2:
            raise Erreur('usage : init "Sujet" [nom-du-projet]')
        if len(a) > 2:
            set_root(a[2])
        ROOT.mkdir(parents=True, exist_ok=True)
        if (saved := export()):
            print(f"Mission précédente archivée : {saved}")
        shutil.copy(HOME / "qg.html", ROOT / "index.html")
        for p in (INBOX, SEEN, CONS, QUEST):
            p.unlink(missing_ok=True)
        shutil.rmtree(LIVR, ignore_errors=True)
        update(LIVE, {}, lambda d: (d.clear(), d.update(new_mission(a[1]))))
        write_history()
        print(f"Mission démarrée dans {ROOT}")
        return
    if cmd == "inbox":
        show(unread())
        return
    if cmd == "wait":
        while not (msgs := unread()):
            time.sleep(1)
        show(msgs)
        return
    if cmd == "export":
        out = export()
        print(f"Mission exportée : {out}" if out else "Rien à exporter : la mission ne contient aucun échange.")
        return
    if cmd == "stages":
        require_mission()
        names = [s.strip() for s in a[1].split("|") if s.strip()]
        if not names:
            raise Erreur('aucune étape : stages "Cadrage|Sources|..."')
        update(LIVE, {}, lambda d: d.__setitem__("stages", [{"id": slug(s), "name": s} for s in names]))
    elif cmd == "hire":
        check_role(a[3], ROLES)
        if not HIRE_ID.fullmatch(a[1]):
            raise Erreur(f"identifiant « {a[1]} » invalide : minuscules, chiffres et _ (16 caractères max.), ex. bib2")
        if a[1] in known_roles():
            raise Erreur(f"l'identifiant « {a[1]} » est déjà pris")
        append_event({"from": "pdg", "type": "hire", "hire": {"id": a[1], "name": a[2], "like": a[3]}, "text": a[4]})
    elif cmd == "ask":
        require_mission()
        options = [o.strip() for o in a[2].split("|") if o.strip()]
        if len(options) < 2:
            raise Erreur('il faut au moins deux choix : ask "Question ?" "Choix A|Choix B"')
        qid = update(QUEST, [], lambda d: (d.append({"id": len(d) + 1, "text": a[1], "options": options, "answer": None, **now()}), len(d))[1])
        append_event({"from": "pdg", "to": "client", "type": "question", "question": qid, "text": a[1] + " (" + " / ".join(options) + ")"})
    elif cmd == "ack":
        n = message(int(a[1]))
        append_event({"from": "pdg", "to": "client", "text": a[2]})
        update(CONS, [], lambda d: d[n - 1].__setitem__("status", "lu") if not d[n - 1]["roles"] else None)
    elif cmd in ("dispatch", "applied"):
        n, role = message(int(a[1])), check_role(a[2])
        if cmd == "dispatch":
            append_event({"from": "pdg", "to": role, "text": f"Consigne n° {n} du client : {a[3]}"})
        else:
            if role not in read(CONS, [])[n - 1]["roles"]:
                raise Erreur(f"la consigne n° {n} n'a pas été transmise à « {role} » (dispatch d'abord)")
            append_event({"from": role, "to": "pdg", "text": f"Consigne n° {n} appliquée : {a[3]}"})

        def change(d):
            m = d[n - 1]
            m["roles"][role] = "transmis" if cmd == "dispatch" else "appliqué"
            m["status"] = "appliqué" if all(v == "appliqué" for v in m["roles"].values()) else "transmis"
        update(CONS, [], change)
    elif cmd == "livrable":
        role = check_role(a[2]) if len(a) > 2 else "ecr"
        entry = save_livrable(a[1], role, a[3] if len(a) > 3 else "")
        print(f"Version {entry['version']} de {entry['name']} enregistrée ({entry['words']} mots)")
    else:
        if len(a) < 3:
            raise Erreur('usage : FROM TO "texte" [type] [étape]  (voir python3 qg_log.py sans argument)')
        ev = {"from": check_role(a[0]), "text": a[2]}
        if a[1] != "-":
            tos = [check_role(t) for t in a[1].split(",")]
            ev["to"] = tos if len(tos) > 1 else tos[0]
        if len(a) > 3 and a[3] != "-":
            if a[3] not in TYPES:
                raise Erreur(f"type inconnu « {a[3]} ». Types : {', '.join(sorted(TYPES))} ou -")
            ev["type"] = a[3]
        if len(a) > 4:
            ev["stage"] = check_stage(a[4])
        append_event(ev)
    show(unread())


set_root()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erreur as e:
        sys.exit(f"Erreur : {e}")
    except (IndexError, ValueError):
        sys.exit("Erreur : arguments manquants ou invalides. Lance  python3 qg_log.py  sans argument pour l'aide.")
