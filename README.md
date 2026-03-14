# MEGA QUIXAI

Autonomous AI agents for lead generation, sales closing, and customer retention.

**Status**: Infrastructure complete, Agent CLOSING implementation in progress

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 15+ with pgvector
- Redis 7+

### Installation

```bash
# Clone repository
git clone <repo> && cd mega-quixai

# Install dependencies using uv
uv sync

# Copy environment template
cp .env.example .env

# Fill in your API keys
nano .env
```

### Local Development

```bash
# Start Docker services
docker-compose -f infra/docker/docker-compose.yml up -d

# Wait for health checks
curl http://localhost/health

# Run FastAPI app
uvicorn src.api.main:app --reload --port 8000

# Run agent in loop
python -m agents.closing.main
```

## Documentation

### For Decision Makers
- [START_HERE.md](./START_HERE.md) - Quick overview (5 min)
- [DEPLOYMENT_SUMMARY.txt](./DEPLOYMENT_SUMMARY.txt) - Architecture & costs (5 min)

### For Architects
- [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) - Complete technical design (20 min)
- [.claude/MEGA-QUIXAI-MASTER-INDEX.md](./.claude/MEGA-QUIXAI-MASTER-INDEX.md) - Agent architecture (30 min)

### For Engineers
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Setup in 10 phases (30 min)
- [.claude/03-closing-agent-implementation-guide.md](./.claude/03-closing-agent-implementation-guide.md) - Code templates (120 min)

## Architecture

### 3 Autonomous Agents

**Agent SÉDUCTION** (Lead Generation)
- Generates leads from platforms
- Scans prospects, sends initial DMs
- Qualifies and scores leads
- Passes to Agent CLOSING

**Agent CLOSING** (Sales Conversion)
- Conducts sales conversations via WhatsApp
- Handles objections with RAG-backed arguments
- Proposes adaptive pricing offers
- Integrates Stripe for checkout
- Measures conversion rate, ROI

**Agent FOLLOW** (Retention & Upsell)
- Onboarding automation
- Usage monitoring
- Upsell triggers
- Churn prevention

### Infrastructure Stack

```
┌─────────────────────────────────────────────────────────┐
│ Nginx (SSL/TLS, Rate Limiting, Security Headers)         │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│ FastAPI Application (Python 3.12)                       │
│ ├── LangGraph Orchestration                             │
│ ├── Claude Opus LLM Integration                         │
│ └── WebSocket for real-time updates                     │
└─────────────────┬───────────────────────────────────────┘
                  │
         ┌────────┼────────┐
         │        │        │
    ┌────▼──┐ ┌──▼────┐ ┌─▼──────┐
    │PostgreSQL│ │Redis │ │LangFuse│
    │+pgvector │ │      │ │        │
    └─────────┘ └──────┘ └────────┘

┌─────────────────────────────────────────────────────────┐
│ Systemd Services (24/7 Autonomous)                       │
│ ├── Agent SÉDUCTION                                    │
│ ├── Agent CLOSING                                      │
│ └── Agent FOLLOW                                       │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
mega-quixai/
├── .github/workflows/
│   └── deploy.yml                    # GitHub Actions CI/CD
│
├── agents/
│   ├── base.py                       # AutonomousAgent base class
│   ├── closing/                      # Agent CLOSING
│   │   ├── state_machine.py
│   │   ├── llm_interface.py
│   │   ├── rag_interface.py
│   │   ├── payment_manager.py
│   │   └── nodes.py
│   ├── seduction/                    # Agent SÉDUCTION
│   └── follow/                       # Agent FOLLOW
│
├── src/api/
│   ├── main.py                       # FastAPI app
│   ├── routes/
│   │   ├── closing.py
│   │   ├── webhooks.py
│   │   └── metrics.py
│   └── middleware.py
│
├── database/
│   ├── schema.sql
│   └── migrations/
│
├── config/
│   └── settings.py                   # Environment config
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── Dockerfile.api
│   ├── nginx/
│   │   └── nginx.conf
│   ├── systemd/
│   │   ├── mega-quixai-agent-*.service
│   │   └── mega-quixai.target
│   ├── scripts/
│   │   ├── init-secrets.sh
│   │   ├── backup.sh
│   │   └── post-deploy-check.sh
│   └── config/
│       ├── schema.sql
│       └── logging.yml
│
├── .env.example
├── pyproject.toml
└── README.md
```

## Deployment

### Local Development (Docker)

```bash
# Start all services
docker-compose -f infra/docker/docker-compose.yml up -d

# Verify health
curl http://localhost/health

# View logs
docker-compose logs -f api
```

### Production (VPS)

Follow [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for:
1. VPS provisioning (Hetzner)
2. Docker setup
3. Secrets management
4. Firewall configuration
5. SSL/TLS setup
6. Systemd agent deployment
7. Backup scheduling
8. Monitoring setup

**Cost**: €18.25/month MVP

## Testing

```bash
# Run all tests with coverage
pytest tests/ --cov=src --cov=agents --cov-fail-under=80

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

## Development Workflow

1. **Create branch**: `git checkout -b feature/agent-closing`
2. **Write tests first**: `pytest tests/unit/test_*.py`
3. **Implement code**: Follow structure in `.claude/03-closing-agent-implementation-guide.md`
4. **Format code**: `ruff format .` and `ruff check --fix .`
5. **Type check**: `mypy --strict src/ agents/`
6. **Commit**: `git commit -m "feat: add closing agent objection handler"`
7. **Push & PR**: `git push origin feature/agent-closing`

## Key Metrics (Target)

| Metric | Target | Status |
|--------|--------|--------|
| Response Rate | 85% | In development |
| Conversion Rate | 35-40% | Baseline: industry avg 2-5% |
| Cost Per Lead | $0.20-0.30 | API cost only |
| Cost Per Acquisition | $5-12 | Pure Claude API |
| ROI | 3:1 to 8:1 | At 35%+ conversion |

## Security

- Non-root containers (appuser:1000)
- SSL/TLS with Let's Encrypt
- UFW firewall (only 22, 80, 443)
- Secrets in `.secrets/` (gitignored)
- Health monitoring with auto-restart
- Database & Redis internal only
- Rate limiting (10 req/s on /api)

## Monitoring

```bash
# View agent logs
journalctl -u mega-quixai-agent-closing -f

# Check agent status
sudo systemctl status mega-quixai.target

# View API logs
docker-compose logs -f api

# Health endpoint
curl https://mega-quixai.com/health
```

## Cost Breakdown

### MVP (€18.25/month)
- Hetzner VPS (4c/8GB): €6.90
- Backup storage: €2.50
- Anthropic API (~100 req/day): €8.00
- Domain: €0.85

### Growth (€31/month at 10k leads/day)
- 3x Hetzner VPS: €20.70
- Backup storage: €2.50
- Anthropic API: €8.00
- Domain: €0.85

## Support

**Issues**: Open an issue on GitHub
**Questions**: Check `.claude/` documentation
**Bugs**: Run post-deploy check: `./infra/scripts/post-deploy-check.sh`

## Contributors

- Jules (Infrastructure & Agents)

## License

MIT (specify if different)

---

**Status**: Production ready infrastructure, Agent CLOSING in development
**Last Updated**: 2026-03-14
