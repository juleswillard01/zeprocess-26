# Cahier de Recettes — OneNote Exporter

**Projet** : OneNote Exporter (branche Aurélien)
**Date** : 2026-03-20
**Version** : 1.0

---

## Introduction

Ce document décrit les scénarios de recette fonctionnelle pour valider l'implémentation du OneNote
Exporter conformément au CDC (`docs/CDC.md`). Chaque section CDC est couverte par des scénarios de
test et 4 questions QCM validant la compréhension des choix d'implémentation.

---

## 1. Authentification (CDC §1.1–1.2)

### Scénarios de test

| ID | Description | Prérequis | Étapes | Résultat attendu | Statut |
|----|-------------|-----------|--------|-------------------|--------|
| AUTH-01 | Authentification réussie | `AZURE_CLIENT_ID` et `AZURE_TENANT_ID` configurés dans `.env` | 1. Lancer `make auth` 2. Suivre le device code flow | Message "Authentification réussie" affiché | - |
| AUTH-02 | Échec sans client_id | `AZURE_CLIENT_ID` vide ou absent | 1. Lancer `make auth` | `ValueError` levée, message d'erreur clair | - |
| AUTH-03 | Token en mémoire uniquement | Authentification réussie | 1. S'authentifier 2. Vérifier `io/` et `/tmp` | Aucun fichier token sur le filesystem | - |
| AUTH-04 | Permissions minimales | Authentification réussie | 1. Vérifier le scope demandé dans les logs | Scope = `Notes.Read` uniquement | - |

### QCM

**Q1.** Pourquoi le token OAuth2 n'est-il jamais stocké sur disque ?
- a) Parce que MSAL ne supporte pas le stockage fichier
- b) Parce qu'un token sur disque est un vecteur d'attaque et qu'un batch CLI de 5-30 min n'a pas besoin de persistence
- c) Parce que le token expire trop vite
- d) Pour économiser de l'espace disque

**Réponse : b)** — ADR-001 : la durée de vie d'un batch (5-30 min) est inférieure à l'expiration du token (~1h). Le stockage disque ajoute un risque sans bénéfice.

**Q2.** Quel scope OAuth2 est demandé ?
- a) `Notes.ReadWrite`
- b) `Notes.Read.All`
- c) `Notes.Read`
- d) `User.Read Notes.Read`

**Réponse : c)** — CDC §1.1 : permissions minimales, lecture seule.

**Q3.** Pourquoi le device code flow plutôt que le client credentials flow ?
- a) Le device code flow est plus rapide
- b) Le client credentials flow nécessite un `client_secret`, plus complexe pour l'utilisateur
- c) Le device code flow supporte le multi-tenant
- d) Le client credentials flow n'est pas disponible pour OneNote

**Réponse : b)** — ADR-001 : pas de `client_secret` nécessaire pour un CLI public.

**Q4.** Que se passe-t-il si `AZURE_CLIENT_ID` est vide ?
- a) Une valeur par défaut est utilisée
- b) MSAL échoue silencieusement
- c) `authenticate()` lève `ValueError` immédiatement (fail-fast)
- d) Le device code flow démarre avec un ID nul

**Réponse : c)** — `src/auth.py:37` : validation explicite avant tout appel MSAL.

---

## 2. Mapping Hiérarchie (CDC §2.1–2.3)

### Scénarios de test

| ID | Description | Prérequis | Étapes | Résultat attendu | Statut |
|----|-------------|-----------|--------|-------------------|--------|
| HIER-01 | Arbre complet affiché | Auth réussie, notebooks existants | 1. Lancer `make tree` | Arbre avec notebooks, sections, comptage pages | - |
| HIER-02 | Cache créé après tree | Pas de cache existant | 1. `make tree` 2. Vérifier `io/cache/hierarchy.json` | Fichier JSON créé avec structure complète | - |
| HIER-03 | Cache respecté au 2e appel | Cache existant < 1h | 1. `make tree` (2e fois) | Résultat instantané, aucun appel API (vérifiable via `--verbose`) | - |
| HIER-04 | --no-cache force le refresh | Cache existant | 1. `onenote-export --no-cache tree` | Nouveaux appels API effectués, cache mis à jour | - |
| HIER-05 | Cache corrompu récupéré | Écrire du JSON invalide dans `io/cache/hierarchy.json` | 1. `make tree` | Warning loggé, re-fetch depuis API, cache régénéré | - |
| HIER-06 | Section groups imbriqués | Notebook avec section groups | 1. `make tree` | Sections dans les groups visibles dans l'arbre | - |
| HIER-07 | Arbre coloré via rich | Terminal couleur | 1. `make tree` | Notebooks en cyan, sections en vert, compteurs visibles | - |

### QCM

**Q1.** Pourquoi l'écriture du cache utilise-t-elle un fichier `.tmp` suivi d'un `rename()` ?
- a) Pour contourner les permissions fichier
- b) Pour que `rename()` soit atomique sur POSIX — aucun lecteur ne voit un fichier partiel
- c) Pour pouvoir annuler l'écriture avec Ctrl-C
- d) Parce que `json.dump` ne supporte pas l'écriture directe

**Réponse : b)** — ADR-006 : `rename()` est atomique au niveau syscall. Un crash entre write et rename laisse un `.tmp` orphelin, jamais un `hierarchy.json` tronqué.

**Q2.** Que fait `_load_cache` si le JSON est corrompu ?
- a) Lève `json.JSONDecodeError`
- b) Retourne une liste vide
- c) Retourne `None` (déclenchant un re-fetch API)
- d) Supprime le fichier et lève une exception

**Réponse : c)** — `src/hierarchy.py:57` : `JSONDecodeError` et `KeyError` interceptés, retour `None`.

**Q3.** Pourquoi stocker `page_ids` dans le cache ?
- a) Pour accélérer l'affichage de l'arbre
- b) Pour que la commande `export` puisse utiliser le cache sans ré-appeler les endpoints de listing
- c) Pour permettre la recherche de pages par ID
- d) Pour compter le nombre total de pages

**Réponse : b)** — ADR-006 : sans `page_ids`, chaque `export` nécessiterait un re-fetch même avec le cache.

**Q4.** Comment le TTL du cache est-il mesuré ?
- a) Par un champ `created_at` dans le JSON
- b) Par la date de dernière modification du fichier (`st_mtime`)
- c) Par un compteur de secondes dans le nom du fichier
- d) Par une requête à l'API pour vérifier les changements

**Réponse : b)** — `src/hierarchy.py:50` : `time.time() - cache_file.stat().st_mtime`.

---

## 3. Sélection (CDC §3.1–3.2)

### Scénarios de test

| ID | Description | Prérequis | Étapes | Résultat attendu | Statut |
|----|-------------|-----------|--------|-------------------|--------|
| SEL-01 | Sélection par nom de section | Auth + arbre disponible | 1. `onenote-export export --sections "Section A"` | Seules les pages de "Section A" exportées | - |
| SEL-02 | Multi-sélection | Auth + arbre | 1. `--sections "Section A,Section B"` | Pages des deux sections exportées | - |
| SEL-03 | --all avec confirmation | Auth + >200 pages | 1. `onenote-export export --all` | Prompt de confirmation affiché | - |
| SEL-04 | --all annulé | Auth + >200 pages | 1. `--all` 2. Répondre "n" | Export annulé, message affiché | - |
| SEL-05 | --max-pages limite | Auth + arbre | 1. `--all --max-pages 10` | Maximum 10 pages exportées | - |
| SEL-06 | Mode interactif s'active sans flags | Auth + arbre | 1. `onenote-export export` (sans --sections ni --all) | Arbre numéroté affiché, prompt de sélection | - |
| SEL-07 | Sélection par numéro unique | Mode interactif | 1. Entrer "3" | Pages de la section 3 exportées | - |
| SEL-08 | Multi-sélection par range | Mode interactif | 1. Entrer "1-5" | Pages des sections 1 à 5 exportées | - |
| SEL-09 | Multi-sélection mixte | Mode interactif | 1. Entrer "1,3-5,8" | Pages des sections 1,3,4,5,8 exportées | - |

### QCM

**Q1.** À partir de combien de pages le prompt de confirmation apparaît-il avec `--all` ?
- a) 100 pages
- b) 150 pages
- c) 200 pages
- d) 250 pages

**Réponse : c)** — CDC §3.2 et `src/cli.py:103` : `if len(page_ids) > 200`.

**Q2.** Quelle est la valeur par défaut de `--max-pages` ?
- a) 100
- b) 150
- c) 200
- d) Illimité

**Réponse : b)** — `src/cli.py:68` : `default=150`, aligné sur CDC §3.2.

**Q3.** Comment les sections sont-elles filtrées dans `_collect_page_ids` ?
- a) Par ID de section
- b) Par correspondance exacte du nom (`node.name in selected_sections`)
- c) Par expression régulière
- d) Par index numérique dans l'arbre

**Réponse : b)** — `src/cli.py:159` : comparaison exacte du nom.

**Q4.** Que se passe-t-il si `--sections` et `--all` ne sont pas spécifiés ?
- a) Toutes les pages sont exportées
- b) Aucune page n'est sélectionnée (export vide)
- c) Une erreur est levée
- d) Le mode interactif se lance

**Réponse : b)** — `_collect_from_node` ne matche aucune section si `export_all=False` et `selected_sections=[]`.

**Q5.** Comment `_parse_selection` gère-t-il "1-5" ?
- a) Regex split sur le tiret
- b) Loop `range(1, 6)` après découpage sur `-`
- c) Conversion directe en liste Python `[1, 5]`
- d) Erreur, la syntaxe range n'est pas supportée

**Réponse : b)** — "1-5" est découpé en `start=1, end=5` puis `range(start, end+1)` génère chaque numéro de section.

**Q6.** Que se passe-t-il si on entre un numéro hors limites (ex: "99") ?
- a) Une `IndexError` est levée
- b) Le numéro est ignoré silencieusement
- c) Le prompt est ré-affiché avec un message d'erreur
- d) Toutes les pages sont exportées par défaut

**Réponse : b)** — Les numéros hors limites ne correspondent à aucune entrée dans l'arbre numéroté et sont ignorés.

---

## 4. Export (CDC §4.1–4.3)

### Scénarios de test

| ID | Description | Prérequis | Étapes | Résultat attendu | Statut |
|----|-------------|-----------|--------|-------------------|--------|
| EXP-01 | Export PDF réussi | Auth + page OneNote | 1. Exporter une page | Fichier PDF créé dans `io/exports/` | - |
| EXP-02 | Nommage correct | Page avec titre | 1. Exporter | Fichier nommé `{ordre}_{titre_sanitisé}.pdf` | - |
| EXP-03 | Rate limit respecté | Export batch > 5 pages | 1. Exporter avec `--verbose` | Sleep de 250ms entre chaque requête visible dans les logs | - |
| EXP-04 | HTML sanitisé | Page avec `<script>` | 1. Exporter | Pas de balise script dans le PDF résultant | - |
| EXP-05 | Path traversal bloqué | Page titre `../../etc/malicious` | 1. Exporter | `ValueError` levée, aucun fichier écrit hors de `output_dir` | - |
| EXP-06 | Erreur isolée | Batch de 5 pages, 1 corrompue | 1. Exporter | 4 PDF créés + `errors.log` avec l'erreur | - |
| EXP-07 | Rapport d'export | Export terminé | 1. Vérifier la sortie | Nombre de pages exportées affiché | - |
| EXP-08 | Images embarquées téléchargées | Page avec images | 1. Exporter une page contenant des images | Images visibles dans le PDF résultant | - |
| EXP-09 | Barre de progression affichée | Terminal interactif, >3 pages | 1. Exporter un batch | Progress bar rich visible pendant l'export | - |
| EXP-10 | Progress bar absente en pipe | Redirection stdout | 1. `onenote-export export --all > out.txt` | Aucune progress bar dans la sortie redirigée | - |

### QCM

**Q1.** Quelles balises HTML sont supprimées par `_sanitize_html` ?
- a) Toutes les balises sauf `<p>`, `<div>`, `<span>`
- b) `<script>`, `<iframe>`, `<object>`, `<embed>`, `<link>`
- c) `<script>` uniquement
- d) Aucune, WeasyPrint gère la sécurité

**Réponse : b)** — ADR-004 et `src/exporter.py:72-77`.

**Q2.** Comment le path traversal est-il détecté ?
- a) En vérifiant que le titre ne contient pas `..`
- b) En comparant `resolved_pdf.is_relative_to(resolved_output)` après `Path.resolve()`
- c) En limitant la longueur du nom de fichier
- d) En utilisant `os.path.commonpath()`

**Réponse : b)** — `src/exporter.py:105-108`.

**Q3.** Pourquoi `errors.log` n'est-il créé que si des erreurs existent ?
- a) Pour économiser de l'espace disque
- b) Pour simplifier les scripts d'intégration qui testent l'existence du fichier
- c) Parce que le fichier serait illisible vide
- d) Pour éviter les conflits de fichiers

**Réponse : b)** — ADR-005 : un fichier vide compliquerait la détection automatique d'erreurs.

**Q4.** Quel est l'intervalle de sleep entre les requêtes batch à 4 req/s ?
- a) 100 ms
- b) 250 ms (`1.0 / 4`)
- c) 500 ms
- d) 1 seconde

**Réponse : b)** — `src/exporter.py:194` : `asyncio.sleep(1.0 / rate_limit)` avec `rate_limit=4`.

---

## 5. CLI (CDC §5.1–5.2)

### Scénarios de test

| ID | Description | Prérequis | Étapes | Résultat attendu | Statut |
|----|-------------|-----------|--------|-------------------|--------|
| CLI-01 | Commande `auth` | `.env` configuré | 1. `onenote-export auth` | Message de succès ou d'erreur clair | - |
| CLI-02 | Commande `tree` | Auth réussie | 1. `onenote-export tree` | Arbre affiché avec comptage | - |
| CLI-03 | Commande `export` | Auth + sections | 1. `onenote-export export -s "Section"` | PDF exportés | - |
| CLI-04 | `--verbose` active le debug | - | 1. `onenote-export -v tree` | Logs DEBUG visibles | - |
| CLI-05 | `--no-cache` propagé | Cache existant | 1. `onenote-export --no-cache tree` | Cache ignoré, API appelée | - |
| CLI-06 | Erreur auth redirigée stderr | `AZURE_CLIENT_ID` vide | 1. `onenote-export auth 2>/dev/null` | Rien sur stdout, erreur sur stderr | - |

### QCM

**Q1.** Pourquoi utiliser `click.echo()` plutôt que `print()` ?
- a) `click.echo` est plus rapide
- b) `click.echo` supporte stderr via `err=True` et est capturable par `CliRunner` dans les tests
- c) `print()` n'est pas disponible en Python 3.12
- d) `click.echo` formate automatiquement en couleur

**Réponse : b)** — ADR-008 : testabilité et séparation stdout/stderr.

**Q2.** Pourquoi y a-t-il plusieurs `asyncio.run()` dans une même commande CLI ?
- a) Parce que chaque appel async a besoin de son propre thread
- b) Parce que Click est sync et MSAL est sync — chaque bloc async est encapsulé séparément
- c) Pour paralléliser les appels API
- d) Parce que `asyncio.run()` ne peut pas être appelé une seule fois

**Réponse : b)** — ADR-007 : la frontière sync/async est traversée individuellement pour chaque bloc.

**Q3.** Que fait `ctx.exit(1)` après une erreur d'authentification ?
- a) Tue le processus immédiatement
- b) Fixe le code de sortie à 1 pour signaler une erreur au shell
- c) Affiche un message d'aide
- d) Relance l'authentification

**Réponse : b)** — Convention CLI standard : exit code 0 = succès, 1 = erreur.

**Q4.** Comment le bloc `finally` protège-t-il les ressources ?
- a) Il ferme le fichier `.env`
- b) Il appelle `asyncio.run(client.close())` pour fermer le pool de connexions TCP même en cas d'exception
- c) Il sauvegarde le token sur disque
- d) Il supprime les fichiers temporaires

**Réponse : b)** — ADR-007 et `src/cli.py:61-62, 120-121`.

---

## 6. Infrastructure (CDC §6.1–6.2)

### Scénarios de test

| ID | Description | Prérequis | Étapes | Résultat attendu | Statut |
|----|-------------|-----------|--------|-------------------|--------|
| INFRA-01 | Docker build réussit | Docker installé | 1. `make docker-build` | Image construite sans erreur | - |
| INFRA-02 | Tests passent | Dépendances installées | 1. `make test` | 131 tests, 0 échecs | - |
| INFRA-03 | Couverture >= 80% | Dépendances installées | 1. `make test-cov` | Couverture >= 80% (actuel : 96%) | - |
| INFRA-04 | Lint propre | Dépendances installées | 1. `make lint` | 0 erreur ruff | - |
| INFRA-05 | Typecheck propre | Dépendances installées | 1. `make typecheck` | 0 erreur pyright strict | - |
| INFRA-06 | Volume io/ monté | Docker opérationnel | 1. `make docker-run` | Exports écrits dans `io/exports/` sur l'hôte | - |
| INFRA-07 | CI pipeline sur push | Push sur branche AURELIEN | 1. `git push` | Jobs lint, typecheck, test, docker passent tous | - |

### QCM

**Q1.** Pourquoi la couverture cible est-elle >= 80% et non 100% ?
- a) Parce que 100% est impossible
- b) Parce que les 20% restants couvrent du code d'infrastructure (Docker entrypoint, MSAL I/O) non testable en unitaire
- c) Par convention industrielle
- d) Pour aller plus vite

**Réponse : b)** — Le code d'authentification MSAL et les interactions Docker nécessitent des tests d'intégration réels.

**Q2.** Quel est le rôle de `make lint` ?
- a) Exécuter les tests
- b) Vérifier le formatage et les erreurs de style via ruff check + ruff format --check
- c) Compiler le code Python
- d) Scanner les vulnérabilités

**Réponse : b)** — `Makefile` : `ruff check src tests` + `ruff format --check src tests`.

**Q3.** Pourquoi pyright est-il en mode strict ?
- a) Pour détecter toutes les erreurs de type à la compilation, pas au runtime
- b) Parce que le mode normal ne fonctionne pas
- c) Pour compatibilité avec mypy
- d) Pour générer de la documentation

**Réponse : a)** — Le mode strict force les annotations de type complètes et détecte les incompatibilités avant exécution.

**Q4.** Quelle image Docker de base est utilisée ?
- a) `python:3.12`
- b) `python:3.12-slim`
- c) `ubuntu:22.04`
- d) `alpine:3.18`

**Réponse : b)** — CDC §6.1 : `python:3.12-slim` pour minimiser la taille de l'image.

---

## Résumé

| Section CDC | Scénarios | QCM | Statut |
|------------|-----------|-----|--------|
| §1 Auth | 4 | 4 | Prêt |
| §2 Hiérarchie | 7 | 4 | Prêt |
| §3 Sélection | 9 | 6 | Prêt |
| §4 Export | 10 | 4 | Prêt |
| §5 CLI | 6 | 4 | Prêt |
| §6 Infra | 7 | 4 | Prêt |
| **Total** | **43** | **26** | - |

Ce cahier de recettes couvre l'ensemble des fonctionnalités décrites dans le CDC avec 43 scénarios
de test et 26 questions QCM. Chaque question est ancrée dans une décision d'implémentation
documentée dans les ADRs correspondants.
