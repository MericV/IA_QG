# Bureau IA

Une mini-société de rôles (PDG, Auditeur, Bibliothécaire, Écrivain, Correcteur et spécialistes) que Claude incarne pour produire des livrables sourcés et audités. Elle se suit en direct dans le **QG**, un bureau isométrique animé.

## Contenu

| Fichier | Rôle |
|---|---|
| `SKILL.md` | Charte du Bureau : rôles, règles de l'Auditeur, embauches, circuit des consignes |
| `qg.html` | Page du QG : bureau animé, fil des échanges, tableau de mission, chat avec le PDG |
| `qg_log.py` | Journal des échanges, consignes du client, archivage des missions |
| `qg_server.py` | Serveur local du QG en direct (port 8766) |
| `projets/<nom>/` | QG en direct de chaque projet |
| `projets/<nom>/missions/` | Missions terminées, rejouables |

Claude trouve le skill via le lien `~/.claude/skills/bureau` → ce dossier.

## Lancer un QG en direct

Depuis la racine du projet sur lequel le Bureau travaille :

```bash
python3 ~/.claude/skills/bureau/qg_log.py init "Sujet de la mission" nom-du-projet
python3 ~/.claude/skills/bureau/qg_server.py 8766
```

Puis ouvrir http://localhost:8766/.
