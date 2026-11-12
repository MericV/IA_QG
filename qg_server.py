"""Serveur local de l'app « QG du Bureau ».

Usage : python3 ~/.claude/skills/bureau/qg_server.py [port_de_départ]
Prend le premier port libre à partir de 8766, l'écrit dans <dossier du Bureau>/.port et affiche l'adresse.
Lancé depuis la racine d'un projet, l'adresse ouvre directement la discussion de ce projet.

Pages
  GET  /                         l'app : barre latérale, discussions, modèles et comptes, intro
  GET  /d/<discussion>/          le QG d'une discussion (bureau, rendu, conversation avec le PDG)
  GET  /intro/<fichier>          la vidéo d'entrée dans le building
API (écritures : jeton secret + origine locale)
  GET  /api/discussions          liste des discussions (sujet, statut, modèle, dernière activité)
  POST /api/discussions          {"text", "model"?}  nouvelle discussion ; le texte devient le premier message au PDG
  GET  /api/providers            fournisseurs de modèles et état des comptes (jamais les clés)
  POST /api/accounts             {"provider", "key"}  enregistre une clé dans le trousseau macOS
  POST /api/accounts/remove      {"provider"}         la retire
  GET  /d/<d>/state · /d/<d>/events (SSE) · /d/<d>/livrables/… · /d/<d>/missions/…
  POST /d/<d>/say · /d/<d>/answer · /d/<d>/model {"provider", "model"} · /d/<d>/dismiss {"id", "reason"?}

Sécurité : écoute seulement sur 127.0.0.1 ; refuse tout en-tête Host non local (rebinding DNS) ; ne sert
qu'une liste blanche de fichiers ; affichage en iframe limité à l'app elle-même ; écritures avec le jeton
secret (stable, conservé dans .token) et une origine locale. Les clés d'API vont dans le trousseau macOS
(service « bureau-ia ») et ne sont jamais renvoyées par le serveur.
"""
import functools, http.server, json, mimetypes, os, re, secrets, shutil, signal, subprocess, sys, threading, time, pathlib
from urllib.parse import urlsplit, parse_qs, unquote

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import qg_log  # noqa: E402
import moteur  # noqa: E402

HOME = qg_log.HOME
TOKEN = None  # fixé au démarrage par serve()
LOCK = moteur.LOCK  # qg_log travaille sur une discussion à la fois : une requête (ou une étape du moteur) à la fois
MODELS = {}  # modèles lus chez chaque fournisseur connecté, une fois par lancement
KEYCHAIN = "bureau-ia"

# Fournisseurs de modèles. Les modèles précis de chaque fournisseur seront lus chez lui une fois le compte ajouté.
PROVIDERS = [
    {"id": "claude-code", "name": "Claude Code", "kind": "moteur", "models": ["Claude Code (moteur actuel)"],
     "help": "Le moteur actuel : la session Claude Code qui a lancé le QG fait travailler le Bureau."},
    {"id": "anthropic", "name": "Anthropic (Claude)", "kind": "key", "models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"],
     "help": "Clé d'API sur console.anthropic.com (sk-ant-…)."},
    {"id": "openai", "name": "OpenAI (GPT)", "kind": "key", "models": [], "help": "Clé d'API sur platform.openai.com (sk-…)."},
    {"id": "google", "name": "Google (Gemini)", "kind": "key", "models": [], "help": "Clé d'API sur aistudio.google.com."},
    {"id": "mistral", "name": "Mistral", "kind": "key", "models": [], "help": "Clé d'API sur console.mistral.ai."},
    {"id": "openrouter", "name": "OpenRouter", "kind": "key", "models": [], "help": "Une seule clé pour des centaines de modèles (openrouter.ai)."},
    {"id": "ollama", "name": "Ollama (modèles locaux)", "kind": "local", "models": [], "help": "Modèles qui tournent sur ton Mac, sans clé. À installer depuis ollama.com."},
    {"id": "hermes", "name": "Hermes Agent", "kind": "local", "models": [], "help": "Agent de Nous Research. Installation : bash ~/Documents/hermes-install/install.sh --skip-computer-use"},
]


def has_key(provider):
    return subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN, "-a", provider],
                          capture_output=True).returncode == 0


def providers():
    out = []
    for p in PROVIDERS:
        p = dict(p)
        if p["kind"] == "key":
            p["status"] = "connecté" if has_key(p["id"]) else "à connecter"
            if p["status"] == "connecté":
                if p["id"] not in MODELS:
                    try:
                        MODELS[p["id"]] = moteur.list_models(p["id"])
                    except moteur.MoteurErreur:
                        MODELS[p["id"]] = []  # liste illisible (clé refusée, hors ligne) : on garde la liste par défaut
                p["models"] = MODELS[p["id"]] or p["models"]
        elif p["id"] == "claude-code":
            p["status"] = "actif"
        elif p["id"] == "ollama":
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1) as r:
                    p["models"] = [m["name"] for m in json.load(r).get("models", [])]
                p["status"] = "détecté"
            except OSError:
                p["status"] = "non installé"
        elif p["id"] == "hermes":
            p["status"] = "détecté" if shutil.which("hermes") else "non installé"
            p["models"] = [moteur.HERMES_DEFAULT] if p["status"] == "détecté" else []
        out.append(p)
    return out


def discussions():
    items = []
    for live in (qg_log.DATA / "projets").glob("*/qg-live.json"):
        try:
            d = json.loads(live.read_text(encoding="utf-8"))
        except ValueError:
            continue
        ev = d.get("events", [])
        items.append({"id": live.parent.name, "topic": d.get("topic") or live.parent.name, "updated": live.stat().st_mtime,
                      "events": len(ev), "done": any(e.get("type") == "deliver" for e in ev),
                      "model": d.get("model", qg_log.DEFAULT_MODEL)})
    return sorted(items, key=lambda x: -x["updated"])


def stamp(root):
    """Empreinte des fichiers d'une discussion : change dès qu'un échange, une consigne ou un livrable arrive."""
    files = [root / "qg-live.json", root / "consignes.json", root / "questions.json", root / "livrables" / "index.json"]
    return tuple(f.stat().st_mtime_ns if f.exists() else 0 for f in files)


def inside(base, rel):
    """Fichier rel à l'intérieur de base, sans fichier caché ni sortie du dossier ; None sinon."""
    if any(part.startswith(".") for part in rel.split("/")):
        return None
    target = (base / rel).resolve()
    if base.resolve() not in target.parents and target != base.resolve():
        return None
    if target.is_dir():
        target = target / "index.html"
    return target if target.is_file() else None


class Handler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        # L'app affiche le QG dans une iframe : autorisé pour elle seule, jamais pour un autre site.
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_HEAD(self):
        self.send_error(405)

    def local(self):
        port = self.server.server_address[1]
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or urlsplit(origin).netloc in hosts)

    def send_body(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, code=200):
        self.send_body(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def send_page(self, path):
        self.send_body(path.read_text(encoding="utf-8").replace("__QG_TOKEN__", TOKEN).encode(), "text/html; charset=utf-8")

    def send_file(self, path):
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        self.send_body(path.read_bytes(), ctype)

    def discussion(self, path):
        """(nom, reste du chemin) pour /d/<nom>/…, sinon None."""
        m = re.fullmatch(r"/d/([^/]+)(/.*)?", path)
        if not m or not qg_log.PROJECT_NAME.fullmatch(m.group(1)) or ".." in m.group(1):
            return None
        return m.group(1), m.group(2)

    def do_GET(self):
        if not self.local():
            return self.send_error(403)
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path in ("/", "/index.html"):
            return self.send_page(HOME / "app.html")
        if path.startswith("/intro/"):
            f = inside(HOME / "intro", path[len("/intro/"):])
            return self.send_file(f) if f and f.suffix in (".mp4", ".webm", ".jpg", ".png") else self.send_error(404)
        if path == "/api/discussions":
            return self.send_json(discussions())
        if path == "/api/providers":
            return self.send_json(providers())
        d = self.discussion(path)
        if not d:
            return self.send_error(404)
        name, rest = d
        if rest is None:
            self.send_response(301)
            self.send_header("Location", f"/d/{name}/")
            return self.end_headers()
        with LOCK:
            qg_log.use_project(name)
            root = qg_log.ROOT
            if not qg_log.LIVE.exists():
                return self.send_error(404)
            if rest in ("/", "/index.html"):
                return self.send_page(HOME / "qg.html")
            if rest == "/state":
                return self.send_json(qg_log.state())
        if rest == "/events":
            if parse_qs(url.query).get("token") != [TOKEN]:
                return self.send_error(403)
            return self.stream(root)
        if rest.startswith("/livrables/") and not rest.endswith("/index.json") or rest.startswith("/missions/"):
            f = inside(root, rest.lstrip("/"))
            return self.send_file(f) if f else self.send_error(404)
        return self.send_error(404)

    def stream(self, root):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last, beat = None, time.time()
        try:
            while True:
                cur = stamp(root)
                if cur != last:
                    self.wfile.write(b"data: change\n\n")
                    self.wfile.flush()
                    last, beat = cur, time.time()
                elif time.time() - beat > 10:
                    # signe de vie visible par la page : sans lui, elle reconnecte (connexion morte en silence)
                    self.wfile.write(b"event: ping\ndata: \n\n")
                    self.wfile.flush()
                    beat = time.time()
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.local() or self.headers.get("X-QG-Token") != TOKEN:
            return self.send_error(403)
        path = unquote(urlsplit(self.path).path)
        try:
            msg = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 32000)) or b"{}")
            if path == "/api/discussions":
                return self.new_discussion(msg)
            if path == "/api/accounts":
                return self.add_account(msg)
            if path == "/api/accounts/remove":
                provider = str(msg.get("provider", ""))
                subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN, "-a", provider], capture_output=True)
                return self.send_json({"ok": True})
            d = self.discussion(path)
            if not d or not d[1]:
                return self.send_error(404)
            name, rest = d
            with LOCK:
                qg_log.use_project(name)
                if rest == "/say":
                    text = str(msg.get("text", "")).strip()[:4000]
                    if not text:
                        return self.send_error(400)
                    qg_log.new_message(text)
                elif rest == "/answer":
                    if not qg_log.answer(int(msg["id"]), str(msg["choice"]), bool(msg.get("other"))):
                        return self.send_json({"erreur": "question déjà réglée ou choix invalide"}, 409)
                elif rest == "/dismiss":
                    qg_log.dismiss(str(msg["id"]), str(msg.get("reason") or "décision du client")[:300], by_client=True)
                elif rest == "/model":
                    model = {"provider": str(msg["provider"])[:40], "model": str(msg["model"])[:120]}
                    if model["provider"] not in {p["id"] for p in PROVIDERS}:
                        return self.send_error(400)
                    qg_log.require_mission()
                    qg_log.update(qg_log.LIVE, {}, lambda data: data.__setitem__("model", model))
                else:
                    return self.send_error(404)
        except (ValueError, KeyError, AttributeError, TypeError):
            return self.send_error(400)
        except qg_log.Erreur as e:
            return self.send_json({"erreur": str(e)}, 409)
        if rest in ("/say", "/answer", "/dismiss", "/model"):
            moteur.kick(name)  # discussion confiée à un autre modèle : le moteur multi-modèles s'en charge
        self.send_response(204)
        self.end_headers()

    def new_discussion(self, msg):
        text = str(msg.get("text", "")).strip()[:4000]
        if not text:
            return self.send_error(400)
        model = msg.get("model") if isinstance(msg.get("model"), dict) else None
        name = (qg_log.slug(text)[:40].strip("-") or "discussion") + "-" + os.urandom(2).hex()
        topic = text if len(text) <= 80 else text[:77].rsplit(" ", 1)[0] + "…"
        with LOCK:
            qg_log.use_project(name)
            qg_log.ROOT.mkdir(parents=True, exist_ok=True)
            qg_log.update(qg_log.LIVE, {}, lambda d: (d.clear(), d.update(qg_log.new_mission(topic, model))))
            qg_log.write_history()
            qg_log.new_message(text)
        moteur.kick(name)
        return self.send_json({"id": name}, 201)

    def add_account(self, msg):
        provider, key = str(msg.get("provider", "")), str(msg.get("key", "")).strip()
        if provider not in {p["id"] for p in PROVIDERS if p["kind"] == "key"} or not 10 <= len(key) <= 400 or any(c.isspace() for c in key):
            return self.send_json({"erreur": "fournisseur inconnu ou clé invalide"}, 400)
        r = subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN, "-a", provider, "-w", key], capture_output=True)
        return self.send_json({"ok": r.returncode == 0}, 200 if r.returncode == 0 else 500)

    def log_message(self, *a):
        pass


def project_token():
    """Jeton secret de l'app, conservé dans un fichier caché (jamais servi) pour survivre aux redémarrages."""
    f = qg_log.DATA / ".token"
    if not f.exists():
        qg_log.DATA.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(24))
        f.chmod(0o600)
    return f.read_text().strip()


def serve(start=8766):
    global TOKEN
    current = qg_log.ROOT.name if qg_log.LIVE.exists() else ""
    TOKEN = project_token()
    # kill (SIGTERM) passe par le même chemin que Ctrl+C : le fichier .port est bien supprimé
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    for port in range(start, start + 50):
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    else:
        sys.exit(f"Erreur : aucun port libre entre {start} et {start + 49}")
    server.daemon_threads = True
    portfile = qg_log.DATA / ".port"
    portfile.write_text(str(port))
    for live in (qg_log.DATA / "projets").glob("*/qg-live.json"):  # messages arrivés pendant l'arrêt du serveur
        moteur.kick(live.parent.name)
    print(f"QG : http://127.0.0.1:{port}/" + (f"#{current}" if current else ""), flush=True)
    try:
        server.serve_forever()
    finally:
        portfile.unlink(missing_ok=True)


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8766)
