# RAG Operations & Deployment Guide

## Production Deployment

### Environment Setup

```bash
# Create .env file
cat > /home/jules/Documents/3-git/zeprocess/main/.env << 'EOF'
# Database
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@localhost:5432/rag_videos
DB_POOL_SIZE=10
DB_TIMEOUT=30

# Embedding
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # or cuda for GPU
EMBEDDING_BATCH_SIZE=32

# Search
SEARCH_METHOD=hybrid
SEARCH_TOP_K=5
SEARCH_THRESHOLD=0.3

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
METRICS_PORT=8000

# MCP Server
MCP_HOST=0.0.0.0
MCP_PORT=5000
EOF

# Load environment
export $(cat /home/jules/Documents/3-git/zeprocess/main/.env | xargs)
```

### Docker Deployment (Optional)

```dockerfile
# Dockerfile for MCP server
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY scripts/ ./scripts/
COPY data/ ./data/

# Expose MCP port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# Run MCP server
CMD ["python", "scripts/mcp_server.py"]
```

```bash
# Build and run
docker build -t rag-mcp:latest .
docker run -d \
  --name rag-mcp \
  -p 5000:5000 \
  -e DATABASE_URL=postgresql://... \
  --restart=always \
  rag-mcp:latest

# Check logs
docker logs -f rag-mcp
```

---

## Operational Monitoring

### Key Metrics to Track

```python
# metrics_dashboard.py

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
import psycopg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RAGMetrics:
    """Daily RAG performance metrics."""
    date: str
    total_queries: int
    avg_latency_ms: float
    p95_latency_ms: float
    semantic_queries: int
    keyword_queries: int
    hybrid_queries: int
    graph_queries: int
    avg_result_score: float
    chunks_used: int
    unique_chunks: int
    conversion_rate: float  # % of queries that led to conversion

class MetricsCollector:
    """Collect and report RAG metrics."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def collect_daily_metrics(self) -> RAGMetrics:
        """Collect metrics for past 24 hours."""
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # Query stats
                cur.execute(
                    """
                    SELECT
                        DATE(created_at)::text as date,
                        COUNT(*) as total_queries,
                        ROUND(AVG(retrieval_time_ms)::NUMERIC, 2) as avg_latency,
                        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
                            ORDER BY retrieval_time_ms
                        )::NUMERIC, 2) as p95_latency,
                        COUNT(*) FILTER (WHERE retrieval_method = 'semantic') as semantic,
                        COUNT(*) FILTER (WHERE retrieval_method = 'keyword') as keyword,
                        COUNT(*) FILTER (WHERE retrieval_method = 'hybrid') as hybrid,
                        COUNT(*) FILTER (WHERE retrieval_method = 'graph') as graph,
                        ROUND(AVG(top_match_score)::NUMERIC, 3) as avg_score,
                        SUM(chunk_count) as chunks_used,
                        COUNT(DISTINCT UNNEST(retrieved_chunk_ids)) as unique_chunks,
                        ROUND(
                            COUNT(*) FILTER (WHERE lead_conversion)::FLOAT /
                            NULLIF(COUNT(*), 0) * 100,
                            2
                        ) as conversion_rate
                    FROM rag_events
                    WHERE created_at > CURRENT_DATE
                    GROUP BY DATE(created_at)
                    """
                )
                row = cur.fetchone()

        if not row:
            return None

        return RAGMetrics(
            date=row[0],
            total_queries=row[1],
            avg_latency_ms=row[2],
            p95_latency_ms=row[3],
            semantic_queries=row[4],
            keyword_queries=row[5],
            hybrid_queries=row[6],
            graph_queries=row[7],
            avg_result_score=row[8],
            chunks_used=row[9],
            unique_chunks=row[10],
            conversion_rate=row[11],
        )

    def alert_if_degradation(self, metrics: RAGMetrics, threshold_latency_ms: float = 300):
        """Alert if metrics degrade."""
        alerts = []

        if metrics.p95_latency_ms > threshold_latency_ms:
            alerts.append(
                f"WARN: Search latency degraded (p95={metrics.p95_latency_ms}ms, "
                f"target={threshold_latency_ms}ms)"
            )

        if metrics.conversion_rate < 20:
            alerts.append(
                f"WARN: Conversion rate low ({metrics.conversion_rate}%)"
            )

        if metrics.unique_chunks < 100 and metrics.total_queries > 50:
            alerts.append(
                "INFO: Low chunk diversity - consider re-chunking"
            )

        for alert in alerts:
            logger.warning(alert)

        return alerts

    def print_dashboard(self, metrics: RAGMetrics):
        """Print pretty dashboard."""
        if not metrics:
            print("No metrics collected yet")
            return

        print("\n" + "="*60)
        print(f"RAG METRICS - {metrics.date}")
        print("="*60)

        print(f"\nQuery Performance:")
        print(f"  Total queries:        {metrics.total_queries:6d}")
        print(f"  Avg latency:          {metrics.avg_latency_ms:6.1f} ms")
        print(f"  P95 latency:          {metrics.p95_latency_ms:6.1f} ms")

        print(f"\nMethod Distribution:")
        print(f"  Semantic:  {metrics.semantic_queries:4d} ({100*metrics.semantic_queries/max(1,metrics.total_queries):5.1f}%)")
        print(f"  Keyword:   {metrics.keyword_queries:4d} ({100*metrics.keyword_queries/max(1,metrics.total_queries):5.1f}%)")
        print(f"  Hybrid:    {metrics.hybrid_queries:4d} ({100*metrics.hybrid_queries/max(1,metrics.total_queries):5.1f}%)")
        print(f"  Graph:     {metrics.graph_queries:4d} ({100*metrics.graph_queries/max(1,metrics.total_queries):5.1f}%)")

        print(f"\nContent Engagement:")
        print(f"  Avg result score:     {metrics.avg_result_score:6.3f}")
        print(f"  Chunks used:          {metrics.chunks_used:6d}")
        print(f"  Unique chunks:        {metrics.unique_chunks:6d}")

        print(f"\nBusiness Impact:")
        print(f"  Conversion rate:      {metrics.conversion_rate:6.1f}%")

        print("\n" + "="*60 + "\n")
```

### Alerting Setup

```bash
# Create monitoring script
cat > /home/julius/Documents/3-git/zeprocess/main/scripts/monitor.sh << 'EOF'
#!/bin/bash

# Monitor RAG health every 5 minutes

DB_URL="postgresql://postgres:dev@localhost:5432/rag_videos"
ALERT_EMAIL="your-email@example.com"

while true; do
    # Check query latency
    LATENCY=$(psql "$DB_URL" -tc "
        SELECT ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
            ORDER BY retrieval_time_ms
        )::NUMERIC, 2)
        FROM rag_events
        WHERE created_at > NOW() - INTERVAL '5 minutes'
    " | xargs)

    if (( $(echo "$LATENCY > 300" | bc -l) )); then
        echo "ALERT: High latency detected: ${LATENCY}ms"
        # Send alert (email, Slack, etc)
    fi

    # Check database connection
    psql "$DB_URL" -c "SELECT 1" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "ALERT: Database connection failed"
    fi

    sleep 300
done
EOF

chmod +x /home/julius/Documents/3-git/zeprocess/main/scripts/monitor.sh
```

---

## Backup & Recovery

### Backup Strategy

```bash
# Daily backup of embeddings
cat > /home/julius/Documents/3-git/zeprocess/main/scripts/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/backups/rag_database"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="rag_videos"

mkdir -p "$BACKUP_DIR"

# Full database backup
pg_dump -d "$DB_NAME" -Fc -b > "$BACKUP_DIR/rag_$TIMESTAMP.dump"

# Keep only last 30 days of backups
find "$BACKUP_DIR" -name "rag_*.dump" -mtime +30 -delete

echo "Backup complete: rag_$TIMESTAMP.dump"
EOF

chmod +x /home/julius/Documents/3-git/zeprocess/main/scripts/backup.sh

# Schedule daily
(crontab -l; echo "0 2 * * * /home/julius/Documents/3-git/zeprocess/main/scripts/backup.sh") | crontab -
```

### Recovery Procedure

```bash
# If database corrupted:

# 1. Stop MCP server
systemctl stop mcp-rag

# 2. Restore from backup
pg_restore -d rag_videos "$BACKUP_DIR/rag_20260314_020000.dump"

# 3. Verify integrity
psql -d rag_videos -c "SELECT COUNT(*) FROM video_chunks;"

# 4. Restart MCP
systemctl start mcp-rag

# 5. Test search functionality
curl -X POST http://localhost:5000/search_content \
  -H "Content-Type: application/json" \
  -d '{"query":"test query"}'
```

---

## Performance Tuning

### Database Optimization

```sql
-- Analyze query plans
EXPLAIN ANALYZE
SELECT * FROM video_chunks
WHERE embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;

-- Increase work_mem for faster aggregations
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';

-- Reload configuration
SELECT pg_reload_conf();
```

### Index Optimization

```sql
-- Check index bloat
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Reindex if bloated
REINDEX INDEX idx_video_chunks_embedding;

-- Monitor index size
SELECT indexname, pg_size_pretty(pg_relation_size(indexrelname))
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelname) DESC;
```

### Query Performance

```python
# Slow query log
import logging
import time
import functools

logger = logging.getLogger(__name__)

def log_slow_query(threshold_ms: float = 100):
    """Decorator to log slow queries."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            if elapsed > threshold_ms:
                logger.warning(
                    f"SLOW QUERY: {func.__name__} took {elapsed:.1f}ms"
                )
            return result
        return wrapper
    return decorator

# Usage:
@log_slow_query(threshold_ms=200)
def search_semantic(query: str):
    # ... search logic
    pass
```

---

## Scaling Guidelines

### When to scale:

| Metric | Threshold | Action |
|--------|-----------|--------|
| Query latency p95 | >300ms | Add database indexes or replicas |
| CPU usage | >80% | Upgrade instance or shard |
| Database size | >10GB | Archive old data or shard by domain |
| Chunk count | >1M | Switch to approximate NN (HNSW) |
| Daily queries | >10K | Add read replicas |

### Vertical Scaling (Single Machine)

```bash
# Upgrade hardware
# - More cores: better parallel query execution
# - More RAM: larger IVFFlat index in memory
# - Better storage: NVMe for faster I/O

# Monitor resource usage
watch -n 5 'free -h; df -h; top -bn1 | head -20'
```

### Horizontal Scaling (Sharding)

```sql
-- Shard by video category
CREATE TABLE video_chunks_approche PARTITION OF video_chunks
  FOR VALUES IN ('approche');

CREATE TABLE video_chunks_qualification PARTITION OF video_chunks
  FOR VALUES IN ('qualification');

-- Use pg_partman for automated partitioning
```

### Vector Index Optimization

```sql
-- Switch from IVFFlat to HNSW for >1M chunks
-- HNSW is faster but uses more memory

DROP INDEX idx_video_chunks_embedding;

CREATE INDEX idx_video_chunks_embedding_hnsw ON video_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);

-- Tune parameters:
-- m: more = better quality but slower
-- ef_construction: more = slower indexing but better quality
```

---

## Troubleshooting Guide

### Issue: High Query Latency

**Symptoms**: Search requests take >1s

**Diagnosis**:
```sql
-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM video_chunks
WHERE embedding <=> query_embedding::vector
LIMIT 5;

-- Check index usage
SELECT * FROM pg_stat_user_indexes
WHERE schemaname = 'public';

-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Solutions**:
1. Increase `ivfflat.probes` parameter for better accuracy
2. Increase cache size: `SET work_mem TO '512MB'`
3. Add more CPU cores
4. Switch to HNSW index for large datasets

### Issue: Low Search Quality

**Symptoms**: Irrelevant results returned

**Diagnosis**:
```sql
-- Check if embeddings exist
SELECT COUNT(*) FROM video_chunks WHERE embedding IS NULL;

-- Check top-matching results
SELECT id, 1 - (embedding <=> query_emb)::vector AS score
FROM video_chunks
ORDER BY embedding <=> query_emb::vector
LIMIT 20;
```

**Solutions**:
1. Re-embed with better model (multilingual-e5-large)
2. Increase chunk size (better semantic coherence)
3. Add reranking with cross-encoder
4. Fine-tune weights per agent

### Issue: Database Out of Disk Space

**Symptoms**: `ERROR: could not extend relation`

**Diagnosis**:
```bash
# Check disk usage
du -sh /var/lib/postgresql
df -h

# Check table sizes
psql -d rag_videos -c "
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

**Solutions**:
1. Delete old rag_events: `DELETE FROM rag_events WHERE created_at < NOW() - INTERVAL '90 days'`
2. Vacuum: `VACUUM ANALYZE`
3. Extend storage volume
4. Archive to separate database

### Issue: MCP Server Crashes

**Symptoms**: Search tool unavailable

**Diagnosis**:
```bash
# Check logs
tail -100 /var/log/rag-mcp.log

# Check process
ps aux | grep mcp_server

# Check database connectivity
psql -d rag_videos -c "SELECT COUNT(*) FROM videos;"
```

**Solutions**:
1. Restart service: `systemctl restart mcp-rag`
2. Check database connection: `psql -d rag_videos -c "SELECT 1"`
3. Review error logs for exceptions
4. Increase Python memory: `export PYTHONMALLOC=malloc`

---

## Runbook Templates

### Daily Check

```bash
#!/bin/bash
# Daily health check

echo "=== Daily RAG Health Check ==="
echo ""

# 1. Database connectivity
psql -d rag_videos -c "SELECT COUNT(*) FROM videos;" > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ Database connectivity OK"
else
    echo "✗ Database connectivity FAILED"
    exit 1
fi

# 2. MCP server
curl -s http://localhost:5000/health > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ MCP server OK"
else
    echo "✗ MCP server NOT RESPONDING"
fi

# 3. Search functionality
RESULT=$(curl -s -X POST http://localhost:5000/search_content \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}')

if echo "$RESULT" | grep -q "Found"; then
    echo "✓ Search functionality OK"
else
    echo "✗ Search returning errors"
fi

# 4. Backup status
LATEST_BACKUP=$(ls -t /backups/rag_database/rag_*.dump 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    AGE_HOURS=$(( ($(date +%s) - $(stat -f%m "$LATEST_BACKUP")) / 3600 ))
    if [ $AGE_HOURS -lt 26 ]; then
        echo "✓ Latest backup: $AGE_HOURS hours old"
    else
        echo "! Backup is $AGE_HOURS hours old (>24h)"
    fi
fi

echo ""
echo "Health check complete"
```

### Incident Response

```markdown
# MCP/RAG Service Degradation

## Assessment Phase (5 min)
1. Check if database is responsive
2. Check if MCP server is running
3. Check system resources (CPU, memory, disk)
4. Check recent error logs

## Mitigation Phase (15 min)
1. If database issue:
   - Kill long-running queries
   - Check locks with `SELECT * FROM pg_locks`
   - Restart PostgreSQL if needed

2. If MCP issue:
   - Restart service: `systemctl restart mcp-rag`
   - Check for Python errors in logs
   - Verify database connection

3. If resource issue:
   - Free disk space if needed
   - Add swap if memory low
   - Scale infrastructure if CPU maxed

## Recovery Phase (30 min)
1. Monitor metrics until normal
2. Collect diagnostics
3. Document root cause
4. Schedule post-mortem

## Post-Mortem (within 48h)
1. Analyze why issue occurred
2. Implement preventive measures
3. Update playbooks
4. Share learnings
```

---

## Capacity Planning

### Current Capacity (Per Instance)

```
Database Size:       10 GB
Chunks Indexed:      500K
Daily Queries:       5K
Query Latency p95:   <200ms
Uptime:              99.9%
```

### Growth Projection

```
Month 1:  500K chunks,   5K queries/day
Month 3:  1.5M chunks,  15K queries/day
Month 6:  5M chunks,    50K queries/day
Month 12: 10M chunks,  100K queries/day

Action Items:
- Month 3: Add read replica for queries
- Month 6: Shard by domain or switch to distributed DB
- Month 12: Consider specialized vector DB (Pinecone, Weaviate)
```

---

## Cost Tracking

### Self-Hosted (Monthly)

```
PostgreSQL + pgvector:    €0 (installed)
Disk storage (100 GB):    €5
Network egress:           €10
Monitoring + backup:      €0
Total:                    ~€15/month
```

### Managed (Monthly)

```
Supabase pgvector:        €25-100 (on pay-as-you-go)
Vector DB (Pinecone):     €0-500 (on usage)
Total:                    €25-600/month
```

---

**Document Version**: 1.0
**Created**: 2026-03-14
**Last Updated**: 2026-03-14
**Audience**: Operations team, DevOps, SRE
