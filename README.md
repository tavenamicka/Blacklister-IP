# Blacklister IP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Application Windows portable pour générer les commandes CLI de blocage d'IP/FQDN sur Palo Alto, Fortinet et Cisco ASA, avec historique local et détection de doublons.

## À quoi ça sert

En réponse à incident, bloquer une IP malveillante veut souvent dire l'écrire à la main sur plusieurs pare-feu — chacun avec sa propre syntaxe (Palo Alto ≠ Fortinet ≠ Cisco ASA). C'est lent et source d'erreurs (CIDR mal formé, doublon entre deux cas...).

Blacklister IP automatise ça : on colle une liste d'IP/CIDR/FQDN, on coche les pare-feu cibles, l'appli génère les commandes prêtes à coller, valide les entrées et détecte les doublons. Les blocages sont organisés par **cas** (ex. un client ou un incident), avec un historique local consultable et exportable en CSV.

Pour qui gère plusieurs pare-feu répartis sur plusieurs pôles/sites (ex. Paris, Bordeaux), un registre dédié (**onglet Pare-feu**) retient quel pare-feu appartient à quel pôle, avec ses préfixes propres et son accès SSH — ces équipements n'exposant pas d'API, l'appli ouvre un terminal SSH pré-rempli ou pousse directement les commandes générées (login/mot de passe jamais stockés, ressaisis à chaque connexion).

Portable (un `.exe` + un dossier `data/`), aucune installation requise.

## Utilisation (développement)

```bash
pip install -r requirements.txt
python app/main.py
```

1. Onglet **Pare-feu** (optionnel mais recommandé si plusieurs sites) : enregistrer chaque pare-feu physique — pôle/site, nom, marque, host + port SSH, préfixes propres et, pour Palo Alto, le vsys.
2. Onglet **Cas** : créer ou sélectionner un cas (ex: "iTrust"), cocher les pare-feu cibles. Si des devices sont enregistrés pour une marque, cocher le(s) device(s) précis à cibler (ex: le Palo Alto de Paris ET celui de Bordeaux séparément) ; sans device coché, génération générique pour la marque (comportement historique).
3. Coller une liste d'IP/CIDR/FQDN (une par ligne), cliquer **Générer**, vérifier les commandes, les doublons (dans le cas/device ou ailleurs) et les valeurs invalides.
4. **Copier**, **Exporter .txt**, ou — pour un résultat ciblant un device — **Terminal SSH** (ouvre un terminal local déjà pointé sur ce device) ou **Envoyer via SSH** (écran de confirmation puis envoi direct des commandes). Puis **Enregistrer** pour les ajouter à l'historique.
5. Onglet **Historique** : rechercher/filtrer toutes les entrées bloquées (pôle/device inclus), exporter en CSV.

## Build de l'exécutable portable

```powershell
./build.ps1
```

Génère `dist/BlacklisterIP.exe`. Un dossier `data/` (base SQLite + `app.log`) est créé à côté de l'exe au premier lancement — copier l'exe + son dossier `data/` suffit à déplacer l'appli sur un autre poste, sans installation.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

Couvre la validation (`validators.py`), la génération de commandes par pare-feu (`generators/`) et la logique de dédup/sauvegarde (`blocker.py`), avec une base SQLite temporaire isolée par test (`tests/conftest.py`).

## Logs

Toute exception non gérée (démarrage ou callback d'interface) est enregistrée dans `data/app.log` (fichier tournant, 1 Mo x 4) et affichée dans une boîte de dialogue — utile car l'exe est construit en mode `--windowed` (pas de console visible).

## Données

`data/blacklister.db` n'est pas chiffrée : toute personne ayant accès au poste ou à l'exe portable (clé USB, poste partagé) peut la lire, y compris les noms de cas. À garder en tête si un cas référence un client/incident sensible.

## SSH

Login et mot de passe sont ressaisis à chaque connexion et jamais écrits sur disque (seul le login est retenu en mémoire pour la durée de la session, pour éviter de le retaper à chaque device). Le push automatique (`paramiko`) accepte la clé d'hôte SSH présentée sans la comparer à un `known_hosts` existant (`AutoAddPolicy`) — adapté à un usage interne sur un réseau de confiance, pas à une connexion via un réseau non maîtrisé.

## Version / À propos

La version affichée (bas de la fenêtre, cliquable) vient de `git describe --tags --always --dirty` : `vX.Y.Z` sur un commit tagué propre, `vX.Y.Z-dirty` s'il reste des modifications non commitées, `vX.Y.Z-N-g<hash>` si on est N commits après le dernier tag. Pour une version propre après un push, tagger le commit (`git tag -a vX.Y.Z -m "..."`, puis `git push origin vX.Y.Z`) avant de relancer `./build.ps1` — qui fige version + date de build dans l'exe au moment du build (`app/_build_info.py`, généré, non versionné). En dev (`python app/main.py`), la version est recalculée à la volée et la date de build affiche « non buildé ».

## Structure

- `app/validators.py` — validation/normalisation IPv4, CIDR, FQDN
- `app/db.py` — persistance SQLite (cas, pare-feu physiques/`devices`, entrées bloquées)
- `app/blocker.py` — dédup intra/inter-cas (scopée par device) + orchestration des générateurs
- `app/generators/` — un module par marque de pare-feu
- `app/ssh_client.py` — terminal SSH pré-rempli et push des commandes (paramiko), sans identifiants stockés
- `app/app_info.py` — version (git) / date de build pour l'écran « À propos »
- `app/ui/` — interface CustomTkinter (dont `devices_tab.py`, `ssh_dialogs.py` et `about_dialog.py`)
- `app/logging_setup.py` — logging fichier + capture des exceptions non gérées
- `tests/` — suite de tests pytest

## Licence

MIT — voir [LICENSE](LICENSE).
