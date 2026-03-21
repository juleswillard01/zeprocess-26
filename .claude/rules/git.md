# Règle : Git

## Stratégie
- Trunk-based development (main directement)
- Commits atomiques — un commit = un changement logique
- Conventional commits obligatoire

## Format commit
```
type(scope): description courte

[corps optionnel — pourquoi, pas quoi]
```

## Types autorisés
- `feat` : nouvelle fonctionnalité
- `fix` : correction de bug
- `test` : ajout ou modification de tests
- `refactor` : restructuration sans changement de comportement
- `docs` : documentation uniquement
- `chore` : maintenance (deps, CI, config)
- `perf` : amélioration de performance

## Scopes du projet
- `auth` : authentification Azure AD / MSAL
- `graph` : client Microsoft Graph API
- `hierarchy` : mapping arbre OneNote
- `export` : export HTML → PDF
- `cli` : interface ligne de commande
- `config` : configuration et settings
- `infra` : Docker, Makefile, CI

## Avant chaque commit
```bash
make lint && make typecheck && make test
```
Si ça ne passe pas, on ne commit pas.
