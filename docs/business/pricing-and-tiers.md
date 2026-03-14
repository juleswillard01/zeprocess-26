# Pricing & Tiers — QUIXAI / Hexis

## Tiers

| | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| **Prix** | 20 EUR/mois | 90 EUR/mois | 180 EUR/mois |
| **Agents** | 1 au choix | Tous | Tous |
| **Concurrence** | 1X (1 session) | 1X (1 session) | 5X (5 sessions) |
| **Canaux** | Web | Web + Telegram | Web + Telegram + WhatsApp + Discord |
| **Memoire** | Episodique + semantique | 5 types | 5 types |
| **Support** | Communaute | Email 24h | Prioritaire |
| **Au-dela** | — | — | Coaching terrain (200+ EUR, humain) |

## "1X vs 5X" = sessions simultanees

- 1X : 1 conversation agent active a la fois (sequentiel)
- 5X : 5 conversations paralleles (batch inference)

## Unit economics

| | Revenu | Stripe (2.9%+0.30) | Marge |
|---|---|---|---|
| Tier 1 | 20 EUR | 0.88 EUR | 95% |
| Tier 2 | 90 EUR | 2.91 EUR | 97% |
| Tier 3 | 180 EUR | 5.52 EUR | 97% |

Couts fixes: 279 EUR/mois (Claude Max 174 + OVH 55 + Stripe ~20 + monitoring 20 + email 10)

**Break-even**: 3-4 abonnes (ARPU 80 EUR mix 40/40/20).

## Stripe setup

```
Tier 1: prod_hexis_tier1  -> price 2000 EUR cents/month, trial 7j
Tier 2: prod_hexis_tier2  -> price 9000 EUR cents/month, trial 14j
Tier 3: prod_hexis_tier3  -> price 18000 EUR cents/month, trial 30j
```

Webhooks critiques: subscription.created, subscription.deleted, invoice.payment_failed, charge.refunded

## Cycle de vie compte

```
TRIAL (7-30j) -> ACTIVE -> PAYMENT_PENDING (3j retry) -> DEACTIVATED (14j) -> DELETED
                    ^                                          |
                    |__________ reactivation (paiement) _______|
```

Non-paiement: desactivation immediate, suppression apres 14 jours.

## Projections

| Mois | Abonnes | MRR | Profit mensuel |
|------|---------|-----|----------------|
| 2 | 4 | 320 EUR | Break-even |
| 6 | 50 | 4,000 EUR | 3,700 EUR (92%) |
| 12 | 100 | 8,000 EUR | 7,700 EUR (96%) |

ARR a M12: ~96K EUR. Marge: 96%.
