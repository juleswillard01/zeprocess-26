# Deployment & Implementation Guide

**Document**: Production Deployment & Launch Plan
**Status**: Ready for Implementation
**Updated**: 14 mars 2026

---

## QUICK START (5 MINUTES)

### Prerequisites Checklist

```bash
# 1. Clone repository
git clone <repo-url> && cd zeprocess

# 2. Install Python 3.12+
python --version  # Should be 3.12+

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env.production
# Edit .env.production with your API keys

# 5. Start services
docker-compose -f docker-compose.prod.yml up -d

# 6. Run migrations
python -m alembic upgrade head

# 7. Verify system
python scripts/test_connection.py

# 8. Start workers
celery -A workers.lead_acquisition worker -l info
```

**Total time**: ~30 minutes

---

## ARCHITECTURE DEPLOYMENT

### Option 1: Docker Compose (Development/Small Scale)

Recommended for: MVP, single-server deployment, < 100 leads/day

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # PostgreSQL + pgvector
  postgres:
    image: pgvector/pgvector:pg16-latest
    environment:
      POSTGRES_USER: megaquixai
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: lead_acquisition
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U megaquixai"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend

  # Redis (caching, rate limits, dedup)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --appendfsync everysec
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    networks:
      - backend

  # Celery Worker (async tasks)
  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://megaquixai:${DB_PASSWORD}@postgres:5432/lead_acquisition
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      YOUTUBE_API_KEY: ${YOUTUBE_API_KEY}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
    command: celery -A workers.lead_acquisition worker -l info
    networks:
      - backend
    restart: unless-stopped

  # LangGraph Runtime (orchestration)
  langgraph_runtime:
    image: langgraph-runtime:latest
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://megaquixai:${DB_PASSWORD}@postgres:5432/lead_acquisition
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    networks:
      - backend
    restart: unless-stopped

  # Prometheus (metrics)
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - backend

volumes:
  postgres_data:
  redis_data:
  prometheus_data:

networks:
  backend:
    driver: bridge
```

### Option 2: Kubernetes (Production Scale)

Recommended for: > 500 leads/day, multi-region, high availability

#### Deployment Files

**1. Namespace & ConfigMap**
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: lead-acquisition

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lead-acq-config
  namespace: lead-acquisition
data:
  ICP_DEFINITION_FILE: /config/icp.yaml
  LOG_LEVEL: INFO
```

**2. Secrets**
```bash
kubectl create secret generic lead-acq-secrets \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=YOUTUBE_API_KEY=... \
  --from-literal=DB_PASSWORD=... \
  -n lead-acquisition
```

**3. Celery Worker Deployment**
```yaml
# k8s/celery-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lead-acq-celery
  namespace: lead-acquisition
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: lead-acq-celery
  template:
    metadata:
      labels:
        app: lead-acq-celery
    spec:
      containers:
      - name: celery-worker
        image: megaquixai/lead-acquisition:latest
        imagePullPolicy: Always
        command:
          - celery
          - -A
          - workers.lead_acquisition
          - worker
          - -l
          - info
          - --concurrency=4
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: lead-acq-secrets
              key: DB_URL
        - name: CELERY_BROKER_URL
          value: redis://redis-service:6379/0
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: lead-acq-secrets
              key: ANTHROPIC_API_KEY
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          exec:
            command:
              - python
              - -c
              - "import os; exit(0)"
          initialDelaySeconds: 30
          periodSeconds: 60
        lifecycle:
          preStop:
            exec:
              command: ["sh", "-c", "sleep 15"]
```

**4. LangGraph Runtime Service**
```yaml
# k8s/langgraph-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: langgraph-service
  namespace: lead-acquisition
spec:
  selector:
    app: langgraph
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langgraph
  namespace: lead-acquisition
spec:
  replicas: 2
  selector:
    matchLabels:
      app: langgraph
  template:
    metadata:
      labels:
        app: langgraph
    spec:
      containers:
      - name: langgraph
        image: megaquixai/langgraph-runtime:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: lead-acq-secrets
              key: DB_URL
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

**5. Horizontal Pod Autoscaler**
```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: lead-acq-celery-hpa
  namespace: lead-acquisition
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: lead-acq-celery
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## DATABASE SETUP

### 1. PostgreSQL Initialization

```bash
# Connect to PostgreSQL
psql -U megaquixai -d lead_acquisition -h localhost

# Run schema migrations
\i schema/01-initial-schema.sql
\i schema/02-vectors.sql
\i schema/03-indexes.sql

# Verify tables
\dt

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 2. Schema Files

**schema/01-initial-schema.sql**
```sql
-- Create tables (as specified in architecture document)
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,
    username VARCHAR(255) NOT NULL,
    profile_url TEXT NOT NULL UNIQUE,
    bio TEXT,
    followers_count INT,
    icp_score FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'detected',
    region VARCHAR(50) DEFAULT 'EU',
    user_consent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE lead_actions (
    id BIGSERIAL PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    action_status VARCHAR(50),
    variant VARCHAR(50),
    action_details JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE consent_audit (
    id BIGSERIAL PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES leads(id),
    action_type VARCHAR(50),
    reason TEXT,
    region VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_icp_score ON leads(icp_score DESC);
CREATE INDEX idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX idx_actions_lead_id ON lead_actions(lead_id);
```

### 3. Alembic Migrations (Version Control)

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add leads table"

# Apply migrations
alembic upgrade head

# Check migration history
alembic history
```

---

## API KEYS & CREDENTIALS

### Setup Checklist

```bash
# 1. ANTHROPIC (Claude API)
export ANTHROPIC_API_KEY="sk-ant-..."
# Get from: https://console.anthropic.com/

# 2. YOUTUBE API
export YOUTUBE_API_KEY="..."
# Setup: https://console.cloud.google.com/
# - Create project
# - Enable YouTube Data API v3
# - Create service account
# - Download JSON key

# 3. REDDIT (PRAW)
export REDDIT_CLIENT_ID="..."
export REDDIT_CLIENT_SECRET="..."
# Get from: https://www.reddit.com/prefs/apps (create script app)

# 4. LANGFUSE (Observability)
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
# Setup: https://cloud.langfuse.com/

# 5. Instagram Proxies
export INSTAGRAM_PROXY_LIST="http://proxy1:port,http://proxy2:port,..."
# Use service like Bright Data, Oxylabs, or residential proxy provider

# 6. Database
export DATABASE_URL="postgresql://user:pass@localhost:5432/lead_acquisition"

# 7. Redis
export REDIS_URL="redis://localhost:6379/0"

# 8. Save to .env
cat > .env.production << 'ENVEOF'
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
REDDIT_CLIENT_ID=${REDDIT_CLIENT_ID}
REDDIT_CLIENT_SECRET=${REDDIT_CLIENT_SECRET}
LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
INSTAGRAM_PROXY_LIST=${INSTAGRAM_PROXY_LIST}
DATABASE_URL=${DATABASE_URL}
REDIS_URL=${REDIS_URL}
ENVEOF

# 9. Verify connectivity
python scripts/test_connections.py
```

---

## TESTING BEFORE PRODUCTION

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_icp_scorer.py::test_score_role_match -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Integration Tests

```bash
# Test with real PostgreSQL (Docker)
pytest tests/integration/ -v -s

# Test with YouTube API (live, uses quota!)
# Set --live-api flag to actually call API
pytest tests/integration/test_youtube_scraper.py -v -s

# Test Celery tasks
pytest tests/integration/test_celery_tasks.py -v -s
```

### End-to-End Test

```bash
# Test full pipeline: source → score → queue
python scripts/test_e2e.py \
  --source youtube \
  --channel-id "UC_x5XG1OV2P6uZZ5FSM9Ttw" \
  --limit 10 \
  --verbose
```

---

## MONITORING & OBSERVABILITY

### 1. Prometheus Setup

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'lead-acquisition'
    static_configs:
      - targets: ['localhost:8000']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']  # postgres_exporter
```

### 2. Grafana Dashboards

Create dashboard with:
- **Volume metrics**: Leads detected, qualified, contacted
- **Quality metrics**: ICP score distribution, DM conversion rate
- **Performance**: API latency, queue depth, worker utilization
- **Cost**: API calls per day, cost breakdown by service

### 3. Alerting

```yaml
# alerts.yaml
groups:
  - name: lead_acquisition
    rules:
      - alert: HighErrorRate
        expr: rate(celery_task_failed_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High error rate in celery tasks"

      - alert: HighQueueDepth
        expr: celery_queue_length > 1000
        for: 10m
        annotations:
          summary: "Celery queue backing up"

      - alert: DatabaseConnectionError
        expr: up{job="postgres"} == 0
        for: 1m
        annotations:
          summary: "Database connection lost"

      - alert: DailyBudgetExceeded
        expr: increase(api_cost_total_usd[1d]) > 10
        annotations:
          summary: "Daily API budget exceeded"
```

---

## PRODUCTION DEPLOYMENT STEPS

### Phase 1: Pre-Launch (Week 1)

**Day 1-2: Setup Infrastructure**
```bash
# 1. Provision server (AWS EC2, DigitalOcean, etc.)
# Instance type: t3.medium or larger (2 vCPU, 4GB RAM minimum)

# 2. Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
# Review script, then: sh get-docker.sh

# 3. Clone repository
git clone <repo> && cd zeprocess

# 4. Create .env.production with all secrets
# (See API Keys section above)

# 5. Start services
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify health
curl http://localhost:8000/health
redis-cli ping
psql -U megaquixai -c "SELECT 1"
```

**Day 3-4: Test Configuration**
```bash
# 1. Test YouTube API
python scripts/test_youtube_api.py

# 2. Test Reddit API
python scripts/test_reddit_api.py

# 3. Test Claude scoring
python scripts/test_icp_scoring.py

# 4. Test database
python scripts/test_db_connection.py

# 5. Run integration tests
pytest tests/integration/ -v
```

**Day 5-7: Load Testing**
```bash
# 1. Generate test data (100 leads)
python scripts/generate_test_leads.py --count 100

# 2. Run load test (10 concurrent scorers)
python scripts/load_test.py --workers 10 --duration 300

# 3. Monitor metrics
# - Check Prometheus: http://localhost:9090
# - Check Celery queue depth
# - Check database load

# 4. Optimize if needed
# - Adjust worker count
# - Tune database connection pool
# - Adjust batch sizes
```

### Phase 2: Launch (Week 2)

**Day 1: Soft Launch (10 leads/day)**
```bash
# 1. Configure rate limits (conservative)
# In config:
#   MAX_DAILY_LEADS: 10
#   ICP_SCORE_THRESHOLD: 0.70 (high bar)

# 2. Enable detailed logging
# LOG_LEVEL: DEBUG

# 3. Monitor closely
# - Check every 2 hours for errors
# - Verify lead quality manually
# - Review contact messages

# 4. Document any issues
```

**Day 2-3: Ramp Up (50 leads/day)**
```bash
# 1. Increase limits if Day 1 went well
# MAX_DAILY_LEADS: 50

# 2. Reduce score threshold
# ICP_SCORE_THRESHOLD: 0.60

# 3. Start A/B testing (all 3 variants)

# 4. Continue manual quality checks (5-10% sample)
```

**Day 4-7: Full Scale (200 leads/day)**
```bash
# 1. Remove daily limit (or set to 200)
# 2. Reduce logging to INFO (save logs)
# 3. Enable automated alerting
# 4. Weekly report:
#    - Volume: 1,000+ leads processed
#    - Quality: ICP accuracy (manual validation)
#    - Cost: actual spend vs budget
#    - Conversion: initial engagement metrics
```

### Phase 3: Optimization (Week 3+)

```
Ongoing monitoring and tuning:

├─ Daily: Check error rates, queue depth, costs
├─ Weekly: Analyze A/B test results, update thresholds
├─ Monthly: Review ICP definition, retrain if needed
└─ Quarterly: Full audit (compliance, performance, ROI)
```

---

## TROUBLESHOOTING

### Common Issues & Solutions

#### Issue 1: High Memory Usage by Celery Workers

```bash
# Symptom: Docker OOM kill after 2-3 hours

# Cause: Task accumulation in memory
# Solution:
# 1. Reduce prefetch multiplier
# In celery_config.py:
#   worker_prefetch_multiplier = 1  # (was 4)

# 2. Set task timeout
#   task_soft_time_limit = 280
#   task_time_limit = 300

# 3. Restart worker
docker-compose restart celery_worker
```

#### Issue 2: Instagram Scraper Getting Blocked

```bash
# Symptom: 403 Forbidden or "too many requests"

# Cause: Rate limiting or detection
# Solution:
# 1. Add delays between requests
#   MIN_DELAY = 5  # seconds
#   MAX_DELAY = 15

# 2. Rotate proxies more frequently
#   Change proxy after every 3 requests instead of 10

# 3. Add human-like behavior (mouse movements, scrolling)

# 4. Check proxy IP reputation
# Use diagnostic tool to test proxy

# 5. Pause Instagram scraping for 24-48 hours
```

#### Issue 3: Claude API Rate Limiting

```bash
# Symptom: 429 Rate Limit errors

# Cause: Too many requests or quota exceeded
# Solution:
# 1. Check quota in Anthropic console
# 2. Batch requests (score multiple profiles in one call)
# 3. Add exponential backoff
# 4. Request higher quota if needed (Anthropic support)

# Temporary fix:
# - Reduce ICP_BATCH_SIZE from 10 to 5
# - Add 1-2 second delay between API calls
```

#### Issue 4: Database Deadlocks

```bash
# Symptom: "ERROR: deadlock detected"

# Cause: Concurrent writes to same row
# Solution:
# 1. Check for hot rows in query logs
# 2. Use optimistic locking (version field)
# 3. Reduce concurrent writers if possible
# 4. Increase statement timeout (with care)
```

---

## ROLLBACK PROCEDURE

If something goes wrong in production:

```bash
# 1. Stop new lead processing
docker-compose exec langgraph-runtime \
  curl -X POST http://localhost:8000/api/stop

# 2. Pause Celery workers
docker-compose stop celery_worker

# 3. Check logs
docker-compose logs celery_worker --tail=100

# 4. Fix issue (update code/config)
git pull origin main
# OR
nano .env.production  # if config issue

# 5. Run migrations if code change
docker-compose exec postgres alembic upgrade head

# 6. Restart workers
docker-compose up -d celery_worker

# 7. Verify health
curl http://localhost:8000/health

# 8. Resume processing
docker-compose exec langgraph-runtime \
  curl -X POST http://localhost:8000/api/start

# 9. Monitor closely for next 1 hour
docker-compose logs -f celery_worker | head -50
```

---

## PERFORMANCE TUNING

### Database Optimization

```sql
-- Check slow queries in PostgreSQL
SELECT query, calls, mean_time FROM pg_stat_statements
WHERE mean_time > 100
ORDER BY mean_time DESC;

-- Add indexes if needed
CREATE INDEX idx_leads_source_type ON leads(source_type);

-- Vacuum & Analyze
VACUUM ANALYZE leads;
```

### Redis Optimization

```bash
# Check memory usage
redis-cli INFO memory

# Set max memory policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Set eviction limit
redis-cli CONFIG SET maxmemory 2gb
```

### Celery Optimization

```python
# In celery_config.py
app.conf.update(
    worker_prefetch_multiplier=2,  # Don't prefetch too many
    worker_max_tasks_per_child=100,  # Restart workers periodically
    task_always_eager=False,  # Ensure async
    task_eager_propagates=True,
)
```

---

## BACKUP & DISASTER RECOVERY

### Database Backup

```bash
# Daily backup schedule
# Backup PostgreSQL to file system
pg_dump -U megaquixai lead_acquisition > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -U megaquixai lead_acquisition < backup_20260314.sql
```

### Redis Backup

```bash
# Redis persistence is enabled (appendonly yes)
# Default location: /var/lib/redis/appendonly.aof

# Manual backup
redis-cli SAVE
cp /var/lib/redis/dump.rdb /backups/redis_$(date +%Y%m%d).rdb
```

### Recovery Plan

```
RTO (Recovery Time Objective): < 2 hours
RPO (Recovery Point Objective): < 15 minutes

In case of major failure:
1. Provision new server
2. Install Docker
3. Deploy latest code
4. Restore PostgreSQL backup
5. Restore Redis backup
6. Verify data integrity
7. Resume operations
```

---

## COST ESTIMATION

### Monthly Costs Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| **Server (EC2 t3.medium)** | $30-50 | 2vCPU, 4GB RAM, 100GB SSD |
| **PostgreSQL (RDS)** | $20-40 | If using managed service |
| **Redis (ElastiCache)** | $15-25 | If using managed service |
| **Claude API** | $100-500 | Depends on lead volume & scoring |
| **YouTube API** | $0 | Free tier (10M units/day sufficient) |
| **Bandwidth** | $5-15 | Data transfer out |
| **Monitoring/Logs** | $10-20 | Prometheus, Grafana, Sentry |
| **Proxy service** | $20-50 | For Instagram scraping |
| **Backups** | $5-10 | Storage |
| **Misc** | $10-20 | Domains, monitoring, etc. |
| **TOTAL** | **$215-730/month** | Typical small-scale production |

### Cost Optimization Tips

1. Use free tier services (Prometheus, Grafana, Loki)
2. Batch API calls (reduce Claude invocations by 30-50%)
3. Cache aggressively (Redis TTL tuning)
4. Rate limit proactively (prevent wasted API calls)
5. Monitor and prune old leads (archival strategy)

---

## SUCCESS METRICS

After 1 week in production, you should see:

```
✅ Volume:
   - 50-200 leads detected/day
   - 20-80 leads qualified/day
   - < 5% error rate

✅ Quality:
   - ICP score distribution roughly normal (mean ~0.55)
   - Manual QA sample: 60%+ accuracy
   - No compliance violations

✅ Performance:
   - API response times: < 500ms (90th percentile)
   - Celery task duration: < 30s (median)
   - Database query times: < 100ms (95th percentile)

✅ Cost:
   - Actual cost < budget (< $10/day)
   - Cost per qualified lead < $1

✅ Integration:
   - Data flowing to Agent #2 (Séduction)
   - No data quality issues reported

If any metric misses, drill down in:
   - Logs (docker-compose logs -f)
   - Metrics (Prometheus dashboard)
   - Database (slow query log)
   - Celery (flower dashboard)
```

---

**End of Deployment & Implementation Guide**
