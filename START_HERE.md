# MEGA QUIXAI Infrastructure — START HERE

Complete infrastructure for deploying 3 autonomous AI agents (Séduction, Closing, Lead Acquisition) on a single VPS.

**Status**: Ready for production deployment  
**Cost**: €18.25/month (MVP)  
**Time to deploy**: 2-3 hours

---

## What You Need to Know

### 3 Files to Read (1 hour total)

1. **[DEPLOYMENT_SUMMARY.txt](./DEPLOYMENT_SUMMARY.txt)** — 5 min
   - Overview of architecture, services, security
   - Cost breakdown: €18/month MVP
   - Key features and monitoring setup

2. **[INFRASTRUCTURE.md](./INFRASTRUCTURE.md)** — 20 min
   - Complete technical architecture
   - Docker Compose services (nginx, api, postgres, redis, langfuse)
   - Systemd units for 3 autonomous agents
   - Security, scaling, monitoring details

3. **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** — 30 min
   - Step-by-step setup in 10 phases
   - What to run at each phase
   - Troubleshooting for common issues

### Then Deploy (2-3 hours)

**Phase 1: VPS Setup** (30 min)
```bash
# Provision Hetzner VPS: 4 cores, 8GB RAM, 100GB SSD, €6.90/month
# SSH in and clone repo
git clone https://github.com/your-org/mega-quixai.git /opt/mega-quixai
```

**Phase 2-3: Secrets & Firewall** (25 min)
```bash
cd /opt/mega-quixai
./infra/scripts/init-secrets.sh
sudo ./infra/scripts/setup-firewall.sh
```

**Phase 4-5: Docker & SSL** (35 min)
```bash
cd infra/docker
docker-compose up -d
# Wait for health checks to pass
curl http://localhost/health
```

**Phase 6-7: Agents & Backups** (25 min)
```bash
sudo cp infra/systemd/* /etc/systemd/system/
sudo systemctl start mega-quixai.target
sudo systemctl enable mega-quixai.target
```

**Phase 8-10: Verify & Monitor** (15 min)
```bash
sudo ./infra/scripts/post-deploy-check.sh
curl https://mega-quixai.com/health
```

---

## What Gets Created

| Component | Technology | Status |
|-----------|-----------|--------|
| **Reverse Proxy** | Nginx + SSL/TLS | ✓ Ready |
| **API Server** | FastAPI (Python 3.12) | ✓ Ready (need implementation) |
| **Database** | PostgreSQL 15 + pgvector | ✓ Ready |
| **Cache** | Redis 7 | ✓ Ready |
| **Observability** | LangFuse + logging | ✓ Ready |
| **Agents** | 3x systemd services (24/7) | ✓ Framework ready (need implementation) |
| **CI/CD** | GitHub Actions | ✓ Ready |
| **Monitoring** | Health checks + logs | ✓ Ready |
| **Security** | Firewall + SSL + rate limiting | ✓ Ready |
| **Backups** | Daily PostgreSQL dumps | ✓ Ready (cron job) |

---

## Files Overview

### Documentation (5 files)

```
START_HERE.md                     ← You are here
DEPLOYMENT_SUMMARY.txt            (5 min read) - Overview
INFRASTRUCTURE.md                 (20 min read) - Full architecture
DEPLOYMENT_GUIDE.md               (30 min read) - Step-by-step
REQUIREMENTS_CHECKLIST.md         (10 min read) - What you're getting
INFRASTRUCTURE_INDEX.md           (10 min read) - File index
```

### Infrastructure (18 files)

```
infra/
├── docker/
│   ├── docker-compose.yml        (5 services with health checks)
│   └── Dockerfile.api            (Python 3.12, non-root)
├── nginx/
│   └── nginx.conf                (SSL/TLS, rate limiting, security)
├── systemd/
│   ├── mega-quixai-agent-seduction.service
│   ├── mega-quixai-agent-closing.service
│   ├── mega-quixai-agent-acquisition.service
│   └── mega-quixai.target        (orchestrator)
├── scripts/
│   ├── init-secrets.sh           (generate .secrets/)
│   ├── setup-firewall.sh         (UFW rules)
│   ├── backup.sh                 (daily backups)
│   └── post-deploy-check.sh      (verification)
├── config/
│   ├── schema.sql                (PostgreSQL schema)
│   ├── logging.yml               (centralized logging)
│   └── .env.example              (environment template)
└── README.md                     (quick reference)

.github/
└── workflows/
    └── deploy.yml                (GitHub Actions: lint → test → build → deploy)

agents/
└── base.py                       (AutonomousAgent abstract class)
```

---

## Architecture at a Glance

```
Internet
   ↓ (ports 80/443)
Nginx (SSL/TLS termination)
   ↓
API Server (FastAPI)
   ├→ PostgreSQL 15 + pgvector (internal)
   ├→ Redis 7 (internal)
   └→ LangFuse (internal)

Systemd Services (24/7):
   ├→ Agent Seduction (autonomous)
   ├→ Agent Closing (autonomous)
   └→ Agent Acquisition (autonomous)

Monitoring:
   ├→ Health checks (30s interval)
   ├→ Redis heartbeat
   ├→ Centralized logs
   └→ Systemd journal
```

**Cost**: €18.25/month (scales to €31/month at 10k leads/day)

---

## Quick Commands

```bash
# Start everything
docker-compose -f infra/docker/docker-compose.yml up -d

# Check status
docker-compose ps
curl http://localhost/health

# Start agents
sudo systemctl start mega-quixai.target
sudo systemctl status mega-quixai.target

# View logs
docker-compose logs -f api
sudo journalctl -u mega-quixai-agent-seduction -f

# Backup database
/opt/mega-quixai/infra/scripts/backup.sh

# Verify deployment
sudo /opt/mega-quixai/infra/scripts/post-deploy-check.sh
```

---

## Security Features

- Non-root containers (appuser:1000)
- SSL/TLS with Let's Encrypt (auto-renewal)
- UFW firewall (only 22, 80, 443 open)
- Database + Redis isolated (internal only)
- Rate limiting (10 req/s on /api)
- Security headers (HSTS, CSP, X-Frame-Options)
- Secrets in .secrets/ (gitignored)
- Health monitoring with auto-restart

---

## Your Implementation Tasks

What you still need to do:

1. **Create Agent Classes** (inherit from `agents.base.AutonomousAgent`)
   - `agents/seduction/main.py` — Seduction agent logic
   - `agents/closing/main.py` — Closing agent logic
   - `agents/acquisition/main.py` — Lead acquisition logic

2. **Create API Endpoints** (`src/api/main.py`)
   - REST endpoints for lead management
   - Integration with agents
   - Webhook endpoints if needed

3. **Configure GitHub Secrets**
   - `PROD_DEPLOY_KEY` — SSH private key
   - `PROD_DEPLOY_HOST` — VPS IP/hostname

4. **Test & Deploy**
   - Push to `main` branch
   - GitHub Actions will run lint → test → build → deploy (approval needed)

---

## Support Resources

### If Something Goes Wrong

1. **Check logs** (choose one):
   ```bash
   docker-compose logs -f api          # API logs
   docker-compose logs -f postgres     # Database logs
   journalctl -u mega-quixai-* -f      # Agent logs
   ```

2. **Run verification**:
   ```bash
   sudo ./infra/scripts/post-deploy-check.sh
   ```

3. **Review guides**:
   - INFRASTRUCTURE.md (full technical details)
   - DEPLOYMENT_GUIDE.md (step-by-step with troubleshooting)
   - INFRASTRUCTURE_INDEX.md (file reference)

### Common Issues

| Problem | Solution |
|---------|----------|
| Docker won't start | Check Docker daemon is running |
| Agent stuck in restart | Check logs: `journalctl -u mega-quixai-*` |
| Database connection refused | `docker-compose restart postgres` |
| Port already in use | `lsof -i :3000` then kill process |
| Disk full | `find /var/log -mtime +30 -delete` |

---

## Timeline

**Before You Start**
- [ ] Read DEPLOYMENT_SUMMARY.txt (5 min)
- [ ] Read INFRASTRUCTURE.md (20 min)
- [ ] Skim DEPLOYMENT_GUIDE.md (10 min)

**Week 1: Infrastructure** (2-3 hours)
- [ ] Provision Hetzner VPS
- [ ] Run Phase 1-7 of deployment guide
- [ ] Verify health checks pass

**Week 2: Agents** (4 hours)
- [ ] Implement 3 agent classes
- [ ] Deploy systemd services
- [ ] Test restart behavior

**Week 3: CI/CD** (2 hours)
- [ ] Configure GitHub secrets
- [ ] Test deployment pipeline
- [ ] Monitor first deploy

**Week 4: Go Live**
- [ ] Load testing
- [ ] Setup alerts
- [ ] Monitor production

---

## Cost Breakdown

### MVP (€18.25/month)

```
Hetzner VPS (4c/8GB)        €6.90
Backup storage              €2.50
Anthropic API (~100 req/day) €8.00
Domain (.com)               €0.85
────────────────────────────────
TOTAL                       €18.25
```

### Growth (€31/month at 10k leads/day)

```
3x Hetzner VPS              €20.70
Backup storage              €2.50
Anthropic API               €8.00
Domain                      €0.85
────────────────────────────────
TOTAL                       €32.05
```

No setup fees, can cancel anytime.

---

## What This Gives You

✓ **Autonomous Agents**: 3 agents run 24/7, auto-restart on failure  
✓ **Scalable**: Vertical (upgrade VPS) or horizontal (add more VPS)  
✓ **Observable**: Health checks, logs, metrics, alerts  
✓ **Secure**: SSL/TLS, firewall, secrets management  
✓ **Reliable**: Auto-backups, disaster recovery procedure  
✓ **Automated**: CI/CD pipeline for deployments  
✓ **Cost-Effective**: ~€18/month MVP, transparent costs  

---

## Next Action

1. Read **[DEPLOYMENT_SUMMARY.txt](./DEPLOYMENT_SUMMARY.txt)** (5 min)
2. Read **[INFRASTRUCTURE.md](./INFRASTRUCTURE.md)** (20 min)
3. Follow **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** (2-3 hours)

---

**Questions?** See INFRASTRUCTURE_INDEX.md for file locations and quick reference.

**Ready to deploy?** Jump to DEPLOYMENT_GUIDE.md Phase 1.

