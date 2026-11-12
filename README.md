# Bureau IA

Une mini-société de rôles (PDG, Auditeur, Bibliothécaire, Écrivain, Correcteur et spécialistes) que Claude incarne pour produire des livrables sourcés et audités. Le client suit la mission en direct dans le **QG**, un bureau isométrique animé, et dialogue avec le PDG.

## Installation

```bash
git clone https://github.com/MericV/IA_QG.git "Bureau IA"
cd "Bureau IA"
./install.sh
```

`install.sh` relie ce dossier à `~/.claude/skills/bureau` : Claude Code trouve alors le skill `/bureau` dans tous les projets. Prérequis : macOS ou Linux, Python 3.8+ (bibliothèque standard seulement), `swift` pour lire les PDF (macOS).

## Contenu

| Fichier | Rôle |
|---|---|
| `SKILL.md` | Charte du Bureau : rôles, règles de l'Auditeur, circuit, mode QG |
| `lecons.md` | Mémoire de méthode : leçons tirées des missions passées, lues au début de chaque mission et complétées à la fin |
| `briefs.md` | Modèles de brief pour les agents (recherche, contre-vérification, rédaction, critique) |
| `qg.html` | Page du QG : bureau animé, fil, questions du PDG, consignes, indicateurs, kanban, livrable |
| `qg_log.py` | Journal de mission, consignes et questions du client, livrables, export, historique |
| `qg_server.py` | Serveur local du QG (jeton secret, mises à jour instantanées) |
| `audit.py` | Contrôles automatiques de l'Auditeur |
| `pdf_text.swift` | Extraction du texte d'un PDF (macOS) |
| `test_qg_log.py` | Test du circuit complet |
| `projets/` | Données locales de chaque projet (exclues du dépôt) |

## Commandes du QG

Toujours depuis la racine du projet sur lequel le Bureau travaille (`B=~/.claude/skills/bureau`).

| Commande | Effet |
|---|---|
| `python3 $B/qg_log.py init "Sujet" [nom]` | Archive la mission précédente, démarre une mission (nom du projet : la première fois) |
| `qg_log.py stages "A\|B\|C"` | Étapes de la mission (par défaut : Cadrage, Sources, Rédaction, Forme, Audit final) |
| `qg_log.py FROM TO "texte" [type] [étape]` | Échange. `TO` = rôle, `a,b` ou `-`. `type` = `ok`, `ko`, `deliver`, `work` ou `-` |
| `qg_log.py hire ID "Nom" ROLE "raison"` | Embauche d'un renfort |
| `qg_log.py livrable FICHIER [ROLE] ["libellé"]` | Nouvelle version du livrable, avec ses changements |
| `qg_log.py ask "Question ?" "A\|B"` | Question du PDG au client, avec boutons de réponse |
| `qg_log.py ack N "…"` · `dispatch N ROLE "…"` · `applied N ROLE "…"` | Traitement du message n° N du client |
| `qg_log.py inbox` · `wait` | Messages et réponses non lus (`wait` bloque jusqu'au prochain) |
| `qg_log.py retro` | Résumé de la mission (renvois, consignes, questions) pour la rétrospective |
| `qg_log.py close N "raison"` | Clôt une question déjà réglée par un message du client |
| `qg_log.py export` | Page rejouable de la mission + historique (`missions/index.html`) |
| `qg_log.py where` | Dossier du projet et adresse du QG |
| `python3 $B/qg_server.py` | Lance le QG (premier port libre à partir de 8766) |

Rôles : `pdg aud bib ecr cor client ana str avo des ing jur cdp`, plus les renforts embauchés.

## Outils de l'Auditeur

```bash
python3 audit.py FICHIER.md --sources SOURCES.md --pages 5   # verdict validé / rejeté
python3 audit.py --selftest
swift pdf_text.swift FICHIER.pdf --pages 1-3
```

## Sécurité du QG

Le serveur n'écoute que sur `127.0.0.1`, refuse les requêtes dont l’hôte n’est pas local, ne sert qu’une liste blanche de fichiers, interdit l’affichage dans une iframe et n’accepte les messages du client qu’avec le jeton secret du projet (conservé d’un démarrage à l’autre). Un autre site ouvert dans le navigateur ne peut ni lire la mission ni écrire au PDG.

## Tests

```bash
python3 test_qg_log.py
```

## Licence

MIT, voir `LICENSE`.
