# Règle : Conformité CDC

Le Cahier des Charges (`docs/CDC.md`) est la source de vérité.

## Principes
- Tout plan DOIT référencer les sections du CDC qu'il implémente
- Tout commit DEVRAIT référencer le point CDC concerné
- Le cdc-validator est invoqué à l'étape 0 et à l'étape 5 (pre-commit)

## Format de référence
Dans les commits : `feat(graph): implémenter listing notebooks [CDC-2.1]`
Dans les plans : `## Implémente CDC §2.1 — Mapping hiérarchie`

## Divergence
Si une décision technique diverge du CDC :
1. Documenter la raison dans un ADR
2. Mettre à jour le CDC pour refléter la réalité
3. Le CDC suit le code, pas l'inverse (après validation)

## Métriques
- Conformité < 50% → FAIL, retour au plan
- Conformité 50-79% → CONDITIONAL, identifier les manques
- Conformité ≥ 80% → PASS
