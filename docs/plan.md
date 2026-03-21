# Plan Produit — OneNote AI Kit

## Vision

Transformer le CLI OneNote Exporter en un produit commercialisable : export batch, pipeline AI, et bibliothèque de prompts. L'objectif est de capitaliser sur la friction technique (setup Azure AD, export propre, prompting structuré) pour créer de la valeur monétisable auprès de professionnels du savoir.

---

## Segments cibles

### Priorité 1 — Consultants / Strategy firms
- **Pain** : knowledge retrieval lent pour accélérer les deliverables ; les notes OneNote sont le seul endroit où tout est centralisé mais impossible à exploiter en batch
- **Budget** : 5/5 — un jour de consulting couvre le coût de l'outil
- **Acquisition** : LinkedIn organique, conférences, bouche à oreille
- **Message** : "Retrouvez n'importe quel insight en 30 secondes"

### Priorité 2 — Coaches indépendants
- **Pain** : extraire des patterns de milliers de notes de sessions clients pour construire des frameworks réutilisables
- **Budget** : 3/5 — solo mais facturation B2B possible
- **Acquisition** : communautés tight, trust-based (ICF, coaching Discord)
- **Message** : "Transformez vos notes en capital intellectuel"

### Priorité 3 — Chercheurs / PhD (early adopters, pas revenue prioritaire)
- Valeur : feedback rapide, cas d'usage edge, ambassadeurs techniques
- Ne pas sur-investir commercialement avant validation

### Priorité 4 — Corporate L&D (bon plafond de revenu, cycle de vente long)
- À adresser en Phase 4+ uniquement, après product-market fit démontré sur P1/P2

---

## Pricing ladder

| Tier | Prix | Contenu |
|------|------|---------|
| Free | 0 | CLI OSS, export TXT / PDF / MD |
| Prompt Kit | 39 € one-time | 20 templates + guide + pipeline script |
| CLI Pro | 89 € / an | Scheduled exports, multi-AI backend, incremental sync |
| Team | 299 € / an | 5 seats, Azure app partagée |
| White-glove B2B | 2 000 € / trimestre | Setup + prompts personnalisés + support dédié |

Logique de la ladder : chaque palier réduit une friction spécifique. Free réduit la friction technique d'entrée. Prompt Kit monétise le gain de productivité immédiat. CLI Pro monétise l'automatisation. Team monétise la collaboration. B2B monétise le support et la customisation.

---

## MVP — 2 semaines

### Semaine 1 : Produit
1. Ajouter `--format md` — export Markdown, meilleur ratio token/contenu pour les LLM
2. Créer 10 à 20 templates de prompts (consulting, coaching, research) avec variables et instructions d'usage
3. Rédiger le guide "Quick Start + Azure AD Setup en 10 min" — objectif zéro abandon à l'étape auth
4. Écrire un script pipeline end-to-end : export → concat → appel Claude API → output structuré

### Semaine 2 : Distribution
1. Créer le listing Gumroad "OneNote AI Kit — Export, Prompt & Analyze" à 39 €
2. Publier un article LinkedIn case study ciblant les consultants (avant/après concret)
3. Poster dans 3 à 5 communautés pertinentes (Reddit r/Notion, Discord consulting, PhD communities)
4. Objectif : 5 premiers clients payants + collecte de feedback structuré

---

## Roadmap

### Phase 1 — Prompt Kit (2 semaines)
- Livrables : export Markdown, bibliothèque de 20 prompts, guide setup, script pipeline
- Canal : Gumroad + LinkedIn
- Indicateur de succès : 5 ventes à 39 €, 3 retours qualitatifs

### Phase 2 — Friction reduction (4 semaines)
- Multi-tenant Azure app avec `AZURE_CLIENT_ID` par défaut dans le package
- Publication sur PyPI (`onenote-exporter`) — installation en une commande
- Documentation complète sur GitHub (SEO, communauté)
- Indicateur de succès : 50 installs PyPI / semaine

### Phase 3 — CLI Pro (2 mois)
- Incremental sync (ne re-exporter que les pages modifiées)
- Scheduled exports (cron-based)
- Support multi-AI backend (Claude, GPT-4, Mistral)
- Indicateur de succès : 10 abonnements CLI Pro actifs

### Phase 4 — Desktop App (3 à 4 mois, conditionnel)
- Déclencheur : ARR > 2 000 €
- Tauri GUI avec visual hierarchy browser
- Supprimer la friction CLI pour les non-développeurs
- Indicateur de succès : conversion CLI → Desktop > 30 %

### Phase 5 — SaaS (conditionnel Phase 4 validée)
- Déclencheur : product-market fit démontré sur Phase 4
- Redesign auth complet (OAuth flow sans Azure app locale)
- Infrastructure cloud, facturation récurrente managée
- Ne pas engager avant validation explicite de Phase 4

---

## Distribution

| Canal | Rôle | Priorité |
|-------|------|----------|
| PyPI (`onenote-exporter`) | Installation, découverte développeurs | Phase 2 |
| GitHub OSS | SEO, communauté, confiance | Maintenant |
| Gumroad | Prompt Kit, licensing one-time | Phase 1 |
| LinkedIn | B2B organique, case studies | Phase 1 |
| Microsoft AppSource | Enterprise, long terme | Phase 4+ |

---

## Insight clé : résoudre la friction Azure AD

Le principal point d'abandon est la création d'une Azure app registration. La solution : publier l'outil comme application multi-tenant avec un `AZURE_CLIENT_ID` par défaut intégré dans le package.

Flux utilisateur cible :
```
pip install onenote-exporter
onenote-export auth         # → browser login, ça marche
onenote-export tree         # → hiérarchie visible
onenote-export export ...   # → fichiers locaux
```

Prérequis technique : passer la vérification publisher Microsoft (Microsoft 365 Developer Program + domaine vérifié). Estimé à 1 à 2 semaines de démarches. Débloquer en priorité pour Phase 2.

---

## Cadre légal

- **Microsoft Graph API** : usage commercial autorisé pour CLI (les utilisateurs s'authentifient contre leur propre tenant, pas d'intermédiaire)
- **WeasyPrint** : licence LGPL, compatible usage commercial via dynamic linking (pip install)
- **GDPR** : pas de stockage intermédiaire — les données vont directement de OneNote (Microsoft) vers le LLM choisi (Anthropic, OpenAI, etc.) ; aucune donnée ne transite par notre infrastructure
- **Tokens OAuth** : stockés en mémoire uniquement, jamais sur disque (cf. règle sécurité)
