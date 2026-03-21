# OneNote Exporter — The Process / Branche Aurélien

CLI Python pour extraire sélectivement des pages OneNote via Microsoft Graph API et les exporter en PDF.
Conçu pour alimenter Claude en lots de ~100-150 pages.

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

# 5. Exporter — mode interactif
onenote-export export

# 5b. Ou export direct par section
onenote-export export --sections "Section A,Section B"

# 5c. Ou tout exporter
onenote-export export --all --max-pages 150
```

Les PDF sont générés dans `io/exports/`.

## Azure AD Setup (une seule fois)

### Étape 1 — Créer l'app registration

1. Aller sur [portal.azure.com](https://portal.azure.com)
2. **Microsoft Entra ID** (ex Azure Active Directory) → **App registrations** → **New registration**
3. Nom : `onenote-exporter`
4. **Supported account types** : choisir selon ton cas (voir ci-dessous)
5. Redirect URI : **laisser vide** (device code flow n'en utilise pas)
6. Cliquer **Register**

### Étape 2 — Choisir le bon type de compte

C'est ici que ça se joue. Le choix du "Supported account types" détermine qui peut se connecter :

| Option | Quand l'utiliser |
|--------|-----------------|
| **Accounts in this organizational directory only** | Compte professionnel/scolaire dans UN SEUL tenant Azure AD |
| **Accounts in any organizational directory** | Comptes pro/scolaires de N'IMPORTE QUEL tenant Azure AD |
| **Accounts in any organizational directory and personal Microsoft accounts** | Comptes pro + comptes personnels (@outlook.com, @hotmail.com, @live.com) |
| **Personal Microsoft accounts only** | Uniquement @outlook.com, @hotmail.com, @live.com |

**Si tu as un compte personnel** (outlook/hotmail/live) → choisis l'option 3 ou 4.
**Si tu as un compte pro/école** → choisis l'option 1 ou 2 selon ton cas.

### Étape 3 — Configurer l'app

1. Note le **Application (client) ID** → `AZURE_CLIENT_ID`
2. Note le **Directory (tenant) ID** → `AZURE_TENANT_ID`
   - Pour un compte personnel : utilise `consumers` au lieu du tenant ID
   - Pour multi-tenant : utilise `common`
   - Pour un tenant spécifique : utilise le GUID du tenant
3. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions** → cherche `Notes.Read` → **Add permissions**
4. **Authentication** → **Advanced settings** → **Allow public client flows** → **Yes** → **Save**

### Étape 4 — `.env`

```env
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_TENANT_ID=common
```

Valeurs possibles pour `AZURE_TENANT_ID` :
- `common` — accepte tous les types de comptes (pro + perso)
- `consumers` — comptes personnels Microsoft uniquement
- `organizations` — comptes pro/école uniquement
- `xxxxxxxx-xxxx-...` — un tenant spécifique (GUID)

## Troubleshooting

### Erreur "Le compte n'existe pas dans le client Microsoft Services"

```
Le compte d'utilisateur sélectionné n'existe pas dans le client
« Microsoft Services » et ne peut pas accéder à l'application
```

**Cause** : Le type de compte avec lequel tu te connectes ne correspond pas au
"Supported account types" configuré dans l'app registration.

**Solution** :

1. Va dans [portal.azure.com](https://portal.azure.com) → **App registrations** → ton app
2. **Manifest** → cherche `"signInAudience"` :
   - `"AzureADMyOrg"` → seulement les comptes de TON tenant
   - `"AzureADMultipleOrgs"` → comptes pro de n'importe quel tenant
   - `"AzureADandPersonalMicrosoftAccount"` → pro + perso
   - `"PersonalMicrosoftAccount"` → perso uniquement
3. Si tu utilises un compte **personnel** (@outlook, @hotmail, @live) :
   - Change `signInAudience` en `"AzureADandPersonalMicrosoftAccount"` ou `"PersonalMicrosoftAccount"`
   - OU crée une nouvelle app registration avec le bon type
4. Mets à jour `AZURE_TENANT_ID` dans `.env` :
   - Compte perso → `AZURE_TENANT_ID=consumers`
   - Multi-tenant → `AZURE_TENANT_ID=common`

### Erreur "AADSTS65001: consent required"

L'admin du tenant doit approuver la permission `Notes.Read`, ou l'utilisateur doit donner son consentement. Réessaie le device code flow — le prompt de consentement apparaîtra.

### Erreur "AZURE_CLIENT_ID ne peut pas être vide"

Tu n'as pas configuré ton `.env`. Copie `.env.example` et remplis les valeurs.

## Commandes

| Commande | Description |
|----------|-------------|
| `onenote-export auth` | Tester l'authentification |
| `onenote-export tree` | Afficher l'arbre OneNote (couleurs rich, comptage pages) |
| `onenote-export export` | Mode interactif : sélection par numéro (1,3,5 ou 1-5) |
| `onenote-export export --sections "A,B"` | Export direct par nom de section |
| `onenote-export export --all` | Tout exporter (confirmation si >200 pages) |
| `onenote-export --no-cache tree` | Forcer le refresh (ignorer le cache 1h) |
| `onenote-export -v export` | Mode verbose/debug |

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

## Métriques actuelles

- **171 tests**, 0 failures, **95% coverage**
- Pyright strict : 0 erreurs
- Ruff : 0 erreurs
- 9 ADRs documentés
- CI GitHub Actions configuré

## Architecture

```
src/
  auth.py          # Azure AD OAuth2 device code flow
  config.py        # Settings via pydantic-settings (.env)
  graph.py         # Client Microsoft Graph API (retry, SSRF guard)
  hierarchy.py     # Arbre notebook/section/page + cache JSON
  exporter.py      # HTML → PDF (sanitize, images base64, WeasyPrint)
  cli.py           # CLI Click (tree, export, auth, mode interactif)
tests/             # Miroir de src/ — 171 tests TDD
docs/
  CDC.md           # Cahier des charges (source de vérité)
  adr/             # 9 Architecture Decision Records
  cahier-de-recettes.md
  audit-golden-workflow.md
  sprint-report-2026-03-20.md
```

## Licence

MIT
