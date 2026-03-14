# QUIXAI / HEXIS — zeprocess

Formations video > chatbots IA specialises vendus par abonnement.

## Concept

Le contenu de formation (DDP Garconniere = seduction, d'autres a venir) est transcrit, ingere via Hexis (appraisal emotionnel, chunking semantique), embed via Claude Max, et stocke dans pgvector. Les chatbots specialises repondent aux abonnes via RAG + Claude.

[Hexis](https://github.com/QuixiAI/Hexis) = moteur cognitif Postgres-native (memoire 5 couches, heartbeat autonome, 80+ outils).

## Pricing

| Tier | Prix | Acces |
|------|------|-------|
| Solo | 20 EUR/mois | 1 chatbot |
| Team | 90 EUR/mois | Tous, 1X |
| Pro | 180 EUR/mois | Tous, 5X |

Break-even: 3-4 abonnes. Marge 96% a 100 users.

## Stack

- **Hexis** — moteur cognitif (PostgreSQL 16 + pgvector + Apache AGE)
- **Python 3.12** / FastAPI / Pydantic v2
- **Claude Max** — 174 EUR/mois (Haiku, Sonnet, Opus + embeddings)
- **RabbitMQ** — heartbeat workers
- **Redis** — sessions, rate limits, cache
- **Stripe** — abonnements recurrents
- **OVH Dedie** — 8c/32GB/500GB (~100 EUR/mois)

## Structure

```
zeprocess/
├── src/
│   ├── agents/        # 3 chatbots: seduction, closing, acquisition
│   ├── api/           # FastAPI
│   ├── database/      # SQLAlchemy ORM
│   ├── graph/         # LangGraph orchestration
│   └── state/         # Pydantic state
├── agents/            # Implementations (closing/llm, rag, stripe)
├── scripts/           # Pipeline: transcribe, embed, search, MCP
├── config/            # Settings
├── data/raw/          # Formations (DDP Garconniere, 9 modules)
├── infra/             # Docker, Nginx, systemd
├── tests/             # pytest
└── docs/              # 47 fichiers organises
```

## Quick Start

```bash
uv sync
cp .env.example .env
docker-compose -f infra/docker/docker-compose.yml up -d
uvicorn src.api.main:app --reload --port 8000
```

## Tests

```bash
pytest tests/ --cov=src --cov=agents -v
ruff check --fix . && ruff format .
mypy --strict src/
```

## Documentation

[docs/README.md](docs/README.md) — index complet (47 fichiers, 6 sections).

| Section | Fichier cle |
|---------|------------|
| Architecture | [hexis-prod-architecture.md](docs/architecture/hexis-prod-architecture.md) |
| Business | [pricing-and-tiers.md](docs/business/pricing-and-tiers.md) |
| Deploiement | [ovh-production-plan.md](docs/deployment/ovh-production-plan.md) |
| Securite | [hexis-prod-hardening.md](docs/security/hexis-prod-hardening.md) |
| Specs | [auth-stripe-multitenancy.md](docs/specs/auth-stripe-multitenancy.md) |
| Roadmap | [implementation-roadmap-v2.md](docs/status/implementation-roadmap-v2.md) |
| Schemas | [SCHEMAS.html](docs/SCHEMAS.html) — 12 diagrammes Mermaid |
