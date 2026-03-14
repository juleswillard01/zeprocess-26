# MEGA QUIXAI Infrastructure

Production-ready infrastructure for autonomous AI agents running 24/7.

## Quick Start

```bash
# 1. Initialize secrets
./scripts/init-secrets.sh

# 2. Configure environment
cp config/.env.example ../.env
nano ../.env

# 3. Start services
cd docker
docker-compose up -d

# 4. Verify health
curl http://localhost:3000/health

# 5. Start agents (on VPS)
sudo systemctl start mega-quixai.target
```

## Directory Structure

```
infra/
├── docker/          # Docker Compose + Dockerfile
├── nginx/           # Nginx reverse proxy config
├── systemd/         # Systemd service files
├── scripts/         # Setup and maintenance scripts
├── config/          # Configuration files (schema, logging, env)
└── .secrets/        # Secrets (gitignored, generated)
```

## Main Components

### Docker Services

- **nginx** : Reverse proxy, SSL termination
- **api** : FastAPI application
- **postgres** : PostgreSQL 15 + pgvector
- **redis** : Cache and task queue
- **langfuse** : LLM observability

Start all:
```bash
cd docker && docker-compose up -d
```

### Systemd Agents

Three autonomous agents running in background:

```bash
sudo systemctl start mega-quixai.target
sudo systemctl status mega-quixai.target
```

Check individual agents:
```bash
sudo journalctl -u mega-quixai-agent-seduction -f
sudo journalctl -u mega-quixai-agent-closing -f
sudo journalctl -u mega-quixai-agent-acquisition -f
```

### Backup & Restore

Daily backups to `/var/backups/mega-quixai/`:

```bash
# Backup now
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh /var/backups/mega-quixai/mega-quixai-full-YYYYMMDD.sql.gz
```

### Firewall Setup

```bash
sudo ./scripts/setup-firewall.sh
```

Opens: 22 (SSH), 80 (HTTP), 443 (HTTPS)
Closes: 5432 (PostgreSQL), 6379 (Redis), 3000 (API)

## Configuration

See `.env.example` for all available options:
- Database credentials (auto-generated)
- API keys (Anthropic, LangFuse)
- Logging level
- Monitoring ports

## Monitoring

Health endpoint:
```bash
curl http://localhost/health
```

Check agent status:
```bash
docker exec mega-quixai-redis redis-cli get agent:seduction:health
```

View logs:
```bash
docker-compose logs -f api
sudo journalctl -u mega-quixai.target -f
```

## Cost

- VPS (Hetzner 4core/8GB): €6.90/month
- Backup storage: ~€2/month
- API calls: ~€8/month
- **Total: ~€17/month**

## Security Notes

- All secrets in `.secrets/` (gitignored)
- Non-root containers
- SSL/TLS with Let's Encrypt
- Firewall rules by default
- Database isolated to internal network

## Troubleshooting

Agent not starting?
```bash
sudo journalctl -u mega-quixai-agent-seduction -n 50
docker-compose logs postgres
curl http://localhost/health
```

Port already in use?
```bash
lsof -i :3000  # Find process
kill -9 <PID>  # Kill it
```

Disk full?
```bash
find /var/log -name "*.log" -mtime +30 -delete
docker system prune -a
```

## References

- Infrastructure guide: [../INFRASTRUCTURE.md](../INFRASTRUCTURE.md)
- Deployment guide: [../DEPLOYMENT.md](../DEPLOYMENT.md)
