# OneNote Exporter — The Process / Branche Aurélien

## Philosophie
Ce projet applique le dogfooding du Golden Workflow : le `.claude/` sert SIMULTANÉMENT
à développer l'outil ET constitue un modèle réutilisable pour d'autres projets.

Principes : KISS/YAGNI d'abord, backward compatibility toujours, jamais d'analogie — raisonner depuis les principes premiers.

## Quoi
CLI Python qui extrait les pages OneNote via Microsoft Graph API, mappe la hiérarchie
du notebook, et exporte les pages sélectionnées en PDF. Conçu pour alimenter Claude
en lots de ~100-150 pages (branche Aurélien de The Process).

## Stack
- **Langage** : Python 3.12+
- **Packages** : `uv` (PAS pip, PAS poetry)
- **Container** : Docker + docker-compose
- **Build** : Makefile encapsule toutes les commandes
- **Tests** : pytest + pytest-cov (TDD obligatoire, couverture ≥80%)
- **Lint** : ruff check + ruff format
- **Types** : pyright mode strict
- **Auth** : MSAL + OAuth2 device code flow
- **HTTP** : httpx (PAS requests)
- **MCP** : Context7 uniquement

## Structure projet
```
src/                  # Code source applicatif
  auth.py             # Authentification Azure AD OAuth2
  graph.py            # Client Microsoft Graph API
  hierarchy.py        # Mapping arbre notebook/section/page
  exporter.py         # Export page → HTML → PDF
  cli.py              # Point d'entrée CLI (click)
  config.py           # Settings via pydantic-settings
io/                   # Artéfacts I/O (exports, caches)
tests/                # Miroir de src/ avec préfixe test_
docs/                 # Documentation, CDC, ADR
.claude/              # Configuration Claude Code (le produit)
```

## Commandes clés
```bash
make install          # uv sync
make test             # pytest -x --tb=short
make test-cov         # pytest --cov=src --cov-report=term-missing
make lint             # ruff check + ruff format --check
make typecheck        # pyright src
make format           # ruff format src tests
make docker-build     # docker build
make docker-run       # docker-compose run --rm app
make tree             # Mapper la hiérarchie OneNote (dry run)
make export           # Exporter les pages sélectionnées en PDF
```

## Golden Workflow — OBLIGATOIRE pour chaque tâche
0. **CDC** : Valider le plan contre `docs/CDC.md` → agent cdc-validator
1. **Plan** : Concevoir pas-à-pas, écrire le plan AVANT de coder → agent architect
2. **TDD** : Test en PREMIER, le voir échouer, puis implémenter → agent tdd-engineer
3. **Review** : `make lint && make typecheck && make test` → agents code-reviewer, security-auditor
4. **Verify** : Quality gates 25/50/75/100% → agent quality-gate-keeper
5. **Commit** : Atomique, format `type(scope): description` → conventional commits
6. **Refactor** : APRÈS tests verts uniquement → agent refactor-guide

## Portes qualité
- **25%** : Architecture alignée au CDC ?
- **50%** : Interfaces intégrées et testées ?
- **75%** : Couverture ≥80%, sécurité OK, edge cases ?
- **100%** : Tout le CDC implémenté, prêt à livrer ?

## Modèles agents
- **opus** : orchestrator, cdc-validator, architect (raisonnement profond)
- **sonnet** : tdd-engineer, code-reviewer, security-auditor, infra-engineer, refactor-guide
- **haiku** : quality-gate-keeper (orchestration légère)

## Style code
- Fonctions < 30 lignes. Si plus long, extraire.
- Pas de `except` nu. Toujours attraper des exceptions spécifiques.
- Toutes les fonctions publiques ont des docstrings.
- `pathlib.Path` pas `os.path`. `httpx` pas `requests`.
- Annotations de type sur TOUTES les signatures.
- `dataclass` ou `pydantic.BaseModel` pour les données structurées.
- Variables d'environnement via `.env` + pydantic-settings. JAMAIS de secrets hardcodés.

## IMPORTANT
- JAMAIS commit `.env`, secrets, ou `client_secret`.
- JAMAIS d'appels Graph API dans les tests — utiliser `respx` ou `pytest-httpx`.
- Toujours vérifier `make lint && make typecheck` AVANT de commit.
- Respecter le rate limit Microsoft Graph (throttle à 4 req/s).
- Le comptage de pages DOIT être visible dans l'arbre pour planifier les lots ~100-150 pages.
