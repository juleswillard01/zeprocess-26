# CDC — OneNote Exporter

## 1. Authentification
### 1.1 Azure AD OAuth2
- Device code flow (pas de redirect browser) <!-- DONE -->
- Permissions : `Notes.Read` (lecture seule) <!-- DONE -->
- Refresh automatique du token avant expiration (~1h) <!-- DONE -->
- Stockage token en mémoire uniquement (jamais sur disque) <!-- DONE -->

### 1.2 Configuration
- `AZURE_CLIENT_ID` et `AZURE_TENANT_ID` via `.env` <!-- DONE -->
- Pas de `client_secret` nécessaire pour device code flow <!-- DONE -->
- Support du tenant `common` pour comptes personnels <!-- DONE -->

## 2. Mapping Hiérarchie
### 2.1 Arbre complet
- Lister tous les notebooks de l'utilisateur <!-- DONE -->
- Pour chaque notebook : lister les section groups (récursif) <!-- DONE -->
- Pour chaque section : lister les pages (avec pagination) <!-- DONE -->
- Afficher le nombre de pages par section et le total <!-- DONE -->

### 2.2 Affichage
- Format arbre (tree) avec indentation <!-- DONE -->
- Compteur de pages par nœud : `Section A (12 pages)` <!-- DONE -->
- Total en bas : `Total : 347 pages` <!-- DONE -->
- Couleurs via `rich` pour la lisibilité <!-- DONE -->

### 2.3 Cache
- Cacher la hiérarchie dans `io/cache/hierarchy.json` <!-- DONE -->
- TTL configurable (défaut : 1h) <!-- DONE -->
- Option `--no-cache` pour forcer le refresh <!-- DONE -->

## 3. Sélection
### 3.1 Mode interactif
- Afficher l'arbre puis demander la sélection <!-- DONE -->
- Sélection par numéro de section ou nom <!-- DONE -->
- Support multi-sélection : `1,3,5` ou `1-5` <!-- DONE -->

### 3.2 Mode CLI
- `--sections "Section A,Section B"` pour sélection directe <!-- DONE -->
- `--all` pour tout exporter (avec confirmation si > 200 pages) <!-- DONE -->
- `--max-pages 150` pour limiter automatiquement <!-- DONE -->

## 4. Export
### 4.1 Récupération contenu
- Fetch du HTML de chaque page via Graph API <!-- DONE -->
- Téléchargement des images embarquées <!-- DONE -->
- Respect du rate limit : 4 req/s max, backoff exponentiel sur 429 <!-- DONE -->

### 4.2 Conversion PDF
- HTML → PDF via WeasyPrint <!-- DONE -->
- Un PDF par page OneNote <!-- DONE -->
- Nommage : `{section}/{ordre}_{titre_page}.pdf` <!-- DONE -->
- Dossier de sortie : `io/exports/` <!-- DONE -->

### 4.3 Rapport
- Barre de progression pendant l'export <!-- DONE -->
- Rapport final : nombre de pages exportées, taille totale, erreurs <!-- DONE -->
- Log des erreurs dans `io/exports/errors.log` <!-- DONE -->

## 5. CLI
### 5.1 Commandes
- `onenote-export tree` : afficher la hiérarchie <!-- DONE -->
- `onenote-export export` : exporter les pages sélectionnées <!-- DONE -->
- `onenote-export auth` : tester l'authentification <!-- DONE -->

### 5.2 Options globales
- `--verbose` / `-v` : mode debug <!-- DONE -->
- `--no-cache` : ignorer le cache <!-- DONE -->
- `--output-dir` : dossier de sortie custom <!-- DONE -->

## 6. Infrastructure
### 6.1 Docker
- Image basée sur `python:3.12-slim` <!-- DONE -->
- WeasyPrint et ses dépendances système <!-- DONE -->
- Volume monté pour `io/` <!-- DONE -->

### 6.2 Qualité
- Tests : couverture ≥ 80% <!-- DONE -->
- Lint : ruff + pyright strict <!-- DONE -->
- CI : lint → test → build (GitHub Actions) <!-- DONE -->

---

## Statut d'implémentation
- **Total points CDC** : 28
- **DONE** : 28 (100%)
- **PARTIAL** : 0
- **TODO** : 0
- **Dernière mise à jour** : 2026-03-20 (Vague 5)
