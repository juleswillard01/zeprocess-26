# Règle : Python

## Style
- Fonctions < 30 lignes. Extraire si plus long.
- Annotations de type sur TOUTES les signatures.
- Docstrings sur toutes les fonctions publiques.
- Pas de `except` nu — toujours spécifique.
- `pathlib.Path` jamais `os.path`.
- `httpx` jamais `requests`.
- `dataclass` ou `pydantic.BaseModel` pour les données structurées.

## Outils
- Lint : `ruff check src tests`
- Format : `ruff format src tests`
- Types : `pyright src` en mode strict
- Package manager : `uv` uniquement

## Imports
- stdlib en premier, puis third-party, puis local
- ruff gère le tri automatiquement (`I` rules)

## Secrets
- Variables d'environnement via `.env` + `pydantic-settings`
- JAMAIS de secrets hardcodés
- JAMAIS commit `.env`
