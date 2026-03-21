# Règle : Portes Qualité

Chaque feature passe par 4 gates progressifs. Le quality-gate-keeper orchestre.

## Gate 25% — Architecture
- Plan existe et est documenté
- ADR écrit pour les décisions techniques majeures
- Interfaces définies (signatures, types de retour)
- Alignement CDC vérifié par cdc-validator
- **Bloquant** : pas de code sans plan approuvé

## Gate 50% — Intégration
- Interfaces implémentées
- Tests unitaires écrits et passent
- `make lint` passe
- `make typecheck` passe
- **Bloquant** : pas de review sans tests verts

## Gate 75% — Qualité
- Couverture tests ≥ 80%
- Aucune issue CRITICAL en sécurité
- Edge cases identifiés et testés
- Performance acceptable (pas de O(n²) évitable)
- **Bloquant** : pas de merge avec CRITICAL sécurité

## Gate 100% — Livraison
- CDC intégralement implémenté
- Documentation à jour (README, docstrings)
- `make docker-build` réussit
- Smoke test manuel validé
- **Bloquant** : pas de release sans gate 100%

## Verdict
- **PASS** : tous les critères du gate remplis
- **CONDITIONAL** : critères non-bloquants manquants, peut avancer avec plan de remédiation
- **FAIL** : critères bloquants manquants, retour à l'étape précédente
