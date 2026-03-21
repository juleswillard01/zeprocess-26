# Lint & Typecheck

Exécuter tous les outils de qualité statique.

1. `ruff check src tests` — linting
2. `ruff format --check src tests` — format
3. `pyright src` — types strict
4. Pour chaque erreur : expliquer et proposer le fix concret
5. Appliquer les fixes automatiques si possible : `ruff check --fix` et `ruff format`

Focus sur : $ARGUMENTS
