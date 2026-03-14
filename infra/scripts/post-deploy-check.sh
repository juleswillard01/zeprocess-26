#!/bin/bash
set -euo pipefail

echo "=== MEGA QUIXAI Post-Deployment Verification ==="
echo ""

# Check Docker services
echo "✓ Docker Services Status:"
docker-compose ps || echo "  ERROR: docker-compose not running"
echo ""

# Check health endpoints
echo "✓ Health Checks:"
curl -s http://localhost/health | jq . || echo "  WARNING: API health check failed"
echo ""

# Check database
echo "✓ Database Connection:"
docker exec mega-quixai-postgres pg_isready -U quixai_user -d mega_quixai || echo "  ERROR: PostgreSQL not ready"
echo ""

# Check Redis
echo "✓ Redis Connection:"
docker exec mega-quixai-redis redis-cli ping || echo "  ERROR: Redis not responding"
echo ""

# Check systemd agents
echo "✓ Systemd Services:"
sudo systemctl is-active mega-quixai.target || echo "  WARNING: mega-quixai.target not active"
for agent in seduction closing acquisition; do
    status=$(sudo systemctl is-active "mega-quixai-agent-$agent" 2>/dev/null || echo "inactive")
    echo "  - mega-quixai-agent-$agent: $status"
done
echo ""

# Check firewall
echo "✓ Firewall Rules:"
sudo ufw status | head -10
echo ""

# Check certificates
echo "✓ SSL Certificates:"
ls -lh /etc/nginx/ssl/ 2>/dev/null || echo "  NOTE: No SSL certs found yet"
echo ""

# Check disk space
echo "✓ Disk Space:"
df -h /opt/mega-quixai/ | tail -1
echo ""

# Check logs
echo "✓ Recent Errors (last 5 lines):"
docker-compose logs api | tail -5 || true
echo ""

echo "=== Deployment Check Complete ==="
