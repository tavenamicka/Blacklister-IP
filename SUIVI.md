# SUIVI.md — Avancement du projet Blacklister IP

> Journal des changements notables. Voir aussi `README.md` (utilisation) et `CONTEXT.md`/`INFRASTRUCTURE.md`
> du homelab pour le contexte plus large (CI/CD, conventions Gitea).

---

Mise à jour : 2026-11-06 (**Page « À propos » (version/date de build/auteur)**, commit `6371a7f`.
Tag `v1.0.0` créé sur le commit précédent (`635df72`) — première version taguée du projet.
- Barre d'état en bas de la fenêtre principale, visible sur tous les onglets : version cliquable
  (`app/ui/main_window.py`), ouvrant la fenêtre **À propos** (`app/ui/about_dialog.py`) — nom,
  version, date de build, auteur, contact, copyright.
- `app/app_info.py` : version = `git describe --tags --always --dirty` (`vX.Y.Z` propre sur un tag,
  `-dirty` si modifs non commitées, `-N-g<hash>` si N commits après le tag). Lue depuis
  `app/_build_info.py` quand il existe (généré par `build.ps1` avant l'appel à PyInstaller, figé au
  moment du build, embarqué par PyInstaller comme un module normal — gitignored, pas de
  `--add-data` nécessaire) ; sinon (dev, `python app/main.py` sans build) recalculée à la volée
  depuis git, date de build affichée comme « non buildé (mode développement) ».
- `build.ps1 -Clean` supprime aussi `app/_build_info.py` en plus de `build/`/`dist/`/`__pycache__`.

Vérifié : suite pytest (76/76, `_build_info` simulé via `sys.modules` pour couvrir les deux modes
sans dépendre d'un vrai build), lancement réel en dev (`dev` affiché sans tag/`.git` accessible,
`vX.Y.Z-dirty`/`-N-g<hash>` corrects avec le vrai dépôt), build réel (`./build.ps1` régénère
`_build_info.py` avec la version/date figées, exe relancé sans exception). `ruff check` propre.)

Mise à jour : 2026-11-06 (**Registre de pare-feu physiques (multi-pôle/site) + accès SSH**, commit
`635df72`. Besoin métier : plusieurs pare-feu dans plusieurs pôles (ex. Paris/Bordeaux) avec des
conventions de nommage et des accès SSH propres à chacun (pas d'API possible sur ces équipements) —
voir aussi `README.md`.
- Nouvel onglet **Pare-feu** : registre `devices` (migration schéma **v3→v4**) — site/pôle, nom,
  marque, host, port SSH, préfixes objets/groupe propres, vsys Palo Alto (stocké en JSON dans
  `extra_options`). CRUD complet (`app/db.py`, `app/ui/devices_tab.py`).
- Onglet **Cas** : la génération cible désormais des **devices précis** (cases à cocher groupées
  par marque) plutôt qu'une simple marque — un device coché utilise ses préfixes/vsys propres ; si
  aucun device n'est coché pour une marque, le mode générique historique reste disponible (bascule
  d'onglet "Pare-feu"→"Cas" recharge le registre, cf. `MainWindow._on_tab_changed`).
- Dédup/historique scopés **par device** et non plus seulement par marque (migration **v4→v5**,
  `entries.device_id`, index actif `COALESCE(device_id, -1)`) : bloquer une IP à Paris n'empêche
  plus de la bloquer à Bordeaux sur un pare-feu de même marque. Historique et export CSV affichent
  le pôle/device de chaque entrée.
- SSH (`app/ssh_client.py`, `app/ui/ssh_dialogs.py`) : **aucun identifiant stocké** — login/mot de
  passe ressaisis à chaque connexion (seul le login est retenu en mémoire pour la durée de la
  session, jamais écrit sur disque). Deux modes : "Terminal SSH" (lance un terminal local déjà
  pointé host/port/login, mot de passe tapé par l'opérateur — ni vu ni stocké par l'appli) et
  "Envoyer via SSH" (écran de confirmation montrant le device cible et les commandes exactes avant
  tout envoi, puis push via un canal shell interactif `paramiko` et affichage de la sortie brute du
  pare-feu — pas d'interprétation automatique du résultat, à l'opérateur de vérifier). Nouvelle
  dépendance `paramiko` (`requirements.txt`).

Vérifié à trois niveaux : suite pytest (71/71, paramiko/subprocess mockés pour `ssh_client` et le
push SSH — aucune vraie connexion réseau dans les tests), lancement réel de l'app (pas d'exception
dans `app.log`), et scénarios de bout en bout pilotant les vrais widgets CustomTkinter (création
d'un device → bascule d'onglet → génération ciblant ce device → sauvegarde → historique montrant le
pôle ; dialogue SSH avec push mocké). `ruff check` propre sur tous les fichiers touchés.)

Mise à jour : 2026-09-11 (**CI/CD (Gitea Actions) mis en place**, commit `b3dc4f4` — job unique `test`
(Python 3.12, `pip install -r requirements-dev.txt` puis `pytest -q`), même convention que les autres
dépôts Python du homelab (cf. `INFRASTRUCTURE.md` §13). Pas de job de build de l'exécutable portable :
`pyinstaller --windowed` produit un binaire Windows, hors de portée du runner Gitea Actions (conteneurs
Linux uniquement) — seule la suite de tests tourne en CI, le build reste manuel (`./build.ps1`). Premier
run vérifié vert (`status: success`, ~17 s) via l'API Gitea (token temporaire généré/supprimé en SSH sur
le ThinkStation, procédure documentée en `INFRASTRUCTURE.md` §13).)

Mise à jour précédente : 2026-09-11 (**Premier commit et dépôt Gitea créé** — le projet existait en local
sans être versionné (dossier ignoré par le `.gitignore` du dépôt parent `infra-docs`). Initialisé en dépôt
Git indépendant, rattaché à `http://192.168.1.23:3001/mickatch/Blacklister_IP` (créé vide côté serveur,
alias SSH `gitea-dev`), commit racine `54cb350` — tout le projet existant (app, tests, `ancienne_methode/`)
plus la fonctionnalité ci-dessous, développée juste avant ce premier commit.)

Mise à jour précédente : 2026-09-11 (**Préfixe de groupe distinct du préfixe des objets, par cas** —
jusqu'ici un seul champ « Préfixe des objets/groupe » servait à la fois aux objets réseau individuels
(`set address ...`) et au nom du groupe (`address-group`/`addrgrp`/`object-group`), toujours identiques.
Ajout d'un second champ optionnel dans le dialogue **Cas**, auto-rempli depuis le préfixe des objets tant
qu'il n'est pas modifié à la main (même logique que l'auto-remplissage nom→préfixe déjà en place) :
- `app/db.py` : colonne `cases.group_prefix` (migration schéma **v2→v3**, backfill = `prefix` pour les
  cas déjà créés — comportement inchangé par défaut), `create_case`/`update_case` acceptent un
  `group_prefix` optionnel.
- `app/blocker.py` : le nom de groupe généré utilise désormais `case.group_prefix` au lieu de
  `case.prefix`.
- `app/ui/case_tab.py` : nouveau champ dans `CaseDialog`, logique de non-écrasement si modifié
  manuellement (édition d'un cas existant comme saisie d'un nouveau cas).

Vérifié à trois niveaux : suite pytest (34/34, nouveaux cas de test db/blocker/migration), lancement réel
de l'app (migration de la base de dev existante v2→v3 sans erreur), et pilotage des vrais widgets
`CaseDialog` (CustomTkinter réel, pas de mock) sur une base temporaire isolée — auto-remplissage,
préservation d'un préfixe de groupe modifié à la main après retouche du nom, pré-remplissage correct à
l'édition d'un cas existant, génération Palo Alto confirmant l'usage du bon préfixe pour chaque élément.)
