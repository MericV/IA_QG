#!/bin/sh
# Relie ce dossier au skill « bureau » de Claude Code (~/.claude/skills/bureau).
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills/bureau"
mkdir -p "$HOME/.claude/skills"
if [ -L "$DEST" ]; then
  echo "Lien existant remplacé : $(readlink "$DEST") → $SRC"
  rm "$DEST"
elif [ -e "$DEST" ]; then
  echo "Erreur : $DEST existe déjà et n'est pas un lien. Déplace-le ou supprime-le, puis relance." >&2
  exit 1
fi
ln -s "$SRC" "$DEST"
echo "Skill installé : $DEST → $SRC"
command -v python3 >/dev/null || echo "Attention : python3 introuvable, le QG ne pourra pas tourner."
