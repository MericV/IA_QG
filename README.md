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
| `vivier.md` | Vivier de rôles où le PDG recrute l'équipe de chaque mission ; il s'enrichit des rôles inventés utiles |
| `lecons.md` | Mémoire de méthode : leçons tirées des missions passées, lues au début de chaque mission et complétées à la fin |
| `briefs.md` | Modèles de brief pour les agents (recherche, contre-vérification, rédaction, critique) |
| `Bureau.command` | Double-clic : démarre le serveur si besoin et ouvre l'app dans le navigateur |
| `app.html` | L'app : barre latérale repliable, discussions, nouvelle discussion, Boîte de réception, Pilote automatique, Fonctionnalités, Modèles et comptes, intro vidéo |
| `features.json` | Fonctionnalités proposées : dépôts GitHub vérifiés qui pourraient enrichir le Bureau (le choix du client, « non » par défaut, reste dans `features-choix.json`, exclu du dépôt) |
| `qg.html` | Page du QG : un étage sur le toit d'une tour (salles vitrées, atrium, café, terrasse ; ville, jour et nuit selon l'heure), pôles et leur état, caméra (molette ou + et − pour zoomer, glisser pour se déplacer, double-clic), fil, questions du PDG, consignes, kanban, livrable |
| `qg_log.py` | Journal de mission, consignes et questions du client, livrables, export, historique |
| `qg_server.py` | Serveur local de l'app : discussions, comptes (trousseau macOS), modèles, QG en direct |
| `moteur.py` | Moteur multi-modèles : fait travailler le Bureau avec le modèle choisi (Anthropic, OpenAI, Google, Mistral, OpenRouter, Ollama, Hermes), sans Claude Code |
| `audit.py` | Contrôles automatiques de l'Auditeur |
| `pdf_text.swift` | Extraction du texte d'un PDF (macOS) |
| `test_qg_log.py` | Test du circuit complet |
| `test_moteur.py` | Test du moteur multi-modèles avec un faux modèle |
| `test_pilote.py` | Test du pilote automatique et de la boîte de réception |
| `intro/` | Vidéo d'entrée dans le building (générée par `intro/entree_building.py` avec Blender) |
| `projets/` | Données locales de chaque projet (exclues du dépôt) |

## Commandes du QG

Toujours depuis la racine du projet sur lequel le Bureau travaille (`B=~/.claude/skills/bureau`).

| Commande | Effet |
|---|---|
| `python3 $B/qg_log.py init "Sujet" [nom]` | Archive la mission précédente, démarre une mission (nom du projet : la première fois) |
| `qg_log.py stages "A\|B\|C"` | Étapes de la mission (par défaut : Cadrage, Sources, Rédaction, Forme, Audit final) |
| `qg_log.py FROM TO "texte" [type] [étape]` | Échange. `TO` = rôle, `a,b` ou `-`. `type` = `ok`, `ko`, `deliver`, `work` ou `-` |
| `qg_log.py recruit ID "Nom" "mission" "pourquoi"` | Le PDG recrute un membre (vivier ou rôle inventé) : il entre dans le bureau et l'Organigramme |
| `qg_log.py release ID "bilan"` | Le membre a terminé sa part |
| `qg_log.py livrable FICHIER [ROLE] ["libellé"]` | Nouvelle version du livrable, avec ses changements |
| `qg_log.py ask "Question ?" "A\|B"` | Question du PDG au client, avec boutons de réponse |
| `qg_log.py ack N "…"` · `dispatch N ROLE "…"` · `applied N ROLE "…"` | Traitement du message n° N du client |
| `qg_log.py inbox` · `wait` · `wait-all` | Messages non lus ; `wait` attend la discussion courante, `wait-all` toutes les discussions de l'app |
| `BUREAU_PROJET=<nom> python3 qg_log.py …` | Agit sur une discussion de l'app, quel que soit le dossier courant |
| `qg_log.py retro` | Résumé de la mission (renvois, consignes, questions) pour la rétrospective |
| `qg_log.py close N "raison"` | Clôt une question déjà réglée par un message du client |
| `qg_log.py export` | Page rejouable de la mission + historique (`missions/index.html`) |
| `qg_log.py where` | Dossier du projet et adresse du QG |
| `python3 $B/qg_server.py` | Lance le QG (premier port libre à partir de 8766) ; ou double-clic sur `Bureau.command` |

Permanents : `pdg` (PDG) et `aud` (Auditeur) ; le client est `client`. Tous les autres rôles sont recrutés avec `recruit` (identifiants du vivier comme `bib`, `ecr`, ou identifiants inventés).

## Outils de l'Auditeur

```bash
python3 audit.py FICHIER.md --sources SOURCES.md --pages 5   # verdict validé / rejeté
python3 audit.py --selftest
swift pdf_text.swift FICHIER.pdf --pages 1-3
```

## Moteur multi-modèles

Dans l'app, chaque discussion a son modèle. Avec « Claude Code », c'est la session Claude Code qui fait travailler le Bureau. Avec un autre modèle, le serveur s'en charge seul : le PDG (le modèle) répond ou pose une question, recrute 1 à 4 rôles qui travaillent en parallèle, l'Écrivain assemble le livrable, l'Auditeur le contrôle (deux corrections au plus) et le PDG le remet. Tout s'affiche dans le QG comme d'habitude.

- **Comptes :** ajoute une clé dans « Modèles et comptes » (trousseau macOS) ; la liste des modèles est lue chez le fournisseur. Ollama et Hermes n'ont pas besoin de clé ici (Hermes utilise sa propre configuration, `hermes -z`).
- **Recherche web :** avec Anthropic, le moteur active la recherche web et la réflexion adaptative ; chaque fait précis est vérifié en ligne avec son adresse. Si le compte ou le modèle les refuse, l'appel repart sans elles. Les autres fournisseurs n'ont pas de recherche web : les règles de l'Auditeur leur interdisent d'inventer et leur font marquer « à vérifier » tout fait précis non garanti.
- **Panne :** si un appel échoue, le client voit l'erreur dans le chat et son message est gardé : il est repris à son message suivant ou au redémarrage de l'app.
- **Appels :** requêtes HTTP de la bibliothèque standard de Python, sans dépendance à installer.

## Boîte de réception et pilote automatique

- **Boîte de réception** (barre latérale de l'app) : toutes discussions confondues, les décisions à prendre (réponse en un clic), ce qui est bloqué, les messages qui attendent une session Claude Code et ce qui a été livré dans la semaine. La pastille compte ce qui attend ta décision.
- **Pilote automatique** : des missions récurrentes (chaque jour, chaque semaine, toutes les N heures). À l'heure prévue, le serveur envoie la consigne au PDG dans la discussion de la tâche, créée au premier lancement puis réutilisée. Les tâches sont dans `pilote.json` (exclu du dépôt). Elles tournent tant que l'app est ouverte et le Mac éveillé ; une tâche manquée part une fois au retour de l'app. Avec « Claude Code », le message attend une session où le Bureau est activé ; avec un autre modèle, le moteur s'en charge seul.

- **Fonctionnalités** : une liste de projets libres sur GitHub (modèles, documents, recherche web, voix, mémoire, visuels, automatisation), chacun avec ce qu'il apporterait et ses points d'attention. Tout est sur « Non » au départ ; ce que tu passes à « Oui » est noté à intégrer, et l'intégration se fait ensuite avec Claude Code.

## Sécurité du QG

Le serveur n'écoute que sur `127.0.0.1`, refuse les requêtes dont l’hôte n’est pas local, ne sert qu’une liste blanche de fichiers, interdit l’affichage dans une iframe et n’accepte les messages du client qu’avec le jeton secret du projet (conservé d’un démarrage à l’autre). Un autre site ouvert dans le navigateur ne peut ni lire la mission ni écrire au PDG. Les clés d'API sont transmises au trousseau par l'entrée standard (jamais en argument, donc invisibles dans la liste des processus), et le modèle choisi pour une discussion est contrôlé.

## Tests

```bash
python3 test_qg_log.py
python3 test_moteur.py
python3 test_pilote.py
```

## Licence

MIT, voir `LICENSE`.
