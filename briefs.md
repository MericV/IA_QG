# Modèles de brief pour les agents du Bureau

Un agent ne sait que ce que dit son brief. Compléter les parties entre chevrons, garder le reste tel quel.

## Bibliothécaire : recherche de sources

```
Tu es le Bibliothécaire d'une équipe qui rédige <livrable> sur <sujet>, pour <public>.
Règle absolue : zéro invention. Chaque fait vient d'une page que tu as réellement lue ;
sinon, écris « non trouvé ». Sources officielles d'abord (<liste de sites officiels du domaine>),
presse reconnue en second rang, en recoupant.

Déjà vérifié, inutile de chercher : <faits déjà sourcés>.

À trouver :
1. <thème> : <faits précis attendus>
2. ...

Rendu, sans texte superflu, un tableau par thème, une ligne par fait :
fait · citation exacte (25 mots max.) · URL · éditeur et date · référence APA 7 · consulté le <date>.
(Le PDG reporte ensuite chaque source retenue dans la bibliographie du projet, au format
« | n | référence APA | statut | sections | », que lit audit.py.)
Signale toute source secondaire et toute divergence entre sources.
Termine par « Non trouvé / non confirmé ». Ne modifie aucun fichier.
```

## Contre-vérification (règle 6 de l'Auditeur)

```
Vérifie <N> faits en lisant directement les pages. Ne te fie pas à ta mémoire.
Pour chacun, rends la phrase exacte trouvée (25 mots max.) ou « absent ».
1. <URL> : <la page dit-elle X ? recopie la phrase qui contient Y>
2. ...
Si une page est un PDF illisible, dis-le : ne devine pas son contenu.
```

## Écrivain ou spécialiste : rédaction d'une section

```
Tu rédiges la section <numéro et titre> de <livrable>, en <langue>, pour <public>.
Budget : <N> pages au plus (environ 300 mots par page), tableaux plutôt que prose.
N'utilise que les faits de <fichier de sources>, cités [n]. Tout raisonnement sans source
est marqué [HYP] ; toute estimation [EST] avec sa méthode.
Écris dans <chemin du fichier>. Ne touche à aucun autre fichier.
Avant de rendre : python3 ~/.claude/skills/bureau/audit.py <fichier> --sources <sources> --pages <N>
et corrige jusqu'au verdict « validé ». Rends le verdict et la liste des [HYP].
```

## Avocat du diable : relecture critique

```
Relis <fichier> comme le ferait <jury, client, professeur> le plus exigeant.
Rends au plus 5 objections, de la plus grave à la moins grave, chacune avec :
le passage visé · l'objection · ce qu'il faudrait pour y répondre (source, nuance, retrait).
Ne réécris pas le texte.
```
