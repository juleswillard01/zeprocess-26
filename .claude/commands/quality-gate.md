# Quality Gate Runner

Exécuter le quality gate demandé et produire un rapport.

## Instructions
1. Identifier le niveau de gate : $ARGUMENTS (25, 50, 75, ou 100)
2. Lire `.claude/rules/quality-gates.md` pour les critères
3. Exécuter les vérifications automatisées :
   - `make test-cov` (couverture)
   - `make lint` (qualité code)
   - `make typecheck` (types)
   - `make docker-build` (si gate 100%)
4. Déléguer aux agents reviewers selon le gate
5. Agréger les résultats
6. Produire le verdict : PASS / CONDITIONAL / FAIL

## Format rapport
```
## Quality Gate $ARGUMENTS% — [PASS|CONDITIONAL|FAIL]
Date : [date]
Score : X/Y critères
### Critères remplis ✅
### Critères manquants ❌
### Bloqueurs
### Actions requises
```
