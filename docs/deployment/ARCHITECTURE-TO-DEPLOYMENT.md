# Architecture → Deployment Mapping — Hexis (QUIXAI)

**Purpose:** Connect system architecture decisions to OVH production choices.

---

## Architecture Requirement → Deployment Implementation

### 1. LLM Orchestration (Claude Max API)

**Architecture Decision:**
- Claude SDK for multi-turn conversations
- Structured outputs for state management
- Token counting for cost control

**Deployment Implementation:**
- ANTHROPIC_API_KEY injected via `.env`
- API rate limiting (10 req/s per IP) via Nginx
- Request logging for cost tracking
- Fallback to queue (RabbitMQ) on API errors

**Cost Impact:** 174€/month (vs. 200€+ for GPU-based Ollama)

**File References:**
- Docker Compose: `docker-compose.prod.yml` (environment variables section)
- Nginx: `hexis-api.conf` (rate limiting zones)
- Environment: `.env` (ANTHROPIC_API_KEY)

---

### 2. PostgreSQL + pgvector + AGE

**Architecture Decision:**
- pgvector for semantic search (embedding similarity)
- Apache AGE for graph relationships
- Vector indexes for <100ms query latency

**Deployment Implementation:**
- PostgreSQL 16 with extensions pre-loaded
- Resource limits: 2 CPU, 4GB RAM
- Automated backups (daily pg_dump + S3 weekly upload)
- Health checks every 10s with 30s startup grace

**Data Persistence:** Named volume `postgres_data` (never bind-mounts)

**Backup Strategy:**
- Local: `/var/backups/hexis/` (7 daily backups)
- Remote: OVH Object Storage (14+ day history)
- Restore time: <5 min from backup

**File References:**
- Docker Compose: `docker-compose.prod.yml` (db service)
- Backup Script: `/opt/hexis/backup.sh`
- DR Script: `/opt/hexis/disaster-recovery.sh`

---

### 3. RabbitMQ Message Broker

**Architecture Decision:**
- Asynchronous task queue (heartbeat, maintenance, channels)
- Dead Letter Queue for failed messages
- At-least-once delivery semantics

**Deployment Implementation:**
- RabbitMQ 4 (Alpine image, smaller footprint)
- Resource limits: 1 CPU, 1GB RAM
- Persistent volume for messages (`rabbitmq_data`)
- Management UI disabled in production (no external access)

**Network:** Internal Docker network only (no external ports exposed)

**Monitoring:** Health checks via `rabbitmq-diagnostics ping`

**File References:**
- Docker Compose: `docker-compose.prod.yml` (rabbitmq service)
- Firewall: No port 5672 exposed externally (UFW rules)

---

### 4. FastAPI Worker Architecture

**Architecture Decision:**
- Multiple independent workers (heartbeat, maintenance, channel handler)
- API server with 2x replicas (zero-downtime deploy)
- Dependency injection (database, API client)

**Deployment Implementation:**

**Heartbeat Worker:**
- Runs every 60s
- Lightweight (256MB limit)
- Monitors system health, updates agent status
- File: `docker-compose.prod.yml` (heartbeat_worker service)

**Maintenance Worker:**
- Runs nightly cleanup tasks
- Garbage collection, index optimization
- File: `docker-compose.prod.yml` (maintenance_worker service)

**Channel Worker:**
- Handles Telegram, Discord, WhatsApp inbound/outbound
- Scales horizontally (one instance per channel group)
- File: `docker-compose.prod.yml` (channel_worker service)

**API Server:**
- 2 replicas via Docker Compose `replicas: 2`
- Nginx upstream load balancing
- Health checks on port 43817 (internal)
- Resource limits: 1 CPU, 1GB RAM per replica

**File References:**
- Docker Compose: `docker-compose.prod.yml` (api, workers)
- Nginx: `hexis-api.conf` (upstream directive, proxy_pass)
- Logging: All workers → JSON-file driver (10MB max, 3 files)

---

### 5. Network Architecture (Public/Private)

**Architecture Decision:**
- Separate networks for isolation
- Public: Nginx reverse proxy layer
- Private: Internal services (no external exposure)

**Deployment Implementation:**

```
External (Internet)
    ↓
Nginx (Port 443, SSL)
    ↓
Docker Network: public
    ├─ UI (port 3477, internal)
    └─ API (port 43817, internal)
    ↓
Docker Network: private (internal: true)
    ├─ PostgreSQL (5432)
    ├─ RabbitMQ (5672)
    ├─ Workers (private IPs)
    └─ [No external access]
```

**Security Implications:**
- Database never exposed externally (no 5432 in UFW)
- RabbitMQ management UI blocked (no 15672)
- All traffic through Nginx SSL termination
- Rate limiting enforced at reverse proxy layer

**File References:**
- Docker Compose: `docker-compose.prod.yml` (networks section)
- Nginx: `hexis-api.conf` (listen 443, ssl)
- Firewall: `setup-firewall.sh` (ufw allow 443/tcp only)

---

### 6. State Management (LangGraph)

**Architecture Decision:**
- Graph-based agent orchestration
- State stored in PostgreSQL
- Async execution via RabbitMQ queues

**Deployment Implementation:**
- API endpoint: `POST /api/v1/agents/{agent_id}/step`
- State serialized to `agent_state` table
- Long-running tasks enqueued to RabbitMQ
- Results cached in Redis (future optimization)

**Concurrency Model:**
- Max 8 concurrent agent steps (configurable)
- Queue depth monitored via RabbitMQ metrics
- Backpressure: 429 Too Many Requests when queue > 100

**File References:**
- API: Hexis worker image (`ghcr.io/quixiai/hexis-worker:latest`)
- Database schema: PostgreSQL migrations
- Rate limiting: Nginx config (limit_req_zone)

---

### 7. Security (V-Code System)

**Architecture Decision:**
- Input validation via Pydantic
- Rate limiting per IP
- API key authentication (header: `X-API-Key`)
- CORS restricted to whitelisted origins

**Deployment Implementation:**

**Input Validation:**
- All requests validated by FastAPI Pydantic models
- Payload size limit: 10MB (Nginx: client_max_body_size)

**Rate Limiting:**
- `/api/v1/auth/login`: 5 req/min per IP (prevent brute force)
- `/api/`: 10 req/s per IP (API tier)
- General: 30 req/s per IP (default)
- Burst allowance: 20 additional requests

**CORS:**
- Allowed origins: `${CORS_ORIGINS}` from `.env`
- Credentials: false (no cookies)
- Methods: GET, POST, PUT, DELETE
- File: FastAPI app initialization

**HTTPS Only:**
- HTTP 80 → 301 redirect to HTTPS 443
- HSTS header: `max-age=31536000; includeSubDomains`
- Certificate: Let's Encrypt (auto-renewed)

**File References:**
- Nginx: `hexis-api.conf` (rate limiting, HSTS, CORS)
- Firewall: `setup-firewall.sh` (port restrictions)
- SSL: `setup-ssl.sh` (certbot automation)
- Environment: `.env` (CORS_ORIGINS, API_KEY)

---

### 8. Observability (Logging & Monitoring)

**Architecture Decision:**
- Structured JSON logging
- Health check endpoints
- External uptime monitoring
- No on-VPS observability stack (avoid complexity)

**Deployment Implementation:**

**Health Checks:**
- PostgreSQL: `pg_isready` every 10s
- RabbitMQ: `rabbitmq-diagnostics ping` every 10s
- API: HTTP 200 on GET `/health`
- All checks with 30s startup grace period

**Logging:**
- Format: JSON (structured logging)
- Rotation: 10MB max file size, 3 files (30MB total)
- Retention: 14 days compressed
- Tool: Logrotate (daily cron)

**Monitoring:**
- UptimeRobot (free tier): Check `/health` every 1 min
- Slack webhook: Alert on 5s+ response time
- Email: Certificate expiry warning 7 days before

**Log Locations:**
```
/var/log/hexis/
  ├── api.log
  ├── db.log
  ├── rabbitmq.log
  ├── channel_worker.log
  ├── heartbeat_worker.log
  └── maintenance_worker.log

/var/log/nginx/
  ├── hexis_api_access.log
  ├── hexis_api_error.log
  ├── hexis_ui_access.log
  └── hexis_ui_error.log
```

**File References:**
- Docker Compose: All services → `json-file` logging driver
- Logrotate: `/etc/logrotate.d/hexis`
- Health checks: `/opt/hexis/health-check.py`
- Monitoring: Nginx access logs (parse with `tail` + grep)

---

### 9. Disaster Recovery Architecture

**Architecture Decision:**
- Point-in-time recovery via database backups
- Stateless API servers (no affinity)
- Configuration in Git (infra-as-code)

**Deployment Implementation:**

**RTO/RPO Targets:**
| Component | RTO | RPO | Method |
|-----------|-----|-----|--------|
| API | 2 min | 0 min | Docker restart |
| Database | 15 min | 24h | pg_dump restore |
| Configuration | 5 min | 0 min | Git checkout |

**Backup Chain:**
- Local: Daily 2 AM → `/var/backups/hexis/` (gzip)
- Remote: Weekly 3 AM → OVH Object Storage (S3)
- Retention: 7 local + 12 monthly in S3

**Recovery Procedures:**
1. **API Crash:** `docker compose restart api` (2 min)
2. **DB Corruption:** Run `disaster-recovery.sh` (15 min)
3. **VPS Failure:** Provision new VPS + DNS update (15 min)

**File References:**
- Backup script: `/opt/hexis/backup.sh`
- Recovery script: `/opt/hexis/disaster-recovery.sh`
- Cron jobs: `/etc/cron.d/hexis-backup`

---

### 10. Deployment Pipeline (CI/CD)

**Architecture Decision:**
- GitHub-hosted runners (no self-hosted complexity)
- Multi-stage: test → build → deploy
- Automated backup before each deploy

**Deployment Implementation:**

**Test Stage:**
- pytest + coverage (min 80%)
- ruff format check
- mypy type checking

**Build Stage:**
- Docker multi-stage build (minimal image)
- Push to GHCR (GitHub Container Registry)
- Tag: `:latest` and `:${COMMIT_SHA}`

**Deploy Stage:**
- SSH into OVH VPS
- `git pull` latest code
- `docker compose pull` latest images
- Run backup before restart
- `docker compose up -d --remove-orphans`
- Health check via `curl https://api.yourdomain.com/health`

**Slack Notification:**
- On success/failure
- Includes commit SHA and deploy timestamp

**File References:**
- GitHub Actions: `.github/workflows/deploy-prod.yml`
- SSH Key: Stored in GitHub Secrets
- Webhook: `SLACK_WEBHOOK` secret

---

## Deployment Summary Table

| Component | Architecture | OVH Implementation | File Reference |
|-----------|--------------|-------------------|-----------------|
| **LLM** | Claude SDK | Claude Max API | `.env` + Nginx rate limits |
| **Database** | PostgreSQL 16 | 2 CPU, 4GB RAM, named volume | `docker-compose.prod.yml` |
| **Message Queue** | RabbitMQ | 1 CPU, 1GB RAM, Alpine image | `docker-compose.prod.yml` |
| **Workers** | FastAPI + Async | 3 types, resource limited | `docker-compose.prod.yml` |
| **API Server** | FastAPI | 2 replicas, internal port | `docker-compose.prod.yml` + Nginx |
| **Network** | Public/Private | Docker networks + UFW rules | `docker-compose.prod.yml` + UFW |
| **Security** | V-Code | Rate limits + CORS + HTTPS | Nginx config + `.env` |
| **Backups** | Point-in-time | Daily local + weekly S3 | `backup.sh` + cron |
| **Monitoring** | Health checks | UptimeRobot + JSON logs | `/opt/hexis/health-check.py` |
| **Recovery** | Automated | Disaster recovery script | `disaster-recovery.sh` |
| **CI/CD** | GitHub Actions | Test → Build → Deploy | `.github/workflows/` |
| **SSL/TLS** | Let's Encrypt | Certbot auto-renewal | `setup-ssl.sh` + cron |
| **Infrastructure** | Single VPS | OVH VPS 4 (16.99€/mo) | VPS subscription |

---

## Cross-Reference: Where to Find Things

**Need to...**

- Set up environment variables? → `.env` file template in repo
- Configure database backups? → `/opt/hexis/backup.sh`
- Set up SSL certificates? → `/opt/hexis/setup-ssl.sh`
- Configure rate limiting? → `/etc/nginx/sites-available/hexis-api.conf`
- Block ports externally? → `/opt/hexis/setup-firewall.sh`
- Deploy to production? → `.github/workflows/deploy-prod.yml`
- Check system health? → `GET https://api.yourdomain.com/health`
- Restore from backup? → `/opt/hexis/disaster-recovery.sh`
- Monitor logs in real-time? → `docker compose logs -f api`
- Upgrade to larger VPS? → OVH panel + update `docker-compose.prod.yml` resource limits

---

**Status:** Complete mapping between architecture and production deployment  
**Last Updated:** 2026-03-14  
**Owner:** DevOps Lead
