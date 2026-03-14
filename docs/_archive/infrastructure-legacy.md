# MEGA QUIXAI — Infrastructure de Déploiement

## Vue d'ensemble

Infrastructure de déploiement pour 3 agents IA autonomes (Séduction, Closing, Lead Acquisition) tournant 24/7 sur Python 3.12 avec LangGraph, LangChain, Claude Code SDK.

**Stack** : Docker Compose, PostgreSQL+pgvector, Redis, LangFuse, Nginx, systemd

---

## Architecture Recommandée

### MVP (Étape 1)

```
VPS Hetzner (4 cores, 8GB RAM, 100GB SSD) — 6.90 EUR/mois
    ├─ Nginx (Reverse proxy + SSL)
    ├─ Docker Compose
    │   ├─ API (FastAPI)
    │   ├─ PostgreSQL 15 + pgvector
    │   ├─ Redis 7
    │   └─ LangFuse
    └─ Systemd units (3 agents autonomes)
        ├─ mega-quixai-agent-seduction.service
        ├─ mega-quixai-agent-closing.service
        └─ mega-quixai-agent-acquisition.service
```

**Coût mensuel** : ~18 EUR (infra + API Anthropic)

### Scaling (Étape 2)

Quand leads > 5000/day :
- 3x VPS (20.70 EUR/mois)
- HAProxy load balancer
- PostgreSQL replication

---

## Structure des Fichiers

```
/opt/mega-quixai/
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml         # Services: nginx, api, postgres, redis, langfuse
│   │   └── Dockerfile.api              # Multi-stage Python 3.12 build
│   ├── nginx/
│   │   └── nginx.conf                  # SSL/TLS, rate limiting, health checks
│   ├── systemd/
│   │   ├── mega-quixai-agent-seduction.service
│   │   ├── mega-quixai-agent-closing.service
│   │   ├── mega-quixai-agent-acquisition.service
│   │   └── mega-quixai.target          # Orchestrate all services
│   ├── scripts/
│   │   ├── backup.sh                   # Daily PostgreSQL backup
│   │   ├── setup-firewall.sh           # UFW rules
│   │   └── init-secrets.sh             # Initialize .secrets/
│   ├── config/
│   │   ├── schema.sql                  # PostgreSQL schema init
│   │   ├── logging.yml                 # Centralized logging config
│   │   └── .env.example                # Environment template
│   └── .secrets/                       # (not committed)
│       ├── pg_password.txt
│       ├── anthropic_key.txt
│       └── langfuse_secret.txt
├── agents/
│   ├── base.py                         # AutonomousAgent base class
│   ├── seduction/
│   │   └── main.py
│   ├── closing/
│   │   └── main.py
│   └── acquisition/
│       └── main.py
├── src/
│   └── api/
│       ├── main.py                     # FastAPI app
│       ├── health.py                   # Health endpoints
│       └── metrics.py                  # Prometheus metrics
└── .github/
    └── workflows/
        └── deploy.yml                  # GitHub Actions CI/CD
```

---

## Installation Rapide

### 1. Provision VPS

```bash
# Hetzner Cloud Console
# 1. Créer VPS : Ubuntu 24.04 LTS, 4 cores, 8GB RAM, 100GB SSD
# 2. Assigner IP publique
# 3. Créer clé SSH
```

### 2. Setup initial

```bash
# SSH on VPS
ssh -i ~/.ssh/hetzner_key root@<VPS_IP>

# Update system
apt-get update && apt-get upgrade -y
apt-get install -y curl wget git fail2ban ufw

# Create app user
useradd -m -s /bin/bash quixai
usermod -aG docker quixai

# Clone repo
git clone https://github.com/your-org/mega-quixai.git /opt/mega-quixai
cd /opt/mega-quixai
chown -R quixai:quixai .

# Create secrets
mkdir -p .secrets
chmod 700 .secrets
./infra/scripts/init-secrets.sh

# Setup firewall
sudo ./infra/scripts/setup-firewall.sh
```

### 3. Docker Compose

```bash
cd /opt/mega-quixai/infra/docker

# Create env from template
cp ../config/.env.example ../.env
nano ../.env  # Edit as needed

# Start services
docker-compose up -d

# Verify
docker-compose ps
docker-compose logs -f api
```

### 4. Systemd Units

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.target /etc/systemd/system/

# Start agents
sudo systemctl daemon-reload
sudo systemctl start mega-quixai.target
sudo systemctl enable mega-quixai.target

# Check status
sudo systemctl status mega-quixai.target
sudo journalctl -u mega-quixai-agent-seduction -f
```

### 5. SSL Setup

```bash
# Install certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --standalone \
    -d mega-quixai.com \
    -d www.mega-quixai.com \
    -m admin@mega-quixai.com \
    --agree-tos \
    --non-interactive

# Update nginx config with cert paths
sudo systemctl restart nginx

# Auto-renewal
echo "0 12 * * * certbot renew --quiet" | sudo crontab -
```

### 6. Monitoring

```bash
# Health check endpoint
curl http://localhost:3000/health

# Agent health via Redis
docker exec mega-quixai-redis redis-cli get agent:seduction:health

# Logs
docker-compose logs -f api
docker-compose logs -f postgres
sudo journalctl -u mega-quixai.target -f
```

---

## Configuration Détaillée

### docker-compose.yml

Services :
- **nginx** : Reverse proxy, SSL termination, rate limiting
- **api** : FastAPI server (3000)
- **postgres** : Database + pgvector (5432, internal only)
- **redis** : Queue + cache (6379, internal only)
- **langfuse** : LLM observability (3001, internal)

Health checks : Tous les 30 secondes
Restart policy : unless-stopped
Resource limits :
- API : 2 CPUs, 2GB RAM
- PostgreSQL : 1 CPU, 2GB RAM
- Redis : 0.5 CPU, 1GB RAM

### Dockerfile.api

Multi-stage build :
1. Builder stage : Install uv, compile requirements
2. Production stage : Minimal runtime, non-root user

Security :
- Non-root user (appuser:1000)
- Read-only base paths
- Health check with 15s start period

### nginx.conf

Upstream : api:3000 (least_conn)
Rate limiting :
- /api/* : 10 req/s
- /health : 50 req/s

Security headers :
- HSTS (strict-transport-security)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- CSP headers

Blocked ports :
- 5432 (PostgreSQL)
- 6379 (Redis)
- 3000 (API)

### Systemd Units

3x agent services + 1x target

Restart behavior :
- Restart=on-failure
- RestartSec=5s
- StartLimitBurst=5 (max 5 restarts per 300s)

Resource limits :
- MemoryLimit=1G
- CPUQuota=50%

Logging :
- stdout/stderr → systemd journal
- Access via : `journalctl -u mega-quixai-agent-*`

---

## Secrets Management

### .secrets/ directory

```
.secrets/
├── pg_password.txt           # 32 bytes random
├── anthropic_key.txt         # From Anthropic console
└── langfuse_secret.txt       # From LangFuse setup
```

**Never committed** (in .gitignore)

Generated via : `./infra/scripts/init-secrets.sh`

### Secret Rotation

```bash
# Change PostgreSQL password
# 1. Generate new password
openssl rand -base64 32 > .secrets/pg_password.txt

# 2. Update PostgreSQL
docker exec mega-quixai-postgres \
    ALTER USER quixai_user WITH PASSWORD 'new_password';

# 3. Update docker-compose (restart required)
docker-compose up -d postgres

# 4. Restart API
docker-compose restart api
```

---

## CI/CD Pipeline

### GitHub Actions (.github/workflows/deploy.yml)

**Stages** :
1. Lint (ruff) : Check style, imports
2. Test : Unit tests, coverage >= 80%
3. Build : Multi-stage Docker build, push to ghcr.io
4. Deploy (manual) : SSH to VPS, pull, restart

**Triggers** :
- Push to main → Lint + Test + Build + Deploy (approval required)
- Push to staging → Lint + Test + Build
- PR to main → Lint + Test

**Secrets required** :
- PROD_DEPLOY_KEY : SSH private key
- PROD_DEPLOY_HOST : VPS IP/hostname

---

## Backup & Recovery

### Automated Backups

```bash
# Daily at 2 AM UTC
0 2 * * * /opt/mega-quixai/infra/scripts/backup.sh

# Script creates gzipped SQL dump
# Retention : 30 days (auto-cleanup)
# Location : /var/backups/mega-quixai/
```

### Manual Recovery

```bash
# Stop API
sudo systemctl stop mega-quixai.service

# Restore from backup
./scripts/restore.sh /var/backups/mega-quixai/mega-quixai-full-20260314.sql.gz

# Start API
sudo systemctl start mega-quixai.service
```

### S3 Backup (Optional)

```bash
# Install AWS CLI
pip install awscli

# Configure
aws configure

# Upload to S3
aws s3 cp /var/backups/mega-quixai/ s3://mega-quixai-backups/ --recursive
```

---

## Monitoring

### Health Endpoints

**API**
```
GET /health
```
Response:
```json
{
  "status": "ok",
  "components": {
    "postgres": "ok",
    "redis": "ok",
    "agent_seduction": "ok:iter=245",
    "agent_closing": "ok:iter=198",
    "agent_acquisition": "ok:iter=156"
  }
}
```

**Redis health check**
```bash
docker exec mega-quixai-redis redis-cli ping
# PONG
```

**PostgreSQL health check**
```bash
docker exec mega-quixai-postgres \
    pg_isready -U quixai_user -d mega_quixai
# accepting connections
```

### Logs

**Docker logs**
```bash
docker-compose logs -f api         # API logs
docker-compose logs -f postgres    # Database logs
docker-compose logs -f redis       # Cache logs
```

**Systemd logs (agents)**
```bash
sudo journalctl -u mega-quixai-agent-seduction -f
sudo journalctl -u mega-quixai.target -f
```

**Centralized logging** (optional)
- ELK stack (Elasticsearch + Logstash + Kibana)
- Grafana Loki
- Datadog
- New Relic

---

## Scaling

### Vertical Scaling (Single VPS)

Upgrade VPS specs when hitting resource limits:

```
4 cores → 8 cores
8GB RAM → 16GB RAM
100GB → 200GB SSD
```

Cost increase : ~2-3x, still < $50/month

### Horizontal Scaling (Multiple VPS)

When leads > 5000/day :

```
VPS #1 (Load Balancer + API)
    ├─ HAProxy (port 80/443)
    └─ API container

VPS #2 (Database)
    └─ PostgreSQL primary

VPS #3 (Replica)
    └─ PostgreSQL replica

Agents : Distributed across VPS #1-3 or separate workers
```

**Cost** : 3 × 6.90 EUR = 20.70 EUR/month

### Agent Scaling

Each agent runs independently in its own systemd service.

If bottlenecked by single agent, increase loop_interval or split into worker pool:

```python
# agents/worker_pool.py
class AgentWorkerPool:
    def __init__(self, agent_name: str, num_workers: int = 4):
        self.queue = asyncio.Queue()
        # Multiple workers process tasks in parallel
```

---

## Security Checklist

- [x] Non-root containers (appuser:1000)
- [x] SSL/TLS with Let's Encrypt
- [x] UFW firewall (deny by default)
- [x] SSH key-based auth only
- [x] Secrets in .secrets/ (not committed)
- [x] Rate limiting on all endpoints
- [x] PostgreSQL internal network only
- [x] Redis internal network only
- [x] Health check monitoring
- [x] Automated backups with retention
- [x] Log rotation and archival
- [x] fail2ban for brute-force protection

---

## Troubleshooting

### Agent stuck in restart loop

```bash
# Check logs
sudo journalctl -u mega-quixai-agent-seduction -n 50

# Check dependencies
docker-compose ps
curl http://localhost:3000/health

# Restart manually
sudo systemctl restart mega-quixai-agent-seduction
```

### PostgreSQL connection refused

```bash
# Check container health
docker-compose logs postgres

# Test connection
docker exec mega-quixai-postgres \
    pg_isready -U quixai_user -d mega_quixai

# Restart
docker-compose restart postgres
```

### Disk space full

```bash
df -h /opt/mega-quixai

# Cleanup logs
find /var/log/mega-quixai -name "*.log" -mtime +30 -delete

# Cleanup Docker
docker system prune -a --volumes
```

### Memory leak

```bash
# Check container memory usage
docker stats

# Check agent memory
ps aux | grep agents
top -p <PID>

# Restart container
docker-compose restart api
```

---

## Cost Estimation

### Monthly (MVP)

| Item | Cost |
|------|------|
| Hetzner VPS 4core/8GB | €6.90 |
| Backup storage (S3) | €2.50 |
| Anthropic API (100 req/day) | ~€8 |
| Domain (.com) | ~€0.85 |
| **TOTAL** | **~€18.25** |

### Annual

```
Year 1 : €109 + €124 + €10 = €243
Year 2+ : €249 + €96 + €10 = €355
```

### Scaling to 3 VPS

```
3 × €6.90 = €20.70 (infra)
+ API costs (same)
+ Backups (same)
= ~€31/month
```

---

## Files Created

```
infra/
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile.api
├── nginx/
│   └── nginx.conf
├── systemd/
│   ├── mega-quixai-agent-seduction.service
│   ├── mega-quixai-agent-closing.service
│   ├── mega-quixai-agent-acquisition.service
│   └── mega-quixai.target
├── scripts/
│   ├── backup.sh
│   ├── setup-firewall.sh
│   └── init-secrets.sh
└── config/
    ├── schema.sql
    ├── logging.yml
    └── .env.example

.github/
└── workflows/
    └── deploy.yml

agents/
└── base.py
```

---

## Next Steps

1. **Week 1** : VPS setup, Docker Compose, verify containers running
2. **Week 2** : Implement 3 agent classes, test systemd units
3. **Week 3** : Setup CI/CD pipeline, test full deployment
4. **Week 4** : Monitoring, backups, security hardening

---

## References

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [systemd Documentation](https://systemd.io/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)

