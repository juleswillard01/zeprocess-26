# ADR-009 : Vague 5 — Fermeture des gaps CDC

## Statut
Accepté — 2026-03-20

## Contexte
Après Vague 4, 4 gaps CDC restaient :
- §3.1 Mode interactif non implémenté
- §2.2 Affichage sans couleurs rich
- §4.1 Images embarquées non téléchargées
- §4.3 Barre de progression absente
- §6.2 CI/CD non déployé

## Décision
5 features implémentées en parallèle avec TDD :

### 1. Mode interactif (§3.1)
- `_parse_selection()` parse "1,3,5" et "1-5" en indices
- `_build_numbered_sections()` flatten l'arbre pour numérotation
- Si ni `--sections` ni `--all`: mode interactif avec prompt
- Fix: page titles utilisés au lieu des page IDs dans les tuples d'export

### 2. Rich tree (§2.2)
- `display_tree` utilise maintenant `rich.Tree` pour l'affichage coloré
- Notebooks en cyan, sections en vert avec compteur, total en bold
- Backward compatible: retourne toujours un string

### 3. Images embarquées (§4.1)
- `GraphClient.download_resource()` télécharge les ressources binaires
- `_replace_images_with_data_uris()` convertit les URLs Graph en base64 data URIs
- Intégré avant sanitization HTML dans `export_page_to_pdf`

### 4. Barre de progression (§4.3)
- `rich.progress.Progress` dans `export_batch()` via paramètre `progress=True`
- Désactivable pour les tests et pipes (`progress=False`)

### 5. CI/CD (§6.2)
- GitHub Actions: lint → typecheck → test → docker build
- uv pour l'installation, WeasyPrint deps système
- Coverage gate ≥ 80%

## Alternatives rejetées
- **questionary pour le mode interactif** : rich est déjà une dépendance, suffisant
- **tqdm pour la progression** : rich est déjà utilisé pour l'arbre
- **BeautifulSoup pour parser les images HTML** : regex suffisant pour les URLs Graph
- **Self-hosted runner pour CI** : GitHub-hosted Ubuntu avec apt-get pour WeasyPrint deps

## Conséquences
- Conformité CDC passe de ~80% à ~95%
- Toutes les features utilisateur sont implémentées
- CI automatise les gates qualité
- Gaps résiduels: CI deployment monitoring, pip-audit automatique

## Implémentation
- `src/cli.py` : `_parse_selection()`, `_build_numbered_sections()`, mode interactif
- `src/hierarchy.py` : `display_tree` avec `rich.Tree`
- `src/graph.py` : `GraphClient.download_resource()`
- `src/exporter.py` : `_replace_images_with_data_uris()`, `export_batch(progress=...)`
- `.github/workflows/ci.yml` : pipeline lint → typecheck → test → docker build

## Référence CDC
CDC §2.2, §3.1, §4.1, §4.3, §6.2
