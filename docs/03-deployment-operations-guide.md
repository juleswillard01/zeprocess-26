# MEGA QUIXAI: Deployment & Operations Guide

**Version**: 1.0
**Date**: 2026-03-14
**Stack**: Docker + PostgreSQL + LangGraph + Claude SDK

---

## Part 1: Pre-Deployment Checklist

### 1.1 Prerequisites

```bash
# System requirements
- Python 3.12+
- PostgreSQL 14+ with pgvector extension
- Docker & Docker Compose (for containerized deployment)
- 2+ GB RAM available
- Stable internet connection (for API calls)

# API Credentials needed
- ANTHROPIC_API_KEY (Claude access)
- LANGFUSE_PUBLIC_KEY & LANGFUSE_SECRET_KEY (observability)
- INSTAGRAM_API_TOKEN (lead sourcing)
- YOUTUBE_API_KEY (lead sourcing)

# Budget verification
- Monthly API budget: $3,000-10,000 USD
- Expected monthly cost at 10k leads: ~$1,000-2,000
```

### 1.2 Infrastructure Decisions

| Component | Option A (Local) | Option B (Cloud) | Option C (Hybrid) |
|-----------|------------------|------------------|-------------------|
| **PostgreSQL** | Docker local | RDS + pgvector | Docker + S3 backup |
| **Graph Execution** | Laptop/Server | AWS Lambda | Always-on VPS |
| **Checkpointing** | Local disk | PostgreSQL RDS | Dual-region sync |
| **Observability** | LangFuse free tier | LangFuse Pro | LangFuse + DataDog |
| **Cost** | $0-50/month | $500-1000/month | $100-300/month |

**Recommendation**: Start with Option A (local), scale to Option C when you have consistent lead volume.

---

## Part 2: Local Development Setup

### 2.1 Clone & Environment

```bash
# Clone repository
git clone https://github.com/your-org/mega-quixai.git
cd mega-quixai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip

# Install uv for fast dependency management (optional)
pip install uv
```

### 2.2 Install Dependencies

```bash
# Option 1: Using pip (standard)
pip install -e ".[dev]"

# Option 2: Using uv (faster)
uv pip install -e ".[dev]"

# Verify installation
python -c "import langgraph; print(langgraph.__version__)"
```

### 2.3 Environment Configuration

Create `.env` file in project root:

```bash
# Core API Keys
ANTHROPIC_API_KEY=sk_...
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/langgraph
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=langgraph

# Social APIs
INSTAGRAM_API_TOKEN=...
YOUTUBE_API_KEY=...

# Observability
LOG_LEVEL=INFO
DEBUG=false

# Budget control
MONTHLY_BUDGET_USD=10000
ALERT_BUDGET_THRESHOLD=0.8  # Alert at 80%

# RAG configuration
RAG_ENABLED=true
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_TOP_K=3

# Deployment
ENVIRONMENT=development  # development, staging, production
WORKERS=5
BATCH_SIZE=10
```

### 2.4 Initialize PostgreSQL (Local)

```bash
# Start PostgreSQL container
docker run --name langgraph_postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=langgraph \
  -p 5432:5432 \
  pgvector/pgvector:pg16 &

# Wait for startup
sleep 10

# Initialize schema
python scripts/init_db.py

# Verify connection
psql postgresql://postgres:postgres@localhost:5432/langgraph -c "SELECT version();"
```

### 2.5 Load DDP Content to RAG

```bash
# Assumes you have DDP Garçonnière video transcriptions in JSON format
# File structure: { "video_id": "...", "title": "...", "content": "...", "source": "ddp" }

python scripts/load_rag.py \
  --source-file data/ddp_transcripts.json \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --batch-size 100

# Verify ingestion
python -c "from src.integrations.postgresql import get_embedding_count; print(f'Embeddings loaded: {get_embedding_count()}')"
```

### 2.6 Test Single Lead Processing

```bash
# Run CLI in single-lead mode
python -m src.main single \
  --lead-id 123e4567-e89b-12d3-a456-426614174000 \
  --source instagram \
  --username test_user_001

# Expected output:
# ============================================================
# Lead: test_user_001
# Status: engaged
# ICP Score: 0.75
# Engagement: 0.60
# Conversion Prob: 0.45
# ============================================================
```

### 2.7 Run Unit Tests

```bash
# Run all tests
pytest tests/ -v --cov=src --cov-fail-under=80

# Run specific test file
pytest tests/unit/test_agents.py -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

---

## Part 3: Docker Containerized Deployment

### 3.1 Docker Setup (docker-compose.yml)

```yaml
version: '3.9'

services:
  # PostgreSQL with pgvector
  postgres:
    image: pgvector/pgvector:pg16
    container_name: langgraph_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-langgraph}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.py:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - langgraph_network

  # LangGraph execution service
  graph_executor:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: langgraph_executor
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - ENVIRONMENT=production
      - WORKERS=${WORKERS:-5}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs
    networks:
      - langgraph_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Optional: Redis for caching/queue
  redis:
    image: redis:7-alpine
    container_name: langgraph_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - langgraph_network
    restart: unless-stopped

  # Optional: Monitoring dashboard (Streamlit)
  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    container_name: langgraph_dashboard
    depends_on:
      - postgres
    ports:
      - "8501:8501"
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    volumes:
      - ./scripts/monitor.py:/app/monitor.py
    networks:
      - langgraph_network
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  langgraph_network:
    driver: bridge
```

### 3.2 Dockerfile (Production)

```dockerfile
# Build stage
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY pyproject.toml uv.lock* ./

# Install with uv or pip
RUN pip install --no-cache-dir uv && \
    uv pip install --system -r pyproject.toml

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy application
COPY src/ src/
COPY scripts/ scripts/
COPY pyproject.toml ./

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default: batch mode with 5 workers
CMD ["python", "-m", "src.main", "batch", "--workers", "5"]

# Expose metrics port
EXPOSE 8000
```

### 3.3 Dockerfile for Dashboard

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install streamlit sqlalchemy psycopg2-binary plotly pandas

COPY scripts/monitor.py .

EXPOSE 8501

CMD ["streamlit", "run", "monitor.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 3.4 Start Services (Docker Compose)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f graph_executor

# Stop services
docker-compose down

# Clean up (remove volumes)
docker-compose down -v
```

---

## Part 4: Production Deployment (AWS / Cloud)

### 4.1 AWS Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS VPC                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              ECS Cluster                             │   │
│  │  ┌──────────────────────────────────────┐            │   │
│  │  │ LangGraph Executor (x3 tasks)        │            │   │
│  │  │ - Python 3.12 container              │            │   │
│  │  │ - Auto-scale based on queue depth    │            │   │
│  │  └──────────────────────────────────────┘            │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                    │
│         ├──→ RDS PostgreSQL + pgvector                      │
│         │    - Multi-AZ for HA                             │
│         │    - Daily automated backups                     │
│         │                                                   │
│         ├──→ ElastiCache Redis                             │
│         │    - Session caching                            │
│         │    - Queue management                           │
│         │                                                   │
│         └──→ CloudWatch Logs + Metrics                     │
│              - All agent executions traced                │
│              - Budget monitoring alerts                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Terraform Configuration (AWS Infrastructure as Code)

```hcl
# main.tf - Core infrastructure

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "mega-quixai-terraform"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

# RDS PostgreSQL
resource "aws_db_instance" "langgraph" {
  identifier     = "langgraph-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t3.medium"

  allocated_storage = 100
  storage_encrypted = true

  db_name  = "langgraph"
  username = var.db_username
  password = random_password.db_password.result

  multi_az               = true
  publicly_accessible   = false
  backup_retention_days = 7

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.default.name

  tags = {
    Name = "langgraph-db"
  }
}

# Enable pgvector extension
resource "aws_rds_cluster_parameter_group" "langgraph" {
  family      = "postgres16"
  name        = "langgraph-params"
  description = "LangGraph parameter group"

  parameter {
    name  = "shared_preload_libraries"
    value = "vector"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "langgraph" {
  name = "langgraph-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "langgraph-cluster"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "langgraph" {
  family                   = "langgraph-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name  = "langgraph"
    image = "${var.ecr_registry}/mega-quixai:latest"

    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]

    environment = [
      {
        name  = "ENVIRONMENT"
        value = "production"
      },
      {
        name  = "WORKERS"
        value = "5"
      }
    ]

    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = aws_secretsmanager_secret.db_url.arn
      },
      {
        name      = "ANTHROPIC_API_KEY"
        valueFrom = aws_secretsmanager_secret.api_key.arn
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.langgraph.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = {
    Name = "langgraph-task"
  }
}

# ECS Service with Auto-scaling
resource "aws_ecs_service" "langgraph" {
  name            = "langgraph-service"
  cluster         = aws_ecs_cluster.langgraph.id
  task_definition = aws_ecs_task_definition.langgraph.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.langgraph.arn
    container_name   = "langgraph"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.langgraph]

  tags = {
    Name = "langgraph-service"
  }
}

# Auto-scaling policy
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.langgraph.name}/${aws_ecs_service.langgraph.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_policy_cpu" {
  policy_name       = "cpu-autoscaling"
  policy_type       = "TargetTrackingScaling"
  resource_id       = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

### 4.3 CloudWatch Monitoring & Alarms

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name mega-quixai-monitoring \
  --dashboard-body file://monitoring/dashboard.json

# Create budget alert (80% threshold)
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://monitoring/budget.json \
  --notifications-with-subscribers file://monitoring/notifications.json

# View logs
aws logs tail /ecs/langgraph-task --follow

# Get metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=langgraph-service \
  --start-time 2026-03-14T00:00:00Z \
  --end-time 2026-03-14T23:59:59Z \
  --period 3600 \
  --statistics Average
```

---

## Part 5: Monitoring & Observability

### 5.1 LangFuse Integration

```python
# src/integrations/langfuse_client.py

from langfuse import Langfuse

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host="https://cloud.langfuse.com"
)

async def trace_agent_execution(agent_name: str, lead_id: str, result: dict):
    """Trace agent execution for observability."""

    trace = langfuse.trace(
        name=f"agent_{agent_name}",
        user_id=lead_id,
        metadata={
            "agent": agent_name,
            "lead_id": lead_id,
            "timestamp": datetime.now().isoformat()
        }
    )

    trace.update(
        output=result.get("status"),
        metadata={
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
            "cost_usd": result.get("cost_usd", 0.0),
            "latency_ms": result.get("latency_ms", 0)
        }
    )

    return trace
```

### 5.2 Metrics Dashboard (Streamlit)

```python
# scripts/monitor.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.integrations.postgresql import get_db

st.set_page_config(page_title="MEGA QUIXAI Dashboard", layout="wide")

# Title
st.title("MEGA QUIXAI - Real-time Monitoring")

# KPIs
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_leads = get_total_leads()
    st.metric("Total Leads", f"{total_leads:,}")

with col2:
    won_deals = get_leads_by_status("won")
    conversion_rate = (won_deals / max(total_leads, 1)) * 100
    st.metric("Conversion Rate", f"{conversion_rate:.1f}%")

with col3:
    monthly_cost = get_monthly_cost()
    st.metric("API Cost (This Month)", f"${monthly_cost:,.0f}")

with col4:
    budget = float(os.getenv("MONTHLY_BUDGET_USD", 10000))
    budget_used_pct = (monthly_cost / budget) * 100
    st.metric("Budget Used", f"{budget_used_pct:.1f}%")

# Charts
st.subheader("Leads by Status")
status_data = get_leads_by_status_distribution()
st.bar_chart(status_data)

st.subheader("Agent Performance")
agent_metrics = get_agent_metrics()
st.dataframe(agent_metrics)

st.subheader("Cost Breakdown")
cost_breakdown = get_cost_breakdown()
st.pie_chart(cost_breakdown)

st.subheader("Recent Escalations")
escalations = get_recent_escalations(limit=10)
st.dataframe(escalations)
```

---

## Part 6: Scaling & Performance Optimization

### 6.1 Scaling Strategy

| Load Level | Leads/Day | Workers | RDS Size | Cost/Month |
|-----------|-----------|---------|----------|-----------|
| **MVP** | 100 | 2 | db.t3.small | $200 |
| **Early Traction** | 500 | 5 | db.t3.medium | $500 |
| **Growth** | 5,000 | 10 | db.t3.large | $1,500 |
| **Scale** | 20,000 | 20 | db.r6i.xlarge | $5,000 |
| **Enterprise** | 100,000 | 50 | db.r6i.4xlarge | $20,000 |

### 6.2 Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_leads_status_updated ON leads(status, updated_at DESC);
CREATE INDEX idx_leads_next_followup_status ON leads(next_follow_up, status);
CREATE INDEX idx_leads_conversion_probability ON leads(conversion_probability DESC);

-- Partitioning for large tables (>10M rows)
CREATE TABLE leads_2026_03 PARTITION OF leads
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM leads WHERE status = 'qualified' AND conversion_probability > 0.6;
```

### 6.3 Caching Strategy

```python
# src/utils/cache.py

import redis
from functools import wraps
from datetime import timedelta

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

def cache_result(ttl_seconds: int = 3600):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            redis_client.setex(
                cache_key,
                timedelta(seconds=ttl_seconds),
                json.dumps(result)
            )

            return result

        return wrapper
    return decorator

# Usage
@cache_result(ttl_seconds=3600)
async def get_rag_context(query: str):
    return await rag_retriever.aretrieve(query)
```

---

## Part 7: Backup & Disaster Recovery

### 7.1 Automated Backups

```bash
# PostgreSQL backup (daily at 2 AM UTC)
0 2 * * * pg_dump postgresql://user:pass@localhost:5432/langgraph | \
  gzip > /backups/langgraph_$(date +\%Y\%m\%d).sql.gz

# AWS S3 backup (daily)
0 3 * * * aws s3 sync /backups/ s3://mega-quixai-backups/postgres/

# Verify backup integrity (weekly)
0 4 * * 0 pg_restore -t leads /backups/langgraph_latest.sql.gz

# Retention policy (keep 30 days)
0 5 1 * * find /backups -name "*.gz" -mtime +30 -delete
```

### 7.2 Disaster Recovery Runbook

```markdown
## If Graph Executor Crashes

1. Check logs: `docker-compose logs graph_executor`
2. Identify last successful checkpoint
3. Resume from checkpoint: `python scripts/recover_checkpoint.py --thread-id <id>`
4. Verify state consistency: `python scripts/verify_state.py`

## If Database Becomes Corrupted

1. Stop all services: `docker-compose down`
2. Restore from backup: `pg_restore /backups/langgraph_latest.sql.gz`
3. Verify tables: `psql -c "\dt"`
4. Restart services: `docker-compose up -d`

## If API Budget Exceeded

1. Stop workers: `python scripts/pause_execution.py`
2. Review cost breakdown: `python scripts/analyze_costs.py --last-7-days`
3. Adjust routing to cheaper models (Haiku for more tasks)
4. Resume with new budget cap: `python scripts/resume_execution.py --budget-limit 1000`
```

---

## Part 8: Maintenance & Troubleshooting

### 8.1 Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| **PostgreSQL connection timeout** | "connection refused" | Check `DATABASE_URL`, restart postgres container, verify network |
| **Out of memory** | "OOMKilled" ECS task | Increase task memory (Fargate), reduce batch size, check for memory leaks |
| **API rate limiting** | Claude API returns 429 | Implement exponential backoff, increase delay between calls |
| **RAG embeddings missing** | "No results" from search | Reload embeddings: `python scripts/load_rag.py` |
| **Stale checkpoints** | Graph resumes old state | Clean old checkpoints: `python scripts/cleanup_checkpoints.py --older-than 7` |

### 8.2 Log Analysis

```bash
# Find errors in logs
docker-compose logs graph_executor | grep ERROR

# Count errors by type
docker-compose logs graph_executor | grep -o "Error: \w*" | sort | uniq -c

# Monitor in real-time
docker-compose logs -f --tail=50 graph_executor

# Export logs for analysis
docker-compose logs graph_executor > logs_$(date +%Y%m%d_%H%M%S).txt
```

### 8.3 Performance Profiling

```python
# Profile agent execution time
import cProfile
import pstats
from io import StringIO

def profile_agent():
    pr = cProfile.Profile()
    pr.enable()

    # Run agent
    result = asyncio.run(agent_node(state))

    pr.disable()
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(10)  # Top 10 functions
    print(s.getvalue())

# Profile database queries
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, params, context, executemany):
    total_time = time.time() - conn.info['query_start_time'].pop(-1)
    if total_time > 1.0:  # Log slow queries (>1s)
        logger.warning(f"SLOW QUERY ({total_time:.2f}s): {statement[:100]}...")
```

---

## Part 9: CI/CD Pipeline

### 9.1 GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml

name: Deploy MEGA QUIXAI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check src tests

      - name: Type check with mypy
        run: mypy src --strict

      - name: Run tests
        run: pytest tests/ -v --cov=src --cov-fail-under=80
        env:
          DATABASE_URL: postgresql://postgres:postgres@postgres:5432/postgres

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to ECR
        run: |
          aws ecr get-login-password --region eu-west-1 | \
            docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.ECR_REGISTRY }}/mega-quixai:latest
            ${{ secrets.ECR_REGISTRY }}/mega-quixai:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster langgraph-cluster \
            --service langgraph-service \
            --force-new-deployment
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: eu-west-1
```

---

## Part 10: Operations Runbook

### 10.1 Daily Operations Checklist

```markdown
## Daily (Every Morning)

- [ ] Check budget: `python scripts/check_budget.py`
- [ ] Verify all leads processed: `SELECT COUNT(*) FROM leads WHERE updated_at > NOW() - INTERVAL '24 hours'`
- [ ] Check error rate: `SELECT COUNT(*) FROM agent_logs WHERE status='error' AND timestamp > NOW() - INTERVAL '24 hours'`
- [ ] Review escalations: `SELECT * FROM escalations WHERE created_at > NOW() - INTERVAL '24 hours'`

## Weekly

- [ ] Database maintenance: `VACUUM ANALYZE;`
- [ ] Review KPIs: conversion rate, cost per lead, cycle time
- [ ] Optimize slow queries: `SELECT query, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10`
- [ ] Update runbooks based on incidents

## Monthly

- [ ] Database backup verification
- [ ] Cost analysis & forecast
- [ ] Capacity planning (do we need to scale?)
- [ ] Security audit (API keys rotation, access logs)
- [ ] Agent performance review & tuning
```

### 10.2 Incident Response

```markdown
## P1 (Critical): Graph Executor Down

**Detection**: CloudWatch alert + Slack notification

**Response Time**: < 5 minutes

1. Check service status: `docker-compose ps`
2. View error logs: `docker-compose logs --tail=100 graph_executor`
3. If OOM: increase memory limit in docker-compose.yml
4. If API error: check API key in .env
5. Restart service: `docker-compose restart graph_executor`
6. Verify recovery: `curl http://localhost:8000/health`

## P2 (High): Poor Agent Performance

**Symptom**: High error rate, slow processing

**Investigation**:
1. Check which agent is slow: `SELECT agent_name, AVG(latency_ms) FROM agent_logs GROUP BY agent_name`
2. Review recent changes to that agent's code
3. Check token usage: `SELECT agent_name, AVG(tokens_in + tokens_out) FROM agent_logs GROUP BY agent_name`
4. Roll back if recent deploy

## P3 (Medium): Budget Alert

**Action**:
1. Review cost breakdown by agent
2. Reduce batch size or worker count
3. Pause non-critical agents
4. Switch to cheaper models where possible
```

---

## Conclusion

This deployment & operations guide covers:
- Local development setup
- Docker containerization
- Production AWS deployment with Terraform
- Monitoring, alerting, and observability
- Scaling strategies
- Backup and disaster recovery
- CI/CD pipeline
- Daily operations and incident response

**Next Steps**:
1. Set up local environment (2 hours)
2. Run tests and verify functionality
3. Deploy to staging (4-8 hours)
4. Run load tests
5. Deploy to production (2-4 hours)
6. Monitor metrics continuously

**Support**:
- Documentation: See `/docs/`
- Logs: `docker-compose logs -f`
- Dashboard: http://localhost:8501 (after deployment)
- Issues: Create GitHub issue with logs attached

