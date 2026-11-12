"""Serveur local du QG en direct.

Usage (depuis la racine du projet) : python3 ~/.claude/skills/bureau/qg_server.py [port_de_départ]
Prend le premier port libre à partir de 8766, l'écrit dans <projet>/.port et affiche l'adresse du QG.

Sécurité : écoute seulement sur 127.0.0.1 (adresse affichée en 127.0.0.1, pas « localhost » qui peut
viser ::1) ; refuse toute requête dont l'en-tête Host n'est pas localhost/127.0.0.1 (rebinding DNS) ;
ne sert qu'une liste blanche de chemins (la page, l'état, les livrables, l'historique) ; interdit
l'affichage dans une iframe ; les écritures exigent le jeton secret du projet (stable d'un démarrage
à l'autre, pour qu'une page ouverte se reconnecte) et une origine locale.

GET  /            page du QG (avec le jeton)
GET  /state       état complet de la mission (JSON)
GET  /events      flux SSE : un signal à chaque changement (mises à jour instantanées)
POST /say         {"text"}           message du client au PDG
POST /answer      {"id", "choice", "other"?}   réponse du client (choix proposé ou réponse libre)
"""
import functools, http.server, json, secrets, signal, sys, time, pathlib
from urllib.parse import urlsplit, parse_qs, unquote

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import qg_log  # noqa: E402


TOKEN = None  # fixé au démarrage par serve()


def project_token():
    """Jeton secret du projet, conservé dans un fichier caché (jamais servi) pour survivre aux redémarrages."""
    f = qg_log.ROOT / ".token"
    if not f.exists():
        qg_log.ROOT.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(24))
        f.chmod(0o600)
    return f.read_text().strip()


def allowed(path):
    """Liste blanche des chemins servis, après décodage (%2E…) : aucun fichier interne du projet."""
    parts = path.split("/")
    if any(p.startswith(".") for p in parts):
        return False
    if path.startswith("/livrables/"):
        return len(parts) == 3 and parts[2] != "index.json"
    return path.startswith("/missions/")


def stamp():
    """Empreinte des fichiers de la mission : change dès qu'un échange, une consigne ou un livrable arrive."""
    files = [qg_log.LIVE, qg_log.CONS, qg_log.QUEST, qg_log.LIVR / "index.json"]
    return tuple(f.stat().st_mtime_ns if f.exists() else 0 for f in files)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_HEAD(self):
        self.send_error(405)

    def local(self):
        port = self.server.server_address[1]
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or urlsplit(origin).netloc in hosts)

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.local():
            return self.send_error(403)
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path in ("/", "/index.html"):
            page = (qg_log.ROOT / "index.html").read_text(encoding="utf-8").replace("__QG_TOKEN__", TOKEN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            return self.wfile.write(page)
        if path == "/state":
            return self.send_json(qg_log.state())
        if path == "/events":
            if parse_qs(url.query).get("token") != [TOKEN]:
                return self.send_error(403)
            return self.stream()
        if not allowed(path):
            return self.send_error(404)
        return super().do_GET()

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last, beat = None, time.time()
        try:
            while True:
                cur = stamp()
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
        try:
            msg = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 32000)))
            if self.path == "/say":
                text = str(msg.get("text", "")).strip()[:4000]
                if not text:
                    return self.send_error(400)
                qg_log.new_message(text)
            elif self.path == "/answer":
                if not qg_log.answer(int(msg["id"]), str(msg["choice"]), bool(msg.get("other"))):
                    return self.send_json({"erreur": "question déjà répondue ou choix invalide"}, 409)
            else:
                return self.send_error(404)
        except (ValueError, KeyError, AttributeError, TypeError):
            return self.send_error(400)
        except qg_log.Erreur as e:
            return self.send_json({"erreur": str(e)}, 409)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


def serve(start=8766):
    global TOKEN
    if not (qg_log.ROOT / "index.html").exists():
        sys.exit('Erreur : aucun QG pour ce projet. Lance d\'abord  python3 qg_log.py init "Sujet" nom-du-projet')
    TOKEN = project_token()
    # kill (SIGTERM) passe par le même chemin que Ctrl+C : le fichier .port est bien supprimé
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    handler = functools.partial(Handler, directory=str(qg_log.ROOT))
    for port in range(start, start + 50):
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            continue
    else:
        sys.exit(f"Erreur : aucun port libre entre {start} et {start + 49}")
    server.daemon_threads = True
    (qg_log.ROOT / ".port").write_text(str(port))
    print(f"QG : http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    finally:
        (qg_log.ROOT / ".port").unlink(missing_ok=True)


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8766)
