# Leçons du Bureau

Mémoire de travail du Bureau : ce que les missions passées ont appris. Le PDG la lit au début de chaque mission et la complète à la fin (rétrospective). Une leçon = un fait observé et la règle qui en découle. Pas de données personnelles ni de contenu propre à un client : seulement la méthode.

Format : `- AAAA-MM-JJ · [catégorie] Règle. (Pourquoi : ce qui s'est passé.)`
Catégories : cadrage · sources · rédaction · audit · client · outils.

## Cadrage
- 2026-11-12 · [cadrage] Pour un texte personnel (motivation, candidature), demander le profil et la limite de longueur **avant** toute rédaction, et ne rien attribuer au client qu'il n'a pas confirmé. (Pourquoi : une mission est restée bloquée faute de ces informations.)
- 2026-11-12 · [cadrage] Déclarer dès le départ les vraies étapes de la mission avec `stages` (une par section ou par décision du client). (Pourquoi : les étapes génériques ne reflétaient pas le travail réel.)

- 2026-11-12 · [cadrage] Découper toute recherche à plusieurs thèmes entre plusieurs Bibliothécaires dès le départ, et demander à chaque recrue de publier son avancement en direct. (Pourquoi : le client a dû réclamer lui-même un second Bibliothécaire et l'écran restait immobile pendant les recherches.)

## Sources
- 2026-11-06 · [sources] Faire relire à la source un échantillon des faits rapportés par un agent, surtout les chiffres. (Pourquoi : deux sources officielles donnaient le même chiffre avec un libellé différent ; l'écart n'est apparu qu'à la relecture.)
- 2026-11-06 · [sources] Un PDF que l'outil web ne sait pas lire se lit avec `pdf_text.swift`. Ne jamais déduire le contenu d'un PDF illisible. (Pourquoi : deux communiqués n'étaient lisibles qu'après extraction locale.)
- 2026-11-12 · [sources] Présenter un atout du client (diplôme, brevet) tel que les sources officielles le décrivent, sans en exagérer la portée. (Pourquoi : un brevet présenté comme un atout n'était, d'après les sources officielles, qu'une preuve d'intérêt.)

## Rédaction
- 2026-11-12 · [rédaction] Quand le Correcteur et un relecteur de fond travaillent en parallèle, le PDG fusionne leurs remarques et écarte toute « clarification » qui ajoute un fait absent des sources. (Pourquoi : la relecture de forme proposait « très souple », « sans reste à charge » et une définition de la greffe, absents des sources.)
- 2026-11-12 · [rédaction] Prévoir une marge de longueur au premier jet (viser le bas de la fourchette) : les relectures ajoutent des nuances obligatoires. (Pourquoi : les corrections de fond ont fait passer la fiche de 2,3 à 2,7 pages et il a fallu resserrer.)
- 2026-11-06 · [rédaction] Vérifier la longueur avec `audit.py --pages N` avant de rendre. (Pourquoi : un premier jet faisait 7,5 pages pour 5 autorisées.)

## Audit
- 2026-11-12 · [audit] Attribuer chaque fait à la source qui le contient vraiment, même une définition. (Pourquoi : un délai de pose de la couronne était cité d'après une source qui ne le donnait pas.)
- 2026-11-06 · [audit] Un chiffre trouvé par un comptage de l'équipe est un `[EST]` avec sa méthode, jamais un chiffre publié. (Pourquoi : un comptage fait sur des données ouvertes avait failli passer pour une statistique publiée.)

## Client
- 2026-11-12 · [client] Quand un message du client règle une question ouverte, la clore avec `close` au lieu de la laisser en attente. (Pourquoi : une question de longueur restait affichée alors que le client avait déjà répondu « 500 caractères ».)
- 2026-11-12 · [client] Dans le QG, répondre au client par des messages courts au PDG (`pdg client`) : ce qui avance, ce qu'on attend de lui. (Pourquoi : le client veut une vraie conversation, pas un journal technique.)
- 2026-11-12 · [client] Avant de clore une mission, même arrêtée, faire passer chaque consigne du client à « appliqué » ou expliquer pourquoi elle ne l'est pas. (Pourquoi : la rétrospective a trouvé deux consignes restées « transmis » sans suite.)
- 2026-11-12 · [client] Ne jamais reprendre les coordonnées personnelles du client (téléphone, e-mail) dans un livrable sauf demande explicite. (Pourquoi : un document du client contenant ses coordonnées avait été collé dans le chat.)

## Outils
- 2026-11-12 · [outils] Un message long (CV, document) peut dépasser la limite du chat ; si un texte du client semble coupé, le lui dire tout de suite. (Pourquoi : un document a été tronqué à 1 000 caractères, limite depuis relevée à 4 000.)
