# Critères d'évaluation — OneNote AI Kit

## 1. Métriques de succès MVP (30 jours)

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Ventes Prompt Kit | ≥10 ventes | Gumroad dashboard |
| Revenue | ≥€300 | Gumroad |
| GitHub stars | ≥50 | GitHub |
| Downloads PyPI | ≥200 | PyPI stats |
| LinkedIn post reach | ≥5000 impressions | LinkedIn analytics |
| Conversion rate (impression → vente) | ≥1% | Calculé |
| NPS premiers clients | ≥8/10 | Feedback direct |

---

## 2. Go / No-Go Gates

| Gate | Critère | Si FAIL |
|------|---------|---------|
| Market validation | 10 ventes en 30 jours sans pub payante | Pivoter segment ou pricing |
| Technical feasibility | Export 1000+ pages sans crash | Debug avant launch |
| Legal clearance | Microsoft Graph ToS OK pour commercial | Restructurer (API perso, pas redistribution) |
| User friction | Setup Azure AD < 15 min pour non-tech | Build managed setup service |
| Content quality | Prompt Kit noté ≥4/5 par 3 beta testers | Itérer templates avant launch |

---

## 3. Matrice de risques

| Risque | Probabilité | Impact | Mitigation | Owner |
|--------|-------------|--------|------------|-------|
| Microsoft change Graph API | Low | High | Abstraction layer déjà en place, monitorer deprecation | Tech |
| Azure AD friction tue le funnel | High | High | Multi-tenant app + publisher verification | Tech |
| Pas de market fit (0 ventes) | Medium | High | Pivoter vers B2B service (white-glove setup) | Business |
| Concurrent lance un GUI avant | Medium | Medium | Prompt library = moat non-copiable | Product |
| GDPR exposure (données transitent) | Low | Medium | Documenter que c'est local → Anthropic direct | Legal |
| WeasyPrint LGPL incompatibilité | Low | Low | Vérifier licensing, alternative: Playwright PDF | Tech |

---

## 4. Critères d'évaluation des templates de prompts

| Critère | Poids | Échelle |
|---------|-------|---------|
| Pertinence (résout un vrai problème) | 30% | 1-5 |
| Qualité output (Claude produit un bon résultat) | 25% | 1-5 |
| Réutilisabilité (marche sur différents contenus) | 20% | 1-5 |
| Facilité d'utilisation (variables claires) | 15% | 1-5 |
| Différenciation (pas trouvable gratuitement) | 10% | 1-5 |

**Score minimum pour inclusion dans le kit : 3.5/5**

---

## 5. KPIs par phase

### Phase 1 — MVP (2 semaines)
- Ship speed : prompt kit live sur Gumroad en ≤14 jours
- 5 beta testers recrutés avant launch
- Article LinkedIn publié

### Phase 2 — Friction reduction (4 semaines)
- PyPI package publié
- Multi-tenant Azure app vérifiée
- 30 total ventes

### Phase 3 — CLI Pro (2 mois)
- 10 licenses Pro vendues (€89/an)
- ARR ≥ €1500
- 100+ GitHub stars

### Phase 4 — Desktop (3-4 mois)
- Seulement si Phase 3 ARR ≥ €2000
- Beta desktop avec 10 testeurs
- One-time purchase model validé

---

## 6. Competitive benchmarking

| Outil | OneNote support | AI pipeline | Batch export | Prix | Notre avantage |
|-------|----------------|-------------|--------------|------|----------------|
| onenote-md-exporter (GitHub) | Oui | Non | Partiel | Free | Pipeline AI complet |
| Notion AI | Non (Notion only) | Oui | Non | $10/mo | OneNote natif |
| ChatDoc | Upload PDF | Oui | Non | $6/mo | Extraction batch native |
| Obsidian + plugins | Import manual | Partiel | Non | Free | Zero manual work |
| Notre produit | Natif | Full pipeline | 1163 pages en 5 min | €39 | End-to-end automatisé |

---

## 7. Checklist pre-launch

- [ ] CLI export TXT/PDF/MD fonctionne pour 1000+ pages
- [ ] 20 prompt templates testés et notés ≥3.5/5
- [ ] Guide Azure AD Setup rédigé et testé par un non-dev
- [ ] Gumroad listing créé avec screenshots
- [ ] Article LinkedIn draft revu
- [ ] Readme GitHub avec badges, GIF démo, quick start
- [ ] .env.example et instructions claires
- [ ] License file (MIT) en place
