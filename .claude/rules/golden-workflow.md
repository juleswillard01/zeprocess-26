# Règle : Golden Workflow

Chaque tâche de développement DOIT suivre ces 7 étapes dans l'ordre.
Aucune étape ne peut être sautée. Les transitions sont contrôlées par l'orchestrator.

## Étapes
0. **CDC** → Valider contre `docs/CDC.md`
1. **Plan** → Concevoir, écrire le plan, produire un ADR si nécessaire
2. **TDD** → Test d'abord (RED), implémenter (GREEN)
3. **Review** → Lint + typecheck + revue code + sécurité
4. **Verify** → Quality gate approprié (25/50/75/100%)
5. **Commit** → `type(scope): description` — conventionnel, atomique
6. **Refactor** → Nettoyage post-commit, tests toujours verts

## Blocages
- Pas de code sans plan approuvé
- Pas de code sans test écrit d'abord
- Pas de commit sans lint + typecheck + tests verts
- Pas de merge sans quality gate PASS
