# Golden Workflow — Pipeline complet 7 étapes

Tu exécutes le Golden Workflow complet pour la tâche demandée.

## Étape 0 — CDC
- Lire `docs/CDC.md`
- Identifier les sections pertinentes pour : $ARGUMENTS
- Déléguer au cdc-validator pour validation initiale
- Si FAIL → s'arrêter et expliquer

## Étape 1 — Plan
- Déléguer à l'architect pour la conception
- Décomposer en tâches atomiques (max 5 fichiers)
- Écrire un ADR si décision technique majeure
- Valider le plan contre le CDC

## Étape 2 — TDD
- Déléguer au tdd-engineer
- Écrire les tests AVANT le code
- `make test` → doit échouer (RED)
- Implémenter le minimum → `make test` doit passer (GREEN)

## Étape 3 — Review
- `make lint && make typecheck && make test`
- Déléguer au code-reviewer pour revue qualité
- Déléguer au security-auditor pour audit sécurité
- Si CRITICAL → corriger avant de continuer

## Étape 4 — Verify
- Déléguer au quality-gate-keeper
- Exécuter le gate approprié (25/50/75/100%)
- Si FAIL → retour à l'étape concernée

## Étape 5 — Commit
- `git add` les fichiers modifiés uniquement
- Format : `type(scope): description [CDC-X.Y]`
- Vérification pre-commit par cdc-validator

## Étape 6 — Refactor
- Déléguer au refactor-guide
- Identifier dead code, duplication, dette
- Refactorer SÉPARÉMENT des features
- Commit de refactoring séparé

---
Tâche à exécuter : $ARGUMENTS
