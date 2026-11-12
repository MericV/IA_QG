"""Journal du QG en direct.

Tout est centralisé dans le dossier du Bureau (celui de ce script) :
  projets/<nom>/            QG en direct du projet (index.html, qg-live.json, consignes.json)
  projets/<nom>/missions/   archive des missions terminées
Le projet est reconnu par le dossier courant (associé à <nom> dans projets.json).

  python3 qg_log.py init "Sujet de la mission" [nom-du-projet]   archive la mission précédente et en démarre une
  python3 qg_log.py where                                        affiche le dossier QG du projet courant
  python3 qg_log.py FROM TO "texte" [ok|ko|deliver|work|-] [stage]   (TO = "-" si aucun, "a,b" pour plusieurs)
  python3 qg_log.py hire ID "Nom" ROLE_DE_BASE "raison"              (embauche d'un renfort)

Consignes du client (il écrit au PDG, qui redistribue) :
  python3 qg_log.py ack N "réponse au client"          le PDG accuse réception du message n° N
  python3 qg_log.py dispatch N ROLE "consigne"         le PDG transmet le message N à un rôle
  python3 qg_log.py applied N ROLE "ce qui a changé"   le rôle confirme qu'il a appliqué la consigne
  python3 qg_log.py inbox                              affiche les messages non lus
  python3 qg_log.py wait                               attend un message, l'affiche, puis s'arrête
Chaque écriture affiche aussi les messages du client non lus.
"""
import fcntl, json, pathlib, re, shutil, sys, time, unicodedata

HOME = pathlib.Path(__file__).resolve().parent
REGISTRY = HOME / "projets.json"


def set_root(name=None):
    """Choisit le dossier QG du projet courant ; avec `name`, associe le dossier courant à ce nom."""
    global ROOT, LIVE, CONS, INBOX, SEEN
    reg = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    cwd = str(pathlib.Path.cwd().resolve())
    if name:
        reg[cwd] = name
        REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    ROOT = HOME / "projets" / reg.get(cwd, pathlib.Path.cwd().name)
    LIVE, CONS = ROOT / "qg-live.json", ROOT / "consignes.json"
    INBOX, SEEN = ROOT / "inbox.jsonl", ROOT / ".inbox-lu"


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:50] or "mission"


def archive():
    """Range la mission en cours (journal + consignes) dans missions/ si elle contient des échanges."""
    if not LIVE.exists():
        return None
    data = json.loads(LIVE.read_text(encoding="utf-8"))
    if not data.get("events"):
        return None
    data["consignes"] = json.loads(CONS.read_text(encoding="utf-8")) if CONS.exists() else []
    day = time.strftime("%Y-%m-%d", time.localtime(LIVE.stat().st_mtime))
    out = ROOT / "missions" / f"{day}-{slug(data.get('topic', ''))}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


set_root()


def update(path, default, fn):
    """Lecture-modification-écriture d'un JSON sous verrou (partagé avec qg_server.py)."""
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(ROOT / ".verrou", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        result = fn(data)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return result


def append_event(ev):
    update(LIVE, {"topic": "", "label": "En direct", "note": "", "events": []}, lambda d: d["events"].append(ev))


def new_message(text):
    """Enregistre un message du client (appelé par le serveur) et renvoie son numéro."""
    def add(d):
        n = len(d) + 1
        d.append({"id": n, "text": text, "t": time.strftime("%H:%M:%S"), "status": "reçu", "roles": {}})
        return n
    n = update(CONS, [], add)
    append_event({"from": "client", "to": "pdg", "text": text})
    with open(INBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": n, "text": text, "t": time.strftime("%H:%M:%S")}, ensure_ascii=False) + "\n")
    return n


def set_status(n, role=None, state=None, status=None):
    def change(d):
        m = d[n - 1]
        if role:
            m["roles"][role] = state
        if status:
            m["status"] = status
        elif m["roles"] and all(v == "appliqué" for v in m["roles"].values()):
            m["status"] = "appliqué"
        elif m["roles"]:
            m["status"] = "transmis"
    update(CONS, [], change)


def unread():
    lines = INBOX.read_text(encoding="utf-8").splitlines() if INBOX.exists() else []
    seen = int(SEEN.read_text()) if SEEN.exists() else 0
    SEEN.write_text(str(len(lines)))
    return [json.loads(l) for l in lines[seen:]]


def show(msgs):
    for m in msgs:
        print(f"📨 MESSAGE DU CLIENT n° {m['id']} [{m['t']}] au PDG : {m['text']}")
        print(f"   → à traiter : ack {m['id']} \"...\" puis dispatch {m['id']} ROLE \"...\" pour chaque rôle concerné")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0]
    if cmd == "where":
        print(ROOT)
    elif cmd == "init":
        if len(a) > 2:
            set_root(a[2])
        ROOT.mkdir(parents=True, exist_ok=True)
        if (saved := archive()):
            print(f"Mission précédente archivée : {saved}")
        shutil.copy(HOME / "qg.html", ROOT / "index.html")  # toujours la dernière version du QG
        for p in (INBOX, SEEN, CONS):
            p.unlink(missing_ok=True)
        update(LIVE, {}, lambda d: (d.clear(), d.update({"topic": a[1], "label": "En direct", "note": "", "events": []})))
        update(CONS, [], lambda d: None)
    elif cmd == "inbox":
        show(unread())
    elif cmd == "wait":
        while not (msgs := unread()):
            time.sleep(1)
        show(msgs)
    elif cmd == "hire":
        append_event({"from": "pdg", "type": "hire", "hire": {"id": a[1], "name": a[2], "like": a[3]}, "text": a[4]})
        show(unread())
    elif cmd == "ack":
        n = int(a[1])
        append_event({"from": "pdg", "to": "client", "text": a[2]})
        set_status(n, status="lu")
        show(unread())
    elif cmd == "dispatch":
        n, role = int(a[1]), a[2]
        append_event({"from": "pdg", "to": role, "text": f"Consigne n° {n} du client : {a[3]}"})
        set_status(n, role, "transmis")
        show(unread())
    elif cmd == "applied":
        n, role = int(a[1]), a[2]
        append_event({"from": role, "to": "pdg", "text": f"Consigne n° {n} appliquée : {a[3]}"})
        set_status(n, role, "appliqué")
        show(unread())
    else:
        ev = {"from": a[0], "text": a[2]}
        if a[1] != "-":
            ev["to"] = a[1].split(",") if "," in a[1] else a[1]
        if len(a) > 3 and a[3] != "-":
            ev["type"] = a[3]
        if len(a) > 4:
            ev["stage"] = a[4]
        append_event(ev)
        show(unread())
