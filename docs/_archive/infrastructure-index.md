# MEGA QUIXAI Infrastructure Files — Complete Index

All infrastructure files for deploying 3 autonomous AI agents (Séduction, Closing, Lead Acquisition) on a single VPS.

---

## Documentation (Read First)

| File | Purpose | Read Time |
|------|---------|-----------|
| **[DEPLOYMENT_SUMMARY.txt](./DEPLOYMENT_SUMMARY.txt)** | Overview of everything | 5 min |
| **[INFRASTRUCTURE.md](./INFRASTRUCTURE.md)** | Full technical architecture | 20 min |
| **[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)** | Step-by-step setup (10 phases) | 30 min |
| **[infra/README.md](./infra/README.md)** | Quick reference | 5 min |

**Recommended Reading Order**: DEPLOYMENT_SUMMARY → INFRASTRUCTURE → DEPLOYMENT_GUIDE

---

## Docker Configuration

| Path | Purpose |
|------|---------|
| **[infra/docker/docker-compose.yml](./infra/docker/docker-compose.yml)** | 5 services: nginx, api, postgres, redis, langfuse |
| **[infra/docker/Dockerfile.api](./infra/docker/Dockerfile.api)** | Multi-stage Python 3.12 build, non-root user |

**Usage**:
```bash
cd infra/docker
docker-compose up -d
docker-compose ps
```

---

## Reverse Proxy & SSL

| Path | Purpose |
|------|---------|
| **[infra/nginx/nginx.conf](./infra/nginx/nginx.conf)** | Nginx config: SSL/TLS, rate limiting, security headers |

**Features**:
- SSL/TLS termination (ports 80/443)
- Rate limiting (10 req/s on /api)
- Security headers (HSTS, X-Frame-Options, etc.)
- Upstream proxy to api:3000

---

## Systemd Services (Autonomous Agents)

| Path | Purpose |
|------|---------|
| **[infra/systemd/mega-quixai-agent-seduction.service](./infra/systemd/mega-quixai-agent-seduction.service)** | Seduction agent (24/7 autonomous) |
| **[infra/systemd/mega-quixai-agent-closing.service](./infra/systemd/mega-quixai-agent-closing.service)** | Closing agent (24/7 autonomous) |
| **[infra/systemd/mega-quixai-agent-acquisition.service](./infra/systemd/mega-quixai-agent-acquisition.service)** | Lead acquisition agent (24/7 autonomous) |
| **[infra/systemd/mega-quixai.target](./infra/systemd/mega-quixai.target)** | Orchestrator (start/stop all agents together) |

**Features**:
- Auto-restart on failure (RestartSec=5s)
- Memory limit (1GB per agent)
- CPU quota (50%)
- Logging to systemd journal
- Dependencies on Docker services

**Usage**:
```bash
sudo cp infra/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start mega-quixai.target
sudo journalctl -u mega-quixai.target -f
```

---

## Deployment Scripts

| Path | Purpose | Run As |
|------|---------|--------|
| **[infra/scripts/init-secrets.sh](./infra/scripts/init-secrets.sh)** | Generate .secrets/ (passwords, API keys) | quixai user |
| **[infra/scripts/setup-firewall.sh](./infra/scripts/setup-firewall.sh)** | Configure UFW firewall (22, 80, 443) | root (via sudo) |
| **[infra/scripts/backup.sh](./infra/scripts/backup.sh)** | Daily PostgreSQL backup to /var/backups/ | quixai user (cron) |
| **[infra/scripts/post-deploy-check.sh](./infra/scripts/post-deploy-check.sh)** | Verify deployment (health checks, services) | root (via sudo) |

**Usage**:
```bash
# Initialize secrets
./infra/scripts/init-secrets.sh

# Setup firewall
sudo ./infra/scripts/setup-firewall.sh

# Schedule backups (in quixai crontab)
0 2 * * * /opt/mega-quixai/infra/scripts/backup.sh

# Run verification
sudo ./infra/scripts/post-deploy-check.sh
```

---

## Configuration Files

| Path | Purpose |
|------|---------|
| **[infra/config/schema.sql](./infra/config/schema.sql)** | PostgreSQL schema + pgvector setup |
| **[infra/config/logging.yml](./infra/config/logging.yml)** | Centralized logging config (JSON format) |
| **[infra/.env.example](./infra/.env.example)** | Environment variables template (copy to parent .env) |

**Usage**:
```bash
# Copy env template
cp infra/.env.example .env
nano .env  # Edit with your settings

# Schema is auto-applied on first docker-compose up
```

---

## CI/CD Pipeline

| Path | Purpose |
|------|---------|
| **[.github/workflows/deploy.yml](./.github/workflows/deploy.yml)** | GitHub Actions: lint → test → build → deploy |

**Pipeline Stages**:
1. **Lint** (ruff): Check code style, imports
2. **Test** (pytest): Unit tests, coverage >= 80%
3. **Build** (Docker): Multi-stage, push to ghcr.io
4. **Deploy** (SSH): Manual approval, pull + restart

**Triggers**:
- Push to `main` → All stages + deploy (approval required)
- Push to `staging` → Lint, test, build
- PR to `main` → Lint, test

**Required GitHub Secrets**:
- `PROD_DEPLOY_KEY`: SSH private key
- `PROD_DEPLOY_HOST`: VPS IP or hostname

---

## Agent Code

| Path | Purpose |
|------|---------|
| **[agents/base.py](./agents/base.py)** | AutonomousAgent base class (implement your agents from this) |

**How to Use**:
```python
from agents.base import AutonomousAgent
import asyncio

class SeductionAgent(AutonomousAgent):
    async def execute_iteration(self, state):
        # Your logic here
        return state

# Create and run
agent = SeductionAgent(name="seduction", redis_client=redis)
await agent.run_forever()
```

---

## Directory Structure

```
/opt/mega-quixai/
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml         ← Start all services
│   │   └── Dockerfile.api             ← Build API image
│   ├── nginx/
│   │   └── nginx.conf                 ← Reverse proxy config
│   ├── systemd/
│   │   ├── mega-quixai-agent-seduction.service
│   │   ├── mega-quixai-agent-closing.service
│   │   ├── mega-quixai-agent-acquisition.service
│   │   └── mega-quixai.target         ← Orchestrator
│   ├── scripts/
│   │   ├── init-secrets.sh            ← Setup .secrets/
│   │   ├── setup-firewall.sh          ← UFW rules
│   │   ├── backup.sh                  ← Daily backup
│   │   └── post-deploy-check.sh       ← Verify deployment
│   ├── config/
│   │   ├── schema.sql                 ← Database schema
│   │   ├── logging.yml                ← Logging config
│   │   └── .env.example               ← Environment template
│   └── README.md                      ← Quick reference
│
├── .github/
│   └── workflows/
│       └── deploy.yml                 ← CI/CD pipeline
│
├── agents/
│   └── base.py                        ← AutonomousAgent base class
│
├── INFRASTRUCTURE.md                  ← Full technical guide
├── DEPLOYMENT_GUIDE.md                ← Step-by-step setup
├── DEPLOYMENT_SUMMARY.txt             ← This overview
└── INFRASTRUCTURE_INDEX.md            ← File index (you are here)
```

---

## Key File Locations

**Secrets** (never committed):
```
/opt/mega-quixai/.secrets/
├── pg_password.txt          (auto-generated)
├── anthropic_key.txt        (from prompt)
└── langfuse_secret.txt      (from prompt)
```

**Environment**:
```
/opt/mega-quixai/.env         (copy from .env.example)
```

**Systemd**:
```
/etc/systemd/system/mega-quixai*.service
/etc/systemd/system/mega-quixai.target
```

**SSL/TLS**:
```
/opt/mega-quixai/infra/ssl/
├── fullchain.pem            (from Let's Encrypt)
└── privkey.pem              (from Let's Encrypt)
```

**Backups**:
```
/var/backups/mega-quixai/
└── mega-quixai-full-YYYYMMDD-HHMMSS.sql.gz
```

**Logs**:
```
/var/log/mega-quixai/
├── app.log                  (API logs)
├── agents.log               (Agent logs)
└── nginx/                   (Nginx logs)
```

---

## Quick Start

### 1. Read Documentation (15 min)
```bash
cat DEPLOYMENT_SUMMARY.txt
less INFRASTRUCTURE.md
less DEPLOYMENT_GUIDE.md
```

### 2. Provision VPS (10 min)
- Go to Hetzner Cloud
- Create Ubuntu 24.04 LTS, 4 cores, 8GB RAM, 100GB SSD
- Note the IP address

### 3. Run Setup Script (30 min)
```bash
# SSH to VPS
ssh root@<VPS_IP>

# Clone repo
git clone https://github.com/your-org/mega-quixai.git /opt/mega-quixai
cd /opt/mega-quixai

# Initialize secrets
./infra/scripts/init-secrets.sh

# Setup firewall
sudo ./infra/scripts/setup-firewall.sh

# Start Docker services
cd infra/docker && docker-compose up -d
```

### 4. Deploy Agents (20 min)
```bash
# Copy systemd files
sudo cp infra/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload

# Start agents
sudo systemctl start mega-quixai.target
sudo systemctl enable mega-quixai.target

# Verify
sudo systemctl status mega-quixai.target
```

### 5. Verify (5 min)
```bash
# Run checks
sudo ./infra/scripts/post-deploy-check.sh

# Should see all green
```

**Total Time**: ~2 hours

---

## Troubleshooting

### Can't find a file?
```bash
find /opt/mega-quixai -name "*filename*" -type f
```

### Agent not starting?
```bash
sudo journalctl -u mega-quixai-agent-seduction -n 50
docker-compose logs postgres
curl http://localhost/health
```

### Health check failing?
```bash
docker-compose ps
docker exec mega-quixai-postgres pg_isready -U quixai_user
docker exec mega-quixai-redis redis-cli ping
```

### Need to restart everything?
```bash
sudo systemctl restart mega-quixai.target
docker-compose restart
```

---

## File Sizes

```
INFRASTRUCTURE.md          ~40 KB   (complete architecture)
DEPLOYMENT_GUIDE.md        ~45 KB   (10 phases, step-by-step)
docker-compose.yml         ~4 KB    (5 services)
nginx.conf                 ~3 KB    (reverse proxy)
Dockerfile.api             ~1 KB    (multi-stage build)
schema.sql                 ~2 KB    (PostgreSQL + pgvector)
agent-seduction.service    ~1 KB    (systemd unit)
deploy.yml                 ~2 KB    (GitHub Actions)
```

---

## Next Steps

1. **Read**: DEPLOYMENT_SUMMARY.txt (5 min)
2. **Review**: INFRASTRUCTURE.md (20 min)
3. **Plan**: DEPLOYMENT_GUIDE.md phase by phase (30 min)
4. **Execute**: Follow DEPLOYMENT_GUIDE.md (2-3 hours)
5. **Monitor**: Check /var/log and systemd journals
6. **Implement**: Create your 3 agent classes inheriting from agents/base.py
7. **Test**: Push to main, watch GitHub Actions deploy
8. **Monitor**: Setup Grafana dashboards for observability

---

## Support

For questions:
1. Check logs: `docker-compose logs -f service_name`
2. Check systemd: `journalctl -u mega-quixai-* -f`
3. Run verification: `sudo ./infra/scripts/post-deploy-check.sh`
4. Review relevant guide (INFRASTRUCTURE.md or DEPLOYMENT_GUIDE.md)

---

## Cost Summary

| Component | Cost |
|-----------|------|
| VPS (Hetzner 4c/8GB) | €6.90/month |
| Backups | €2.50/month |
| API calls | ~€8/month |
| Domain | ~€0.85/month |
| **TOTAL** | **~€18.25/month** |

Scales to 10k+ leads/day at ~€31/month (3 VPS).

---

**Created**: 2026-03-14  
**Stack**: Python 3.12, Docker, PostgreSQL+pgvector, Redis, systemd  
**Status**: Production-ready
