# MEGA QUIXAI — Deployment Guide

Step-by-step instructions for deploying 3 autonomous agents on a VPS.

---

## Prerequisites

- [ ] GitHub account with repo access
- [ ] Anthropic API key (from console.anthropic.com)
- [ ] LangFuse account (langfuse.com)
- [ ] Domain name (example: mega-quixai.com)
- [ ] Admin email for SSL certificates

---

## Phase 1: VPS Setup (30 minutes)

### 1.1 Provision VPS

**Hetzner Cloud**:

1. Login to cloud.hetzner.com
2. Create new server
   - Image: Ubuntu 24.04 LTS
   - Type: Standard 4 (4 cores, 8GB RAM, 40GB SSD)
   - Location: Helsinki or Nuremberg (EU)
   - Add SSH key for authentication
3. Write down IP address (example: 203.0.113.45)

### 1.2 Initial SSH Connection

```bash
# Update ~/.ssh/config
cat >> ~/.ssh/config << EOF
Host mega-quixai
    HostName 203.0.113.45
    User root
    IdentityFile ~/.ssh/hetzner_key
EOF

# SSH in
ssh mega-quixai
```

### 1.3 System Setup

```bash
#!/bin/bash
# Run as root on VPS

# Update packages
apt-get update && apt-get upgrade -y

# Install essential tools
apt-get install -y \
    curl wget git \
    build-essential \
    fail2ban ufw \
    htop tree \
    jq vim

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Verify Docker
docker --version
docker-compose --version

# Create application user
useradd -m -s /bin/bash quixai
usermod -aG docker quixai
usermod -aG sudo quixai

# Setup fail2ban
systemctl enable fail2ban
systemctl start fail2ban

echo "✓ System setup complete"
```

### 1.4 Clone Repository

```bash
su - quixai

# Clone repo
git clone https://github.com/your-org/mega-quixai.git /opt/mega-quixai
cd /opt/mega-quixai

# Setup permissions
sudo chown -R quixai:quixai /opt/mega-quixai
chmod -R 755 /opt/mega-quixai/infra/scripts
```

---

## Phase 2: Secrets & Configuration (15 minutes)

### 2.1 Initialize Secrets

```bash
cd /opt/mega-quixai/infra/scripts
./init-secrets.sh

# This creates:
# - .secrets/pg_password.txt (auto-generated)
# - .secrets/anthropic_key.txt (from prompt)
# - .secrets/langfuse_secret.txt (from prompt)

# Verify
ls -la /opt/mega-quixai/.secrets/
```

### 2.2 Configure Environment

```bash
cd /opt/mega-quixai/infra

# Copy template
cp config/.env.example ../.env

# Edit configuration
nano ../.env

# Required changes:
# DOMAIN_NAME=mega-quixai.com
# POSTGRES_DB=mega_quixai
# LOG_LEVEL=info
# ENVIRONMENT=production

# Verify
cat ../.env | grep -v "^#" | grep -v "^$"
```

### 2.3 Add to .gitignore

```bash
# Make sure .secrets is never committed
echo ".secrets/" >> /opt/mega-quixai/.gitignore
echo ".env" >> /opt/mega-quixai/.gitignore

# Verify
git check-ignore .secrets .env
```

---

## Phase 3: Firewall Setup (10 minutes)

### 3.1 Configure UFW

```bash
cd /opt/mega-quixai/infra/scripts

# Run as root
sudo ./setup-firewall.sh

# Verify (should allow 22, 80, 443 only)
sudo ufw status verbose

# Important: Your SSH session stays open during setup
```

### 3.2 Test Firewall

```bash
# From your laptop, verify SSH still works
ssh mega-quixai

# Port scan (internal only)
sudo netstat -tlnp | grep LISTEN
```

---

## Phase 4: Docker Compose (20 minutes)

### 4.1 Start Services

```bash
cd /opt/mega-quixai/infra/docker

# Pull images (first time, ~2-3 min)
docker-compose pull

# Start all services
docker-compose up -d

# Watch startup logs
docker-compose logs -f

# Wait ~30 seconds for all containers to start
```

### 4.2 Verify Container Health

```bash
# Check status
docker-compose ps

# Should see:
# - nginx: healthy
# - api: healthy
# - postgres: healthy
# - redis: healthy
# - langfuse: healthy

# If any are unhealthy, check logs:
docker-compose logs api
docker-compose logs postgres
```

### 4.3 Test Endpoints

```bash
# Health check
curl http://localhost/health

# Should return JSON:
# {"status": "ok", "components": {...}}

# Test database
docker exec mega-quixai-postgres pg_isready -U quixai_user -d mega_quixai
# accepting connections

# Test Redis
docker exec mega-quixai-redis redis-cli ping
# PONG
```

---

## Phase 5: SSL/TLS Setup (15 minutes)

### 5.1 Obtain Certificate

```bash
# Install certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Get certificate (standalone mode)
sudo certbot certonly --standalone \
    -d mega-quixai.com \
    -d www.mega-quixai.com \
    -m admin@example.com \
    --agree-tos \
    --non-interactive \
    --expand

# Certificates stored in:
# /etc/letsencrypt/live/mega-quixai.com/

# Copy to Docker volume
sudo cp /etc/letsencrypt/live/mega-quixai.com/fullchain.pem \
    /opt/mega-quixai/infra/ssl/
sudo cp /etc/letsencrypt/live/mega-quixai.com/privkey.pem \
    /opt/mega-quixai/infra/ssl/
sudo chown quixai:quixai /opt/mega-quixai/infra/ssl/*
```

### 5.2 Test HTTPS

```bash
# Restart nginx to load certs
docker-compose restart nginx

# Test (ignore self-signed for now)
curl -k https://localhost/health

# Test from your laptop
curl -k https://mega-quixai.com/health
```

### 5.3 Auto-Renewal

```bash
# Setup cron job
sudo crontab -e

# Add this line:
0 12 * * * certbot renew --quiet && docker exec mega-quixai-nginx nginx -s reload

# Verify
sudo crontab -l
```

---

## Phase 6: Systemd Agents (15 minutes)

### 6.1 Install Service Files

```bash
# Copy systemd files
sudo cp /opt/mega-quixai/infra/systemd/*.service /etc/systemd/system/
sudo cp /opt/mega-quixai/infra/systemd/*.target /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Verify files are found
sudo systemctl list-unit-files | grep mega-quixai
```

### 6.2 Start Agents

```bash
# Start all agents via target
sudo systemctl start mega-quixai.target

# Enable auto-start on reboot
sudo systemctl enable mega-quixai.target

# Check status
sudo systemctl status mega-quixai.target

# View each agent
sudo systemctl status mega-quixai-agent-seduction
sudo systemctl status mega-quixai-agent-closing
sudo systemctl status mega-quixai-agent-acquisition
```

### 6.3 Monitor Agent Logs

```bash
# Follow all agents
sudo journalctl -u mega-quixai.target -f

# Follow individual agent
sudo journalctl -u mega-quixai-agent-seduction -f -n 50

# Check if healthy (should be running)
ps aux | grep "mega-quixai-agent"
```

---

## Phase 7: Backup Setup (10 minutes)

### 7.1 Create Backup Directory

```bash
sudo mkdir -p /var/backups/mega-quixai
sudo chown quixai:quixai /var/backups/mega-quixai
sudo chmod 755 /var/backups/mega-quixai

# Backup logs
sudo mkdir -p /var/log/mega-quixai
sudo chown quixai:quixai /var/log/mega-quixai
```

### 7.2 Schedule Backups

```bash
# Edit crontab for quixai user
sudo crontab -u quixai -e

# Add this line (daily at 2 AM UTC):
0 2 * * * /opt/mega-quixai/infra/scripts/backup.sh

# Verify
sudo crontab -u quixai -l
```

### 7.3 Test Backup

```bash
# Run manually
/opt/mega-quixai/infra/scripts/backup.sh

# Verify file created
ls -lh /var/backups/mega-quixai/

# Test restore (do NOT restore on prod yet)
# gunzip -c /var/backups/mega-quixai/mega-quixai-full-*.sql.gz | head -20
```

---

## Phase 8: Verification (10 minutes)

### 8.1 Run Deployment Check

```bash
cd /opt/mega-quixai/infra/scripts
sudo ./post-deploy-check.sh

# Expected output:
# ✓ Docker Services Status: All containers running
# ✓ Health Checks: {"status": "ok"}
# ✓ Database Connection: accepting connections
# ✓ Redis Connection: PONG
# ✓ Systemd Services: All agents active
# ✓ Firewall Rules: 22, 80, 443 open
```

### 8.2 Full System Test

```bash
# 1. Test API health
curl https://mega-quixai.com/health

# 2. Check agent heartbeat (via Redis)
docker exec mega-quixai-redis redis-cli get agent:seduction:health
# Should see: ok:iter=123 or similar

# 3. Check database
docker exec mega-quixai-postgres \
    psql -U quixai_user -d mega_quixai \
    -c "SELECT COUNT(*) FROM leads;"

# 4. Monitor agent activity
sudo journalctl -u mega-quixai-agent-seduction -n 10
```

---

## Phase 9: Monitoring Dashboard (Optional, 20 minutes)

### 9.1 Setup Grafana (Optional)

```bash
# Add Grafana to docker-compose (optional step)
docker run -d \
    -p 3002:3000 \
    -e GF_SECURITY_ADMIN_PASSWORD=admin \
    --name mega-quixai-grafana \
    grafana/grafana:latest

# Access at http://localhost:3002
# Add Prometheus data source: http://prometheus:9090
```

### 9.2 Import Dashboard

```bash
# Dashboard templates available in:
# /opt/mega-quixai/infra/config/grafana-dashboard.json
```

---

## Phase 10: CI/CD Setup (10 minutes)

### 10.1 GitHub Secrets

```bash
# Go to: https://github.com/your-org/mega-quixai/settings/secrets/actions

# Add secrets:
1. PROD_DEPLOY_KEY
   # Get your SSH private key:
   cat ~/.ssh/hetzner_key
   # Paste entire content

2. PROD_DEPLOY_HOST
   # Value: your VPS IP or domain
   # Example: 203.0.113.45

3. GITHUB_TOKEN
   # Auto-provided by GitHub
```

### 10.2 Test Deployment Pipeline

```bash
# On your laptop, push a test commit
git add .
git commit -m "test: CI/CD pipeline"
git push origin main

# Monitor at: https://github.com/your-org/mega-quixai/actions

# Should run: lint → test → build → deploy (approval required)
```

---

## Post-Deployment Checklist

- [ ] VPS is running (Hetzner)
- [ ] SSH access confirmed
- [ ] Docker services healthy
- [ ] API responds to /health
- [ ] Database initialized
- [ ] Redis running
- [ ] Firewall configured (22, 80, 443 open)
- [ ] SSL certificate obtained
- [ ] Agents starting and running
- [ ] Backups scheduled
- [ ] Logs centralized
- [ ] CI/CD pipeline working
- [ ] Domain pointing to VPS
- [ ] Monitoring dashboard accessible

---

## Troubleshooting

### Containers won't start

```bash
# Check logs
docker-compose logs -f

# Restart from scratch
docker-compose down
docker-compose up -d

# Check volumes
docker volume ls

# Check network
docker network ls
```

### SSL certificate errors

```bash
# Renew certificate
sudo certbot renew --force-renewal

# Copy to ssl directory
sudo cp /etc/letsencrypt/live/mega-quixai.com/* /opt/mega-quixai/infra/ssl/

# Restart nginx
docker-compose restart nginx
```

### Agents not running

```bash
# Check status
sudo systemctl status mega-quixai.target

# Check logs
sudo journalctl -u mega-quixai-agent-seduction -n 50

# Restart
sudo systemctl restart mega-quixai.target

# Test database connection
docker-compose exec api psql -h postgres -U quixai_user -d mega_quixai -c "SELECT 1"
```

### High memory usage

```bash
# Monitor containers
docker stats

# Check PostgreSQL
docker exec mega-quixai-postgres ps aux

# Restart if needed
docker-compose restart postgres
```

---

## Next Steps

1. **Configure CI/CD** : Update `.github/workflows/deploy.yml` with your VPS IP
2. **Setup monitoring** : Add alerts to Grafana
3. **Configure backups** : Test restore procedure
4. **Load testing** : Simulate agent traffic
5. **Scale if needed** : Add more VPS when leads > 5000/day

---

## Support

For issues or questions:
1. Check `/var/log/mega-quixai/` logs
2. Check Docker logs: `docker-compose logs -f service_name`
3. Check systemd logs: `journalctl -u mega-quixai-* -n 50`
4. Review nginx config: `/opt/mega-quixai/infra/nginx/nginx.conf`

---

**Deployment Time**: ~2-3 hours  
**Expertise Required**: Basic Linux + Docker knowledge  
**Monthly Cost**: ~€18-20

