"""Serveur local du QG en direct : sert le dossier qg/ et reçoit les messages du client au PDG.

Usage (depuis la racine du projet) : python3 ~/.claude/skills/bureau/qg_server.py [port]
POST /say {"text": "..."} : enregistre le message (consignes.json, inbox.jsonl) et l'ajoute au journal.
"""
import functools, http.server, json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qg_log import ROOT, new_message  # noqa: E402


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/say":
            return self.send_error(404)
        try:
            msg = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 8000)))
            text = str(msg.get("text", "")).strip()[:1000]
        except (ValueError, AttributeError):
            return self.send_error(400)
        if not text:
            return self.send_error(400)
        new_message(text)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=str(ROOT))).serve_forever()
