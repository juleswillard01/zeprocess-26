# Documentation — QUIXAI / HEXIS

Moteur cognitif Hexis + formations video = chatbots IA vendus par abonnement.

## Clarifications

- [clarifications-quixai.txt](clarifications-quixai.txt) — 26 questions repondues sur la mise en prod

## Schemas

- [SCHEMAS.html](SCHEMAS.html) — 12 diagrammes Mermaid interactifs

---

## Architecture

| Fichier | Contenu |
|---------|---------|
| [hexis-prod-architecture.md](architecture/hexis-prod-architecture.md) | Architecture prod OVH, Claude Max, multi-tenant, migration zeprocess |
| [langgraph-orchestration.md](architecture/langgraph-orchestration.md) | Orchestration LangGraph multi-agents |
| [decisions.md](architecture/decisions.md) | Architecture Decision Records |
| [claude-sdk-integration.md](architecture/claude-sdk-integration.md) | Integration Claude SDK |
| [safety-v-code.md](architecture/safety-v-code.md) | Systeme de securite V-Code |

## Business

| Fichier | Contenu |
|---------|---------|
| [pricing-and-tiers.md](business/pricing-and-tiers.md) | Tiers 20/90/180 EUR, unit economics, Stripe, break-even |
| [business-model.md](business/business-model.md) | Modele economique global |
| [prd.md](business/prd.md) | Product Requirements Document |
| [content-strategy-seduction.md](business/content-strategy-seduction.md) | Strategie contenu seduction |
| [pitch-youtube-rag-pipeline.md](business/pitch-youtube-rag-pipeline.md) | Pitch pipeline YouTube RAG |
| [quickstart-usecases.md](business/quickstart-usecases.md) | Cas d'usage |

## Deploiement

| Fichier | Contenu |
|---------|---------|
| [ovh-production-plan.md](deployment/ovh-production-plan.md) | Plan OVH complet (1572 lignes) |
| [ovh-quick-start.md](deployment/ovh-quick-start.md) | Quick start 30 min |
| [architecture-to-deployment.md](deployment/architecture-to-deployment.md) | Mapping archi vers deploiement |

## Securite

| Fichier | Contenu |
|---------|---------|
| [hexis-prod-hardening.md](security/hexis-prod-hardening.md) | Hardening prod (1865 lignes) |
| [codebase-audit.md](security/codebase-audit.md) | Audit OWASP codebase |
| [quick-checklist.md](security/quick-checklist.md) | Checklist securite |
| [migrations.sql](security/migrations.sql) | Migrations securite PostgreSQL |

## Statut

| Fichier | Contenu |
|---------|---------|
| [implementation-roadmap-v2.md](status/implementation-roadmap-v2.md) | Roadmap 8 semaines, 7 phases |
| [phase1-completion.md](status/phase1-completion.md) | Bilan Phase 1 (historique) |

## Specs techniques

| Fichier | Contenu |
|---------|---------|
| [auth-stripe-multitenancy.md](specs/auth-stripe-multitenancy.md) | Auth JWT + Stripe + multi-tenant (1740 lignes, SQL) |
| [agent-seduction/](specs/agent-seduction/) | Specs chatbot Seduction (5 docs) |
| [agent-closing/](specs/agent-closing/) | Specs chatbot Closing (4 docs) |
| [lead-acquisition/](specs/lead-acquisition/) | Specs Lead Acquisition (6 docs) |
| [knowledge-base-rag-architecture.md](specs/knowledge-base-rag-architecture.md) | Architecture RAG |
| [rag-implementation-guide.md](specs/rag-implementation-guide.md) | Guide RAG |
| [rag-implementation-checklist.md](specs/rag-implementation-checklist.md) | Checklist RAG |
| [rag-operations-guide.md](specs/rag-operations-guide.md) | Operations RAG |
| [youtube-rag-pipeline-plan.md](specs/youtube-rag-pipeline-plan.md) | Pipeline YouTube RAG |
| [phase1-completion-status.md](specs/phase1-completion-status.md) | Statut Phase 1 |
| [phase2-plan.md](specs/phase2-plan.md) | Plan Phase 2 |
| [mega-quixai/01-observabilite-langfuse.md](specs/mega-quixai/01-observabilite-langfuse.md) | Observabilite LangFuse |

---

25 fichiers legacy dans [_archive/](_archive/) (zeprocess pre-Hexis).
