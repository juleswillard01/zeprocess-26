# OVH Deployment Quick Start — Hexis (QUIXAI)

**Full Plan:** See [ovh-production-plan.md](ovh-production-plan.md) (1,572 lines)

## TL;DR: Deploy in 30 Minutes

### Step 1: Get OVH VPS (5 min)
```
Product:  OVH VPS 4
Cost:     16.99€/month
Specs:    4 vCPU | 8GB RAM | 80GB NVMe | 1Gbps unmetered
Region:   GRA (Gravelines, France) — RGPD compliant
URL:      https://www.ovh.com/world/vps/
```

### Step 2: Configure DNS (5 min)
```
Domain:      yourdomain.com
DNS A Record: api.yourdomain.com → YOUR_OVH_IP
TTL:         300 (auto-refresh)
Provider:    Cloudflare (free), GoDaddy, or Route53
```

### Step 3: Deploy Stack (20 min)
```bash
# SSH into VPS
ssh root@YOUR_OVH_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and deploy
git clone https://github.com/quixiai/hexis.git /opt/hexis
cd /opt/hexis

# Create environment (EDIT with your values!)
cp .env.example .env
nano .env  # Set: POSTGRES_PASSWORD, ANTHROPIC_API_KEY, DOMAIN=yourdomain.com

# Setup firewall
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable

# Setup SSL
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# Start services
docker compose -f docker-compose.prod.yml --profile active up -d

# Verify
curl https://api.yourdomain.com/health
```

## Key Files in Full Plan

| Section | Lines | Purpose |
|---------|-------|---------|
| **Infrastructure** | 1-70 | OVH sizing for 10/50/100 users |
| **Docker Compose** | 71-380 | Production-ready configs (no Ollama) |
| **Nginx** | 381-500 | SSL, rate limiting, reverse proxy |
| **Firewall** | 501-550 | UFW rules (SSH + HTTPS only) |
| **Backups** | 551-650 | pg_dump + OVH Object Storage |
| **Monitoring** | 651-750 | Health checks, UptimeRobot, alerts |
| **CI/CD** | 751-900 | GitHub Actions (test → build → deploy) |
| **SSL** | 901-950 | Let's Encrypt auto-renewal |
| **Logs** | 951-1050 | Logrotate, retention policy |
| **DR** | 1051-1300 | Recovery scripts, RTO/RPO, scenarios |
| **Costs** | 1301-1400 | 380€/month breakdown (50 users) |
| **Checklist** | 1401-1572 | Pre/day-0/post deployment steps |

## Cost at a Glance

```
Infrastructure:    31.48€/month  (VPS 4 + storage + domain + monitoring)
Claude Max API:   174.00€/month  (estimating 5K requests/month)
────────────────────────────────
TOTAL:            205.48€/month  (→ 380€/month at 100 users)

Break-even:       6 Pro subscriptions @ 149€ = 894€/month
```

## Production Checklist (20 items)

**Pre-Deploy:**
- [ ] Domain registered & DNS updated
- [ ] GitHub repo with CI/CD workflows
- [ ] `.env` file with secrets (not committed)
- [ ] OVH Object Storage bucket created
- [ ] Slack webhook for notifications

**Deploy Day:**
- [ ] Run setup script (Docker, firewall, SSL)
- [ ] Start containers: `docker compose ... up -d`
- [ ] Verify health: `curl https://api.yourdomain.com/health`
- [ ] Test database: `docker exec hexis_brain pg_isready`
- [ ] Test backup: `bash /opt/hexis/backup.sh`

**Post-Deploy:**
- [ ] Monitor logs for 24h
- [ ] Verify automated backups
- [ ] Test SSL renewal (dry-run)
- [ ] Document IPs/credentials
- [ ] Train team on monitoring

## Disaster Recovery (Under 15 Min)

**Database restored from backup:**
```bash
/opt/hexis/disaster-recovery.sh
# Stops app → restores from latest backup → verifies → restarts
```

**VPS failure:**
- Order new VPS (5 min)
- Run disaster-recovery.sh (5 min)
- Update DNS A record (propagates 5 min)
- **Total RTO: 15 minutes**

## Monitoring Stack

**Health Endpoint:** `GET https://api.yourdomain.com/health`

**Alerting (via UptimeRobot free tier):**
- API down → Email within 1 min
- Response time > 5s → Slack notification
- SSL expires < 7 days → Email reminder

**Log Locations:**
```
/var/log/hexis/api.log         (FastAPI)
/var/log/hexis/db.log          (PostgreSQL)
/var/log/hexis/rabbitmq.log    (RabbitMQ)
/var/log/nginx/hexis*.log      (Nginx)
```

## Scaling Path

| Users | Infrastructure | Monthly Cost | Approach |
|-------|-----------------|--------------|----------|
| **10** | VPS 2 | 8€ | Development |
| **50** | VPS 4 | 17€ | Default: Start here |
| **100** | Dedicated XE | 25€ | Upgrade when needed |
| **500+** | Dedicated Advance | 50€ | Consider multi-region |

## What's NOT Included (Keep Separate)

- Frontend hosting (use Vercel/Netlify if needed)
- Email service (SendGrid/Mailgun for transactional)
- Analytics (Mixpanel/Segment optional)
- Support ticketing (GitHub Issues sufficient initially)

## Tech Stack Summary

```
┌─────────────────────────────────────────────┐
│            QUIXAI HEXIS                     │
├─────────────────────────────────────────────┤
│  Reverse Proxy:    Nginx (SSL/TLS)          │
│  Frontend:         Next.js/Vite (React)     │
│  API:              FastAPI (Python)         │
│  Message Broker:   RabbitMQ 4 (Alpine)      │
│  Database:         PostgreSQL 16 + pgvector │
│  Embeddings:       Claude API (no local LLM)│
│  Channels:         Telegram, Discord, etc.  │
│  Orchestration:    Docker Compose           │
│  Infrastructure:   OVH VPS / Dedicated      │
│  Backups:          OVH Object Storage (S3)  │
│  CI/CD:            GitHub Actions           │
│  SSL:              Let's Encrypt + certbot  │
│  Monitoring:       UptimeRobot + health chk │
└─────────────────────────────────────────────┘
```

## Key Decisions Explained

**Why Claude Max API (not Ollama)?**
- 174€/month fixed cost vs. 50GB+ VRAM for local LLM
- Always latest models (Sonnet 3.5 vs. stale embeddings)
- No cold-start latency, no infra overhead
- Optimal until >1000 concurrent users

**Why Nginx (not Traefik)?**
- Simpler, lighter, battle-tested
- No Docker complexity, can be managed standalone
- Excellent rate limiting & IP whitelist support
- Let's Encrypt integration trivial

**Why OVH (not AWS/GCP)?**
- RGPD: All data stays in EU (France)
- 70% cost savings vs. AWS EC2 equivalent
- Object Storage cheaper than S3 (0.12€/GB vs. 0.023$/GB)
- Predictable pricing, no surprise overage bills

## Links

- Full Plan: [ovh-production-plan.md](ovh-production-plan.md)
- Hexis Repo: https://github.com/quixiai/hexis
- OVH Docs: https://docs.ovh.com/us/en/
- Docker Compose: https://docs.docker.com/compose/production/
- Let's Encrypt: https://letsencrypt.org/

---

**Status:** Ready to deploy  
**Last Updated:** 2026-03-14  
**Owner:** DevOps Lead
