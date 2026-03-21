# Règle : Testing

## TDD obligatoire
- Écrire le test AVANT le code. Toujours.
- Le test DOIT échouer avant l'implémentation (RED).
- Implémenter le MINIMUM pour passer (GREEN).
- Refactorer APRÈS les tests verts.

## Framework
- pytest pour tout le code Python
- Couverture cible : ≥ 80%
- Mocking : `respx` pour httpx, `pytest-httpx` en alternative
- JAMAIS d'appels réseau réels dans les tests

## Conventions
- Fichiers : `tests/test_<module>.py`
- Nommage : `test_<quoi>_<condition>_<attendu>`
- Un test = un comportement
- Fixtures pour le setup partagé

## Commandes
```bash
make test             # pytest -x --tb=short (fail fast)
make test-cov         # pytest --cov=src --cov-report=term-missing
```
