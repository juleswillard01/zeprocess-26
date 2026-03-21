# OneNote Exporter — The Process / Branche Aurélien

CLI Python pour extraire les pages OneNote via Microsoft Graph API, exporter en TXT/PDF, et regrouper en Markdown thématiques pour Claude Projects.

## Prérequis

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker (optionnel)

## Setup rapide

```bash
# 1. Cloner et installer
git clone <repo-url>
cd onenote-exporter
make install

# 2. Configurer Azure AD (voir section ci-dessous)
cp .env.example .env
# Éditer .env avec AZURE_CLIENT_ID et AZURE_TENANT_ID

# 3. Tester l'auth
onenote-export auth

# 4. Afficher l'arbre OneNote (avec couleurs rich)
onenote-export tree

# 5. Exporter en TXT
onenote-export export --all --format txt

# 6. Regrouper en 10 fichiers Markdown
onenote-export bundle
```

## Commandes

| Commande | Description |
|----------|-------------|
| `onenote-export auth` | Tester l'authentification Azure AD |
| `onenote-export tree` | Afficher l'arbre OneNote (couleurs rich, comptage pages) |
| `onenote-export export` | Mode interactif : sélection par numéro (1,3,5 ou 1-5) |
| `onenote-export export --sections "A,B"` | Export direct par nom de section |
| `onenote-export export --all --format txt` | Exporter toutes les pages en TXT |
| `onenote-export export --all --format pdf` | Exporter toutes les pages en PDF (images incluses) |
| `onenote-export export --all --resume` | Reprendre un export interrompu (skip fichiers existants) |
| `onenote-export bundle` | Regrouper les TXT en 10 Markdown thématiques |
| `onenote-export bundle --dry-run` | Prévisualiser le regroupement sans écrire |
| `onenote-export --no-cache tree` | Forcer le refresh (ignorer le cache 24h) |
| `onenote-export -n "GAME" tree` | Cibler un notebook spécifique |
| `onenote-export -v export` | Mode verbose/debug |

## Pipeline complet

```
OneNote (Graph API) → TXT/PDF (io/exports/) → 10 Markdown (io/md/) → Claude Projects
```

### 1. Export OneNote → TXT

```bash
onenote-export export --all --format txt
```

- Auth device code flow (1 seule fois, cache MSAL 24h)
- 1163 pages exportées section par section dans `io/exports/<section>/`
- Resume automatique (skip fichiers existants)
- Rate limit : 4 req/s + 10 retries avec backoff exponentiel + 5s cooldown entre sections

### 2. Bundle → 10 Markdown

```bash
onenote-export bundle
```

Regroupe les 1085 pages en 10 fichiers thématiques avec table des matières :

| Fichier | Sections incluses | Pages |
|---------|-------------------|-------|
| `01_REVELATION_LR.md` | Revelation LR | 149 |
| `02_REVELATION_VALUE.md` | Revelation TXT VALUE, Revelation Value | 194 |
| `03_LES_COACHS.md` | Les Coachs se Lachent | 91 |
| `04_VALUE.md` | VALUE, Value, Lindberg Model | 92 |
| `05_LR.md` | LR | 70 |
| `06_REVELATION_FR.md` | Revelation FR, Questions, TINDER Profil, REVELATION 2 | 168 |
| `07_TXTGAME.md` | Revelation TXTGAME, TXT, TXTGAME Blueprint | 80 |
| `08_JON.md` | JON, Jon Notes, Jon HTML | 32 |
| `09_FR_CHALLENGE.md` | FR, CHALLENGE, Avant-Propos, BOOTCAMP, etc. | 71 |
| `10_MISC.md` | SEXU, LOUP_DDP, ARTICLES FONDATEURS, QdA, etc. | 138 |

### 3. Upload → Claude Projects

Les 10 fichiers MD dans `io/md/` sont prêts pour upload dans la knowledge base de Claude Projects.

## Azure AD Setup (une seule fois)

### Étape 1 — Créer l'app registration

1. Aller sur [portal.azure.com](https://portal.azure.com)
2. **Microsoft Entra ID** → **App registrations** → **New registration**
3. Nom : `onenote-exporter`
4. **Supported account types** : voir tableau ci-dessous
5. Redirect URI : **laisser vide** (device code flow)
6. Cliquer **Register**

### Étape 2 — Choisir le bon type de compte

| Option | Quand l'utiliser |
|--------|-----------------|
| **Accounts in this organizational directory only** | Compte pro/scolaire dans UN SEUL tenant |
| **Accounts in any organizational directory** | Comptes pro de n'importe quel tenant |
| **Accounts in any org directory + personal accounts** | Comptes pro + perso (@outlook, @hotmail) |
| **Personal Microsoft accounts only** | Uniquement @outlook, @hotmail, @live |

### Étape 3 — Configurer l'app

1. Note le **Application (client) ID** → `AZURE_CLIENT_ID`
2. Note le **Directory (tenant) ID** → `AZURE_TENANT_ID`
   - Compte personnel → `consumers`
   - Multi-tenant → `common`
   - Tenant spécifique → GUID du tenant
3. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated** → `Notes.Read`
4. **Authentication** → **Advanced settings** → **Allow public client flows** → **Yes** → **Save**

### Étape 4 — `.env`

```env
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_TENANT_ID=common
NOTEBOOK_NAME=GAME
```

## Troubleshooting

### "Le compte n'existe pas dans le client Microsoft Services"

Le type de compte ne correspond pas au "Supported account types" de l'app registration. Vérifier le `signInAudience` dans le **Manifest** et ajuster.

### "AADSTS65001: consent required"

L'admin du tenant doit approuver `Notes.Read`, ou réessayer le device code flow pour le prompt de consentement.

### "AZURE_CLIENT_ID ne peut pas être vide"

Copier `.env.example` vers `.env` et remplir les valeurs.

### Rate limit (429 errors)

Le CLI gère automatiquement : 10 retries avec backoff exponentiel, 5s de cooldown entre sections. Si ça persiste, réduire `GRAPH_RATE_LIMIT` dans `.env`.

## Développement

```bash
make install          # uv sync
make test             # pytest -x --tb=short
make test-cov         # pytest --cov=src --cov-fail-under=80
make lint             # ruff check + ruff format --check
make typecheck        # pyright strict
make format           # ruff format
make docker-build     # docker build
```

## Métriques

- **250 tests**, 0 failures, **96% coverage**
- Pyright strict : 0 erreurs
- Ruff : 0 erreurs
- 9 ADRs documentés
- CI GitHub Actions configuré

## Architecture

```
src/
  auth.py          # Azure AD OAuth2 device code flow + MSAL cache 24h
  config.py        # Settings via pydantic-settings (.env)
  graph.py         # Client Microsoft Graph API (retry 10x, backoff, SSRF guard)
  hierarchy.py     # Arbre notebook/section/page + cache JSON 24h
  exporter.py      # HTML → PDF/TXT (sanitize, images base64, path guard)
  bundler.py       # Regroupement TXT → 10 Markdown thématiques
  cli.py           # CLI Click (auth, tree, export, bundle)
tests/             # Miroir de src/ — 250 tests TDD
io/
  cache/           # hierarchy.json + msal_cache.bin (gitignored)
  exports/         # TXT/PDF par section (gitignored)
  md/              # 10 fichiers Markdown thématiques (gitignored)
docs/
  CDC.md           # Cahier des charges
  adr/             # 9 Architecture Decision Records
```

## Licence

MIT
