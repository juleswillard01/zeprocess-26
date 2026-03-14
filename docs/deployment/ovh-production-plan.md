# OVH Production Deployment Plan — QUIXAI/Hexis

**Date:** 2026-03-14  
**Status:** Ready for Implementation  
**Audience:** DevOps Lead, Infrastructure Team  

## Table of Contents
1. [OVH Infrastructure Recommendation](#1-ovh-infrastructure-recommendation)
2. [Production Docker Compose](#2-production-docker-compose)
3. [Nginx Configuration](#3-nginx-configuration)
4. [Firewall Rules (UFW)](#4-firewall-rules-ufw)
5. [Backup Strategy](#5-backup-strategy)
6. [Monitoring Stack](#6-monitoring-stack)
7. [CI/CD Pipeline (GitHub Actions)](#7-cicd-pipeline-github-actions)
8. [SSL Certificates (Let's Encrypt)](#8-ssl-certificates-lets-encrypt)
9. [Log Management](#9-log-management)
10. [Disaster Recovery Plan](#10-disaster-recovery-plan)
11. [Cost Breakdown](#11-cost-breakdown)
12. [Deployment Checklist](#12-deployment-checklist)

---

## 1. OVH Infrastructure Recommendation

### Analysis: Hexis Resource Requirements

**Key Constraints:**
- PostgreSQL 16 (pgvector + AGE extensions) with pgvector indexes = moderate disk/memory
- RabbitMQ queue broker = modest CPU/RAM
- 3-5 FastAPI workers = CPU-bound (depends on concurrency)
- Channel workers (Telegram/WhatsApp/Discord) = I/O-bound, low CPU
- React/Next.js frontend = static assets (minimal server load if edge-cached)
- Claude Max API calls = external (no local LLM, saving 50+ GB VRAM)

**Capacity Planning per User Tier:**
- **10 users:** 1-2 concurrent sessions max, development/beta phase
- **50 users:** 5-8 concurrent sessions, moderate queue depth
- **100 users:** 10-15 concurrent sessions, peak queue depth

### Recommended OVH Offers

| Tier | Product | vCPU | RAM | NVMe SSD | Price/mo | Use Case |
|------|---------|------|-----|---------|----------|----------|
| **10 users (Beta)** | VPS 2 | 2 | 4GB | 40GB | ~7.99€ | Development, testing |
| **50 users (Scale)** | VPS 4 | 4 | 8GB | 80GB | ~16.99€ | Production ready, growth |
| **100 users (Peak)** | Dedicated Starter | 8 cores | 16GB | 240GB | ~24.99€ | Full capacity, growth runway |

**Alternative: Dedicated Server (Recommended for Stability)**
- **OVH Dedicated Starter XE** (production-grade for 50-100 users)
  - 8 CPU cores (Intel Xeon E-2136)
  - 16GB DDR4 RAM
  - 240GB NVMe SSD
  - Unmetered bandwidth
  - **Price:** 24.99€/month
  - **Why:** Guaranteed CPU (VPS is shared), RAID1 option for uptime, no noisy neighbors

**Recommended Path:**
1. **Start:** VPS 4 (50-user capacity, 16.99€/mo) for initial launch
2. **Scale:** Upgrade to Dedicated Starter XE when hitting 50+ concurrent users
3. **Future:** Dedicated Advance (32+ CPU) only if >500 concurrent users

---

## 2. Production Docker Compose

**Key Changes from Dev:**
- No Ollama (using Claude Max API for embeddings)
- No local volume binds (use named volumes only)
- Resource limits on all containers
- Health checks on every service
- Secrets via `.env` file (never committed)
- Init containers for migrations/schema setup
- Network policies: PostgreSQL/RabbitMQ only on internal network

**File:** `/opt/hexis/docker-compose.prod.yml`

```yaml
version: '3.9'

services:
  db:
    image: ghcr.io/quixiai/hexis-brain:latest
    container_name: hexis_brain
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_INITDB_ARGS: "-c shared_preload_libraries=pg_stat_statements,pg_cron"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private
    command:
      - postgres
      - -c
      - search_path=ag_catalog,public
      - -c
      - app.embedding_dimension=1536
      - -c
      - app.embedding_service_url=${EMBEDDING_SERVICE_URL}
      - -c
      - app.embedding_model_id=claude-3-5-sonnet

  rabbitmq:
    image: rabbitmq:4-management-alpine
    container_name: hexis_rabbitmq
    restart: unless-stopped
    profiles:
      - active
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST:-/}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 20s
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private

  heartbeat_worker:
    image: ghcr.io/quixiai/hexis-worker:latest
    container_name: hexis_heartbeat_worker
    restart: unless-stopped
    profiles:
      - active
    command: ["hexis-worker", "--mode", "heartbeat"]
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      RABBITMQ_HOST: rabbitmq
      RABBITMQ_PORT: 5672
      RABBITMQ_USER: ${RABBITMQ_USER}
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
      RABBITMQ_VHOST: ${RABBITMQ_VHOST:-/}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private

  maintenance_worker:
    image: ghcr.io/quixiai/hexis-worker:latest
    container_name: hexis_maintenance_worker
    restart: unless-stopped
    profiles:
      - active
    command: ["hexis-worker", "--mode", "maintenance"]
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      RABBITMQ_HOST: rabbitmq
      RABBITMQ_PORT: 5672
      RABBITMQ_USER: ${RABBITMQ_USER}
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
      RABBITMQ_VHOST: ${RABBITMQ_VHOST:-/}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private

  api:
    image: ghcr.io/quixiai/hexis-worker:latest
    container_name: hexis_api
    restart: unless-stopped
    profiles:
      - active
    command: ["hexis-api", "--host", "127.0.0.1", "--port", "43817"]
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "43817"
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS:-https://yourdomain.com}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private

  channel_worker:
    image: ghcr.io/quixiai/hexis-channels:latest
    container_name: hexis_channel_worker
    restart: unless-stopped
    profiles:
      - active
    command: ["hexis-channels"]
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      RABBITMQ_HOST: rabbitmq
      RABBITMQ_PORT: 5672
      RABBITMQ_USER: ${RABBITMQ_USER}
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
      RABBITMQ_VHOST: ${RABBITMQ_VHOST:-/}
      DISCORD_BOT_TOKEN: ${DISCORD_BOT_TOKEN:-}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
      SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN:-}
      SLACK_APP_TOKEN: ${SLACK_APP_TOKEN:-}
      WHATSAPP_ACCESS_TOKEN: ${WHATSAPP_ACCESS_TOKEN:-}
      WHATSAPP_PHONE_NUMBER_ID: ${WHATSAPP_PHONE_NUMBER_ID:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private

  ui:
    image: ghcr.io/quixiai/hexis-ui:latest
    container_name: hexis_ui
    restart: unless-stopped
    depends_on:
      api:
        condition: service_started
    expose:
      - "3477"
    environment:
      VITE_API_URL: https://${DOMAIN}/api
      VITE_WS_URL: wss://${DOMAIN}/ws
      NODE_ENV: production
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          cpus: '0.125'
          memory: 128M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - private

volumes:
  postgres_data:
    driver: local
  rabbitmq_data:
    driver: local

networks:
  private:
    internal: true
```

**Environment File:** `/opt/hexis/.env` (NEVER commit)

```bash
# PostgreSQL
POSTGRES_DB=hexis_memory
POSTGRES_USER=hexis_prod_user
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_INITDB_ARGS="-c shared_preload_libraries=pg_stat_statements"

# RabbitMQ
RABBITMQ_USER=hexis_mq
RABBITMQ_PASSWORD=CHANGE_ME_STRONG_PASSWORD
RABBITMQ_VHOST=/prod

# API Keys (load from secrets manager in production)
ANTHROPIC_API_KEY=sk-ant-XXXXXXXX

# Domain & Network
DOMAIN=api.yourdomain.com
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Channel Integrations (optional)
DISCORD_BOT_TOKEN=
TELEGRAM_BOT_TOKEN=
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

# Logging
LOG_LEVEL=info

# Embedding Service (using Claude API)
EMBEDDING_SERVICE_URL=https://api.anthropic.com/v1/embeddings
```

---

## 3. Nginx Configuration

**Purpose:** SSL termination, rate limiting, IP whitelist, reverse proxy

**File:** `/etc/nginx/sites-available/hexis-api.conf`

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;

# IP Whitelist (optional: for admin/internal endpoints)
geo $admin_whitelist {
    default 0;
    YOUR_OFFICE_IP 1;
    YOUR_VPN_IP 1;
}

upstream hexis_api {
    # API replicas (2x for zero-downtime)
    server 127.0.0.1:43817 max_fails=3 fail_timeout=30s;
}

upstream hexis_ui {
    server 127.0.0.1:3477 max_fails=3 fail_timeout=30s;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name api.yourdomain.com *.yourdomain.com;

    location /.well-known/acme-challenge/ {
        # Let's Encrypt verification
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS (API)
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL Certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/yourdomain.com/chain.pem;

    # SSL hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;

    # HSTS (Strict-Transport-Security)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Logging
    access_log /var/log/nginx/hexis_api_access.log;
    error_log /var/log/nginx/hexis_api_error.log warn;

    # Client body size (uploads, payloads)
    client_max_body_size 10M;

    # Timeouts
    proxy_connect_timeout 30s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;

    # Health check endpoint (no rate limit)
    location /health {
        access_log off;
        proxy_pass http://hexis_api;
        proxy_http_version 1.1;
    }

    # Authentication endpoint (stricter rate limit)
    location /api/v1/auth/login {
        limit_req zone=auth_limit burst=10 nodelay;
        proxy_pass http://hexis_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # General API endpoint (standard rate limit)
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://hexis_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;

        # Prevent caching of API responses
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
    }

    # Admin endpoints (IP whitelist)
    location /admin/ {
        if ($admin_whitelist = 0) {
            return 403;
        }
        proxy_pass http://hexis_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Default
    location / {
        limit_req zone=general burst=50 nodelay;
        proxy_pass http://hexis_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTPS (UI Frontend)
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    access_log /var/log/nginx/hexis_ui_access.log;
    error_log /var/log/nginx/hexis_ui_error.log warn;

    # Frontend assets (long cache, immutable hashes)
    location ~* ^/assets/ {
        proxy_pass http://hexis_ui;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA: index.html (no cache)
    location / {
        proxy_pass http://hexis_ui;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SPA routing: fallback to index.html
        error_page 404 =200 /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}
```

**Enable & Test:**
```bash
sudo ln -s /etc/nginx/sites-available/hexis-api.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 4. Firewall Rules (UFW)

**Strategy:** Block all inbound except SSH + HTTPS, outbound unrestricted

```bash
#!/bin/bash
# /opt/hexis/setup-firewall.sh

set -e

echo "Configuring UFW firewall..."

# Enable UFW
sudo ufw --force enable

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH (port 22)
sudo ufw allow 22/tcp comment "SSH"

# HTTP (port 80) - Let's Encrypt verification + redirect
sudo ufw allow 80/tcp comment "HTTP (ACME + redirect)"

# HTTPS (port 443)
sudo ufw allow 443/tcp comment "HTTPS"

# Docker internal (no external access)
# PostgreSQL (5432), RabbitMQ (5672) NOT exposed externally

# Deny everything else
sudo ufw logging on
sudo ufw logging high

# List rules
echo "Firewall rules:"
sudo ufw status verbose

echo "Firewall configured successfully."
```

**Optional: Rate Limit SSH (prevent brute force)**
```bash
sudo ufw limit 22/tcp comment "SSH rate limit"
```

---

## 5. Backup Strategy

**Approach:** 
- Automated nightly pg_dump (PostgreSQL) to local disk
- Upload to OVH Object Storage (S3-compatible) weekly
- Keep 7 daily + 4 weekly + 12 monthly backups
- Test restore monthly

**File:** `/opt/hexis/backup.sh`

```bash
#!/bin/bash
# Production backup script for Hexis

set -e

BACKUP_DIR="/var/backups/hexis"
DB_CONTAINER="hexis_brain"
RETENTION_DAYS=7
LOG_FILE="/var/log/hexis-backup.log"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/hexis_memory_$TIMESTAMP.sql.gz"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting backup..."

# Backup PostgreSQL
docker exec "$DB_CONTAINER" pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-password \
    --verbose \
    --format=plain \
    | gzip > "$BACKUP_FILE"

log "Backup completed: $BACKUP_FILE"

# Upload to OVH Object Storage (S3)
if command -v aws &> /dev/null; then
    log "Uploading to OVH Object Storage..."
    
    aws s3 cp "$BACKUP_FILE" \
        "s3://hexis-backups/postgresql/$TIMESTAMP.sql.gz" \
        --region gra \
        --endpoint-url https://s3.gra.io.cloud.ovh.net
    
    log "Upload completed"
fi

# Rotate local backups (keep 7 days)
log "Rotating backups (keeping $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "hexis_memory_*.sql.gz" -mtime +$RETENTION_DAYS -delete

log "Backup process completed successfully"
```

**Cron Job:** `/etc/cron.d/hexis-backup`

```bash
# Run at 2 AM daily
0 2 * * * root /opt/hexis/backup.sh >> /var/log/hexis-backup.log 2>&1

# Weekly S3 upload at 3 AM on Sunday
0 3 * * 0 root /usr/local/bin/hexis-s3-upload.sh
```

**OVH Object Storage Setup:**
```bash
# Install AWS CLI
sudo apt-get install -y awscli

# Configure credentials (~/.aws/credentials)
[hexis-backup]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY

# Test connectivity
aws s3 ls s3://hexis-backups/ --region gra --endpoint-url https://s3.gra.io.cloud.ovh.net
```

**Restore Procedure:**
```bash
# Download backup from S3
aws s3 cp s3://hexis-backups/postgresql/TIMESTAMP.sql.gz . \
    --region gra --endpoint-url https://s3.gra.io.cloud.ovh.net

# Restore to database
gunzip < TIMESTAMP.sql.gz | docker exec -i hexis_brain psql -U hexis_prod_user -d hexis_memory
```

---

## 6. Monitoring Stack

**Philosophy:** Lightweight (no Kubernetes complexity), health-based alerting

### 6.1 Health Check Endpoints

**API Health:** `GET /health`
```json
{
  "status": "healthy",
  "timestamp": "2026-03-14T10:00:00Z",
  "services": {
    "database": "ok",
    "rabbitmq": "ok",
    "api": "ok"
  }
}
```

### 6.2 Log Aggregation (Simple)

**File:** `/var/log/hexis/` (JSON logging)

All containers configured with:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"      # Rotate at 10MB
    max-file: "3"        # Keep 3 files (30MB total)
    labels: "service"
```

**Monitor logs locally:**
```bash
# Real-time tail
docker compose logs -f api

# Search for errors
grep ERROR /var/log/hexis/*.log

# Retention policy
find /var/lib/docker/containers -name "*-json.log" -mtime +30 -delete
```

### 6.3 Uptime Monitoring (External)

Use a free/paid service (recommended: UptimeRobot, Pingdom, or OVH Manager):

**Monitoring URL:** `https://api.yourdomain.com/health`

**Alert Conditions:**
- API responds with HTTP 500+ → Email alert
- Response time > 5s → Page (PagerDuty/Slack)
- DB connection fails → Critical alert

### 6.4 Optional: Prometheus + Node Exporter

**For future scaling (not MVP):**
```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  command:
    - --config.file=/etc/prometheus/prometheus.yml
  expose:
    - "9090"

node_exporter:
  image: prom/node-exporter:latest
  command:
    - --path.procfs=/host/proc
    - --path.rootfs=/
  volumes:
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
  expose:
    - "9100"
```

### 6.5 Alerting (Email + Slack)

**File:** `/opt/hexis/health-check.py`

```python
#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp
import structlog

logger = logging.getLogger(__name__)
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

HEALTH_URL = "https://api.yourdomain.com/health"
SLACK_WEBHOOK = "${SLACK_WEBHOOK_URL}"
MAX_RESPONSE_TIME = 5.0


async def check_health() -> dict[str, Any]:
    """Check API health and return status."""
    async with aiohttp.ClientSession() as session:
        try:
            start = datetime.now()
            async with session.get(HEALTH_URL, timeout=10) as resp:
                elapsed = (datetime.now() - start).total_seconds()
                data = await resp.json()
                return {
                    "status": "ok" if resp.status == 200 else "degraded",
                    "http_code": resp.status,
                    "response_time_s": elapsed,
                    "services": data.get("services", {}),
                }
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {"status": "down", "error": str(e)}


async def alert_slack(message: str) -> None:
    """Send alert to Slack."""
    if not SLACK_WEBHOOK:
        return

    payload = {
        "text": f":warning: Hexis Alert: {message}",
        "color": "danger",
    }
    async with aiohttp.ClientSession() as session:
        await session.post(SLACK_WEBHOOK, json=payload)


async def main() -> None:
    """Monitor health continuously."""
    while True:
        health = await check_health()

        if health["status"] == "down":
            await alert_slack(f"API is DOWN: {health.get('error')}")
        elif health["response_time_s"] > MAX_RESPONSE_TIME:
            await alert_slack(
                f"API slow: {health['response_time_s']:.2f}s response time"
            )

        logger.info("health_check", **health)
        await asyncio.sleep(60)  # Check every minute


if __name__ == "__main__":
    asyncio.run(main())
```

**Cron:** `/etc/systemd/system/hexis-health-check.service`

```ini
[Unit]
Description=Hexis Health Check
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=hexis
ExecStart=/usr/bin/python3 /opt/hexis/health-check.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 7. CI/CD Pipeline (GitHub Actions)

**File:** `.github/workflows/deploy-prod.yml`

```yaml
name: Deploy to OVH Production

on:
  push:
    branches:
      - main
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_hexis
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      rabbitmq:
        image: rabbitmq:4-alpine
        options: >-
          --health-cmd "rabbitmq-diagnostics -q ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5672:5672

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-fail-under=80 -v

      - name: Run linting
        run: |
          pip install ruff mypy
          ruff check .
          mypy src/ --strict

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Docker images
        uses: docker/build-push-action@v4
        with:
          context: .
          file: ./Dockerfile.worker
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-worker:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-worker:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to OVH VPS
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.OVH_VPS_IP }}
          username: ${{ secrets.OVH_SSH_USER }}
          key: ${{ secrets.OVH_SSH_KEY }}
          script: |
            set -e
            
            # Pull latest code
            cd /opt/hexis
            git fetch origin main
            git checkout origin/main
            
            # Load environment
            source .env
            
            # Pull latest images
            docker compose -f docker-compose.prod.yml pull
            
            # Backup database before deploy
            /opt/hexis/backup.sh
            
            # Restart services (zero-downtime with replicas)
            docker compose -f docker-compose.prod.yml up -d --remove-orphans
            
            # Wait for health check
            sleep 10
            curl -f https://api.yourdomain.com/health || exit 1
            
            echo "Deployment successful!"

      - name: Notify Slack
        if: always()
        uses: slackapi/slack-github-action@v1
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "text": "Hexis Deploy: ${{ job.status }}",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Hexis Production Deploy*\nStatus: ${{ job.status }}\nCommit: ${{ github.sha }}"
                  }
                }
              ]
            }
```

**GitHub Secrets Required:**
- `OVH_VPS_IP`: 123.45.67.89
- `OVH_SSH_USER`: root or deploy user
- `OVH_SSH_KEY`: Private SSH key (generated on VPS)
- `SLACK_WEBHOOK`: For notifications

**Setup SSH Access:**
```bash
# On VPS
ssh-keygen -t ed25519 -f /opt/hexis/deploy_key -N ""
cat /opt/hexis/deploy_key  # Add to GitHub Secrets

# Authorize key
mkdir -p /root/.ssh
echo "YOUR_PUBLIC_KEY" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

---

## 8. SSL Certificates (Let's Encrypt)

**Auto-renewal via Certbot:**

```bash
#!/bin/bash
# /opt/hexis/setup-ssl.sh

sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# Initial certificate
sudo certbot certonly \
    --nginx \
    -d yourdomain.com \
    -d www.yourdomain.com \
    -d api.yourdomain.com \
    --agree-tos \
    --email admin@yourdomain.com \
    --non-interactive

# Test renewal
sudo certbot renew --dry-run

# Enable auto-renewal (cron)
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Verify renewal
sudo systemctl status certbot.timer

# Manual renewal (if needed)
sudo certbot renew --force-renewal
```

**Auto-renewal Cron:**
```bash
# /etc/cron.d/hexis-certbot
0 3 * * * root /usr/bin/certbot renew --quiet && systemctl reload nginx
```

**Monitor Certificate Expiry:**
```bash
# Check expiry date
certbot certificates

# Alert if < 30 days
ssl_expiry_date=$(openssl x509 -enddate -noout -in /etc/letsencrypt/live/yourdomain.com/cert.pem | cut -d= -f2)
echo "SSL expires: $ssl_expiry_date"
```

---

## 9. Log Management

### 9.1 Centralized Log Structure

```
/var/log/hexis/
├── api.log (FastAPI)
├── db.log (PostgreSQL)
├── rabbitmq.log (RabbitMQ)
├── channel_worker.log (Telegram/Discord/WhatsApp)
├── heartbeat_worker.log
├── maintenance_worker.log
└── nginx/
    ├── hexis_api_access.log
    ├── hexis_api_error.log
    ├── hexis_ui_access.log
    └── hexis_ui_error.log
```

### 9.2 Log Rotation (Logrotate)

**File:** `/etc/logrotate.d/hexis`

```
/var/log/hexis/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload hexis || true
    endscript
}

/var/log/nginx/hexis*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        systemctl reload nginx || true
    endscript
}
```

### 9.3 Log Retention Policy

- **Application logs:** 14 days (compressed)
- **Nginx access logs:** 30 days (compressed)
- **Database logs:** 7 days
- **Backup logs:** Permanent (in `/var/backups/`)

### 9.4 Log Monitoring (Search & Alert)

```bash
# Search for errors in last 24h
journalctl --since "24 hours ago" -u hexis | grep -i error

# Count errors per service
grep ERROR /var/log/hexis/*.log | cut -d: -f1 | sort | uniq -c

# Real-time error stream
tail -f /var/log/hexis/*.log | grep -i error
```

---

## 10. Disaster Recovery Plan

### 10.1 RTO & RPO Targets

| Component | RTO | RPO |
|-----------|-----|-----|
| Application | 5 min | 0 min (stateless) |
| Database | 15 min | 1 day (latest backup) |
| Configuration | 5 min | 0 min (Git repo) |

### 10.2 Failure Scenarios

#### Scenario 1: Database Corruption

**Detection:** Health check fails, `pg_isready` timeout  
**Recovery Steps:**
1. Stop application containers: `docker compose stop api channel_worker`
2. Restore from latest backup:
   ```bash
   gunzip < /var/backups/hexis/latest.sql.gz | \
     docker exec -i hexis_brain psql -U hexis_prod_user -d hexis_memory
   ```
3. Verify integrity: `docker exec hexis_brain psql -U hexis_prod_user -c "SELECT COUNT(*) FROM users;"`
4. Restart services: `docker compose up -d`
5. Test health endpoint: `curl https://api.yourdomain.com/health`

#### Scenario 2: API Pod Crash

**Detection:** Nginx upstream unavailable  
**Recovery Steps:**
1. Check logs: `docker logs hexis_api`
2. Restart pod: `docker compose restart api`
3. Monitor: `docker compose logs -f api`
4. If persistent, rollback: `git checkout HEAD~1 && docker compose pull && docker compose up -d`

#### Scenario 3: RabbitMQ Loss (Queue Data)

**Detection:** Channel workers unable to connect  
**Recovery Steps:**
1. Restart RabbitMQ: `docker compose restart rabbitmq`
2. Recreate queues (idempotent): Application auto-declares on startup
3. Re-send failed messages from DLQ (Dead Letter Queue)
4. Monitor: `docker compose logs -f rabbitmq`

#### Scenario 4: VPS Hardware Failure

**Detection:** SSH timeout, no heartbeat  
**Recovery Steps:**
1. Order replacement VPS from OVH (5-10 min)
2. Deploy fresh instance using automated setup script
3. Restore database from S3: `aws s3 cp s3://hexis-backups/.../latest.sql.gz . && gunzip < ...`
4. Restore `/opt/hexis/` from Git: `git clone https://github.com/quixiai/hexis.git /opt/hexis`
5. Update DNS A record to new IP (propagate ~5 min)

### 10.3 Automated Recovery Script

**File:** `/opt/hexis/disaster-recovery.sh`

```bash
#!/bin/bash
# Automated disaster recovery

set -e

BACKUP_DATE="${1:-latest}"
RECOVERY_LOG="/var/log/hexis-recovery-$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RECOVERY_LOG"; }

log "Starting disaster recovery from backup: $BACKUP_DATE"

# 1. Backup current state (if available)
if docker ps | grep -q hexis_brain; then
    log "Backing up current database..."
    /opt/hexis/backup.sh || true
fi

# 2. Stop application
log "Stopping application containers..."
docker compose stop api channel_worker heartbeat_worker maintenance_worker || true

# 3. Download backup if remote
if [[ "$BACKUP_DATE" != "latest" ]]; then
    log "Downloading backup from OVH Object Storage..."
    aws s3 cp "s3://hexis-backups/postgresql/$BACKUP_DATE.sql.gz" /tmp/ \
        --region gra --endpoint-url https://s3.gra.io.cloud.ovh.net
    BACKUP_FILE="/tmp/$BACKUP_DATE.sql.gz"
else
    BACKUP_FILE=$(ls -t /var/backups/hexis/*.sql.gz | head -1)
    log "Using local backup: $BACKUP_FILE"
fi

# 4. Restore database
log "Restoring database..."
gunzip -c "$BACKUP_FILE" | docker exec -i hexis_brain psql -U hexis_prod_user -d hexis_memory

# 5. Verify integrity
log "Verifying database integrity..."
docker exec hexis_brain psql -U hexis_prod_user -d hexis_memory -c \
    "SELECT COUNT(*) as user_count FROM users;"

# 6. Restart services
log "Restarting services..."
docker compose up -d

# 7. Health check
log "Waiting for health check..."
sleep 10
if curl -f https://api.yourdomain.com/health; then
    log "Recovery SUCCESSFUL"
    exit 0
else
    log "Recovery FAILED - manual intervention required"
    exit 1
fi
```

**Usage:**
```bash
# Restore from latest backup
/opt/hexis/disaster-recovery.sh

# Restore from specific date
/opt/hexis/disaster-recovery.sh 20260310_020000
```

### 10.4 Testing Recovery (Monthly)

**Procedure:**
1. Spin up test instance with fresh Docker
2. Run recovery script against staging database
3. Verify data integrity: row counts, key relationships
4. Document results and timestamp

---

## 11. Cost Breakdown

### 11.1 Infrastructure (Monthly)

| Component | Cost | Notes |
|-----------|------|-------|
| **OVH VPS 4** (50 users) | 16.99€ | 4 vCPU, 8GB RAM, 80GB SSD |
| **OVH Object Storage** | 6.00€ | ~50GB backups/month @ 0.12€/GB |
| **Domain Name** (yourdomain.com) | 2.50€ | GoDaddy/Route53 (annual: ~30€) |
| **SSL Certificate** | 0€ | Let's Encrypt (free) |
| **Email/DNS** | 0€ | Cloudflare (free tier) |
| **Monitoring** (UptimeRobot) | 5.99€ | Basic uptime monitoring |
| **Subtotal Infrastructure** | **31.48€/month** | ~€377/year |

### 11.2 Software (Monthly)

| Component | Cost | Notes |
|-----------|------|-------|
| **Anthropic Claude Max** | 174.00€ | API calls (5K requests/mo est.) |
| **GitHub Pro** (optional) | 4.00€ | Private repos, CI/CD minutes |
| **Slack** (optional) | 8.00€ | Team communication |
| **Subtotal Software** | **186.00€/month** | ~€2,232/year |

### 11.3 Scaling Costs (100 users)

| Component | Cost | Notes |
|-----------|------|-------|
| **OVH Dedicated Starter XE** | 24.99€ | Upgrade from VPS |
| **Object Storage** (10% growth) | 6.60€ | ~60GB backup volume |
| **Claude API** (2x usage) | 348.00€ | Higher concurrency |
| **Subtotal (100 users)** | **379.59€/month** | ~€4,555/year |

### 11.4 Breakdown: Why Claude Max (No Ollama)?

**Ollama Self-Hosted Cost Analysis:**

| Approach | Monthly Cost | Pros | Cons |
|----------|------------|------|------|
| **Claude Max API** | 174€ | Usage-based, no infra, latest models | Higher marginal cost per request |
| **Ollama + GPU Server** | 80-150€ (server) + 200€ (GPU rental) | Unlimited requests | Infra overhead, older models, cold starts |
| **Ollama + Local Hardware** | 0€ (amortized) | No monthly cost | 50GB+ VRAM (expensive), model updates, latency |

**Conclusion:** Claude Max is optimal for <500 concurrent users. Revisit when hitting API rate limits.

### 11.5 ROI & Pricing Model (Business)

**Assuming 3-tier subscription (see business-model.md):**

| Tier | Price/mo | Min Users | Monthly Revenue |
|------|----------|-----------|-----------------|
| **Starter** | 49€ | 1 | 49€ |
| **Pro** | 149€ | 5 | 745€ |
| **Enterprise** | 499€ | 1 | 499€ |

**Break-even (50 customers):**
- 30x Starter (30€ users) = 1,470€
- 15x Pro (75€ users) = 2,235€
- 5x Enterprise (5€ users) = 2,495€
- **Total:** 6,200€/month revenue
- **Costs:** ~380€/month infrastructure
- **Gross Margin:** 94%

---

## 12. Deployment Checklist

### Pre-Deployment

- [ ] Domain registered & DNS pointing to OVH VPS IP
- [ ] SSH key generated & stored securely
- [ ] GitHub repo with CI/CD workflows configured
- [ ] `.env` file created with production values (NOT committed)
- [ ] OVH Object Storage bucket created (`hexis-backups`)
- [ ] AWS CLI configured with S3 credentials
- [ ] Slack webhook created for notifications
- [ ] SSL certificate request prepared (Let's Encrypt)
- [ ] Uptime monitoring configured (UptimeRobot/Pingdom)
- [ ] DMS (disaster recovery) script tested on staging

### Day 0: Initial Deployment

```bash
# 1. SSH into VPS
ssh root@YOUR_OVH_IP

# 2. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 3. Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker root
docker compose version

# 4. Clone Hexis repository
git clone https://github.com/quixiai/hexis.git /opt/hexis
cd /opt/hexis

# 5. Create production environment
cp .env.example .env
# EDIT .env with production values

# 6. Setup firewall
bash /opt/hexis/setup-firewall.sh

# 7. Setup SSL certificates
bash /opt/hexis/setup-ssl.sh

# 8. Configure Nginx
sudo cp /opt/hexis/nginx.conf /etc/nginx/sites-available/hexis-api.conf
sudo nginx -t && sudo systemctl restart nginx

# 9. Start containers
docker compose -f docker-compose.prod.yml --profile active up -d

# 10. Verify health
curl https://api.yourdomain.com/health

# 11. Setup backup script
sudo install -m 0755 /opt/hexis/backup.sh /usr/local/bin/
echo "0 2 * * * root /usr/local/bin/backup.sh" | sudo tee /etc/cron.d/hexis-backup

# 12. Test disaster recovery script
bash /opt/hexis/disaster-recovery.sh
```

### Post-Deployment

- [ ] Verify all containers are healthy: `docker compose ps`
- [ ] Test API endpoint: `curl -v https://api.yourdomain.com/health`
- [ ] Test frontend: `https://yourdomain.com` (check in browser)
- [ ] Verify database: `docker exec hexis_brain psql -U hexis_prod_user -d hexis_memory -c "SELECT 1;"`
- [ ] Test backup: `bash /opt/hexis/backup.sh && ls -lh /var/backups/hexis/`
- [ ] Test S3 upload: Check OVH Object Storage bucket
- [ ] Verify logs: `docker compose logs -f --tail=50`
- [ ] Check firewall: `sudo ufw status verbose`
- [ ] Monitor Slack/email for alerts
- [ ] Update team documentation with IPs/credentials

### Ongoing (Weekly)

- [ ] Monitor logs for errors: `grep -i error /var/log/hexis/*.log`
- [ ] Check SSL expiry: `certbot certificates`
- [ ] Verify backup completion: `ls -lh /var/backups/hexis/ | tail -5`
- [ ] Review GitHub Actions deployment logs
- [ ] Test health endpoint: `curl https://api.yourdomain.com/health`

### Ongoing (Monthly)

- [ ] Run disaster recovery drill: `bash /opt/hexis/disaster-recovery.sh`
- [ ] Review and rotate backups
- [ ] Audit firewall rules: `sudo ufw status verbose`
- [ ] Update Docker images: `docker compose pull && docker compose up -d`
- [ ] Review cost report (OVH billing)

---

## Summary & Next Steps

### What's Included

✓ OVH infrastructure recommendation (VPS 4 → Dedicated for scaling)  
✓ Production Docker Compose (removed Ollama, added Claude API integration)  
✓ Nginx configuration (SSL, rate limiting, IP whitelist)  
✓ UFW firewall rules (SSH + HTTPS only)  
✓ Automated backup strategy (daily local + weekly S3)  
✓ Health-based monitoring (no Prometheus overhead initially)  
✓ GitHub Actions CI/CD pipeline  
✓ Let's Encrypt auto-renewal  
✓ Centralized log management with rotation  
✓ Disaster recovery procedures & scripts  
✓ Complete cost breakdown (380€/month for 50 users)  

### Immediate Actions

1. **Purchase OVH VPS 4** (~16.99€/mo)
2. **Configure domain DNS** (A record → OVH IP)
3. **Create `.env` file** with production credentials
4. **Run initial deployment** using checklist above
5. **Test health check** & verify all containers running
6. **Enable GitHub Actions** for automated future deploys

### Future Optimizations (Post-Launch)

- Prometheus + Grafana for detailed metrics (once stable)
- Database replication (primary + standby) for HA
- CDN integration (Cloudflare) for frontend assets
- Multi-region backups (OVH regions: GRA, SBG, BHS)
- Load balancer (if >100 concurrent users)
- API rate limiting per-user (currently per-IP)

---

## References

- **OVH VPS Specs:** https://www.ovh.com/world/vps/
- **Docker Compose Best Practices:** https://docs.docker.com/compose/production/
- **Nginx SSL:** https://nginx.org/en/docs/http/ngx_http_ssl_module.html
- **Let's Encrypt:** https://letsencrypt.org/
- **PostgreSQL Backups:** https://www.postgresql.org/docs/16/backup-dump.html
- **Disaster Recovery Planning:** https://en.wikipedia.org/wiki/Disaster_recovery

---

**Last Updated:** 2026-03-14  
**Owner:** DevOps Lead  
**Status:** Ready for Implementation
