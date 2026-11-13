#!/bin/sh
# Double-clic : ouvre l'app du Bureau dans le navigateur, en démarrant le serveur s'il ne tourne pas déjà.
# Les discussions confiées à un modèle (Anthropic, OpenAI…) travaillent seules ; celles sur « Claude Code »
# attendent une session Claude Code qui lance le skill « bureau ».
cd "$(dirname "$0")" || exit 1
PORT=$(cat .port 2>/dev/null)
if [ -n "$PORT" ] && curl -s -o /dev/null "http://127.0.0.1:$PORT/api/discussions"; then
  open "http://127.0.0.1:$PORT/"
  exit 0
fi
python3 qg_server.py > /tmp/bureau-qg.log 2>&1 &
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 0.5
  URL=$(grep -o 'http://127.0.0.1:[0-9]*/' /tmp/bureau-qg.log | head -1)
  [ -n "$URL" ] && open "$URL" && echo "Bureau ouvert : $URL (ferme cette fenêtre pour arrêter le serveur)" && wait && exit 0
done
echo "Le serveur n'a pas démarré :" && cat /tmp/bureau-qg.log && exit 1
