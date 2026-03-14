# MEGA QUIXAI - Quick Reference

**Jump to what you need:**

## 🚀 I Want to Deploy

1. **First time?** → Read [START_HERE.md](./START_HERE.md) (5 min)
2. **Setup locally?** → [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) Phase 1-5 (1 hour)
3. **Deploy to VPS?** → [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) Phase 6-10 (1 hour)
4. **Verify?** → Run `./infra/scripts/post-deploy-check.sh`

## 👨‍💻 I Want to Code

### Start Here
1. Read [DEVELOPMENT_ROADMAP.md](./DEVELOPMENT_ROADMAP.md) (15 min)
2. Review [.claude/03-closing-agent-implementation-guide.md](./.claude/03-closing-agent-implementation-guide.md) (120 min)
3. Create `agents/closing/nodes.py` (follow template)
4. Write tests in `tests/unit/test_nodes.py`
5. Run: `pytest tests/ --cov-fail-under=80`

### Quick Commands
```bash
# Install dependencies
uv sync

# Run tests
pytest tests/ -v

# Format code
ruff format . && ruff check --fix .

# Type check
mypy --strict src/ agents/

# Start API (dev)
uvicorn src.api.main:app --reload

# Start Docker services
docker-compose -f infra/docker/docker-compose.yml up -d
```

## 🏗️ I Want to Understand Architecture

1. **30 seconds?** → Read "Architecture Summary" in [COMPLETION_SUMMARY.md](./COMPLETION_SUMMARY.md)
2. **5 minutes?** → Read [DEPLOYMENT_SUMMARY.txt](./DEPLOYMENT_SUMMARY.txt)
3. **20 minutes?** → Read [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) (sections 1-3)
4. **1 hour?** → Read [.claude/02-agent-closing-architecture.md](./.claude/02-agent-closing-architecture.md)

## 📊 I Want to See Metrics

**Key Targets** (see COMPLETION_SUMMARY.md):
- Response Rate: 85%
- Conversion Rate: 35-40% (vs industry avg 2-5%)
- Cost Per Lead: $0.20-0.30
- Cost Per Acquisition: $5-12
- ROI: 3:1 to 8:1

**Track via**:
- LangFuse dashboard (configured)
- agents/closing/analytics.py (Phase 2)
- Database metrics tables

## 🔧 I Have a Problem

| Problem | Solution |
|---------|----------|
| API won't start | `docker-compose logs api` |
| Agent stuck | `journalctl -u mega-quixai-* -f` |
| Database error | `docker-compose restart postgres` |
| Tests failing | `pytest tests/ -v --tb=short` |
| Port in use | `lsof -i :8000` then `kill -9 <pid>` |
| Low coverage | Add tests to `tests/unit/` |

## 📁 File Structure at a Glance

```
MEGA QUIXAI/
├── START_HERE.md              ← Read this first
├── COMPLETION_SUMMARY.md      ← What's been done
├── DEVELOPMENT_ROADMAP.md     ← Phase 2 plan
├── QUICK_REFERENCE.md         ← This file
│
├── infra/                     ← Infrastructure (Deploy Guide Phase 5-10)
│   ├── docker/
│   ├── nginx/
│   ├── systemd/
│   ├── scripts/
│   └── config/
│
├── agents/                    ← Agent implementations
│   ├── base.py               ← AutonomousAgent base class
│   ├── closing/              ← Agent CLOSING (Phase 2 focus)
│   │   ├── state_machine.py
│   │   ├── llm_interface.py
│   │   ├── rag_interface.py
│   │   └── payment_manager.py
│   ├── seduction/            ← Agent SÉDUCTION (Phase 1)
│   └── follow/               ← Agent FOLLOW (Phase 3)
│
├── src/api/                  ← FastAPI application
│   └── main.py
│
├── config/                   ← Configuration
│   └── settings.py
│
├── tests/                    ← Test suite (80% coverage gate)
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── conftest.py
│
├── .env.example              ← Configuration template
├── pyproject.toml            ← Dependencies
└── .github/workflows/        ← CI/CD
    └── deploy.yml
```

## 🎯 What's Done vs TODO

### ✅ Done (Infrastructure Phase)
- [x] Docker Compose (5 services)
- [x] systemd service units
- [x] Nginx reverse proxy
- [x] CI/CD pipeline
- [x] PostgreSQL schema
- [x] Security hardening
- [x] Backup & recovery
- [x] Documentation

### ✅ Done (Agent CLOSING Phase 1)
- [x] State machine definition
- [x] LLM interface (Claude)
- [x] RAG interface (pgvector)
- [x] Payment manager (Stripe)
- [x] FastAPI skeleton
- [x] Test framework
- [x] Configuration system

### 🔄 In Progress (Phase 2)
- [ ] LangGraph node implementation (5 nodes)
- [ ] Tools layer (5 tools)
- [ ] Prompt templates (20+)
- [ ] Integration tests
- [ ] Observability

### ⏳ TODO (Phase 3+)
- [ ] Agent FOLLOW (retention)
- [ ] Load testing
- [ ] Prompt optimization
- [ ] Production monitoring

## 💰 Costs

**MVP**: €18.25/month
- VPS: €6.90
- Storage: €2.50
- API (Claude): €8.00
- Domain: €0.85

**At Scale**: €31/month @ 10k leads/day

## 🔗 Key Documentation

| Document | Purpose | Time |
|----------|---------|------|
| [START_HERE.md](./START_HERE.md) | Quick overview | 5 min |
| [DEPLOYMENT_SUMMARY.txt](./DEPLOYMENT_SUMMARY.txt) | Architecture & costs | 5 min |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | Setup steps | 30 min |
| [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) | Technical deep dive | 20 min |
| [DEVELOPMENT_ROADMAP.md](./DEVELOPMENT_ROADMAP.md) | Phase 2 plan | 15 min |
| [COMPLETION_SUMMARY.md](./COMPLETION_SUMMARY.md) | Full status | 10 min |
| [.claude/02-agent-closing-architecture.md](./.claude/02-agent-closing-architecture.md) | Agent design | 60 min |
| [.claude/03-closing-agent-implementation-guide.md](./.claude/03-closing-agent-implementation-guide.md) | Code templates | 120 min |

## 🚢 Deployment Timeline

```
Week 1 (Infrastructure)
├── Day 1-2: VPS provisioning + Docker setup (2 hours)
├── Day 2-3: Secrets + Firewall (1 hour)
└── Day 3-5: Verify + Monitoring (1 hour)
→ Infrastructure ready ✅

Week 2-3 (Agent CLOSING Nodes)
├── Day 1-2: node_init implementation
├── Day 3-4: node_converse + objection_handling
├── Day 5: Tools + LangGraph builder
└── Day 6-7: Testing + fixes
→ Agent CLOSING MVP ready ✅

Week 4+ (Production)
├── Load testing
├── Prompt optimization
└── Monitoring setup
→ Live production 🚀
```

## 👥 Team Roles

**DevOps**: Run [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md), maintain infra/
**Backend**: Implement [DEVELOPMENT_ROADMAP.md](./DEVELOPMENT_ROADMAP.md), agents/closing/nodes.py
**QA**: Add tests in tests/unit/ and tests/integration/
**Product**: Monitor metrics in .claude/04-closing-agent-use-cases-and-diagrams.md

## ❓ FAQ

**Q: Where do I start?**
A: Read START_HERE.md, then choose your role above.

**Q: How long to deploy?**
A: 2-3 hours locally, same on VPS with DEPLOYMENT_GUIDE.md

**Q: How much does it cost?**
A: €18.25/month MVP. No setup fees, cancel anytime.

**Q: When is it production-ready?**
A: Infrastructure now. Agent CLOSING: after Phase 2 (2-3 weeks).

**Q: Can I scale?**
A: Yes. Vertical (upgrade VPS) or horizontal (3x VPS). See INFRASTRUCTURE.md section 7.

**Q: How do I monitor?**
A: Health checks, logs, LangFuse dashboard, systemd status.

**Q: What if I find a bug?**
A: File issue on GitHub. Check logs with `docker-compose logs -f` or `journalctl -f`.

---

**Status**: Infrastructure ✅ Complete | Agent CLOSING 🔄 Phase 2 | MVP 📅 4-5 weeks

**Last updated**: 2026-03-14 | **Owner**: Jules | **Questions?** See docs above
