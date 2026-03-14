# Deployment & Licensing Strategy

## 1. Docker Deployment

### 1.1 docker-compose.yml

```yaml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16-latest
    environment:
      POSTGRES_USER: quixai
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: mega_quixai
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "quixai"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - mega_quixai

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - mega_quixai

  mega_quixai:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DB_HOST: postgres
      DB_USER: quixai
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: mega_quixai
      REDIS_URL: redis://redis:6379
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    networks:
      - mega_quixai
    restart: unless-stopped

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - mega_quixai
    networks:
      - mega_quixai

volumes:
  postgres_data:
  redis_data:

networks:
  mega_quixai:
    driver: bridge
```

### 1.2 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project files
COPY pyproject.toml pyproject.toml
COPY uv.lock uv.lock
COPY src/ src/
COPY sql/ sql/

# Install dependencies with uv
RUN /root/.cargo/bin/uv pip install --no-cache -r <(uv pip compile pyproject.toml)

# Create non-root user
RUN useradd -m -u 1000 quixai
USER quixai

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "src.main"]
```

---

## 2. Kubernetes Deployment (Optional Scale)

```yaml
# k8s/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: mega-quixai
  labels:
    app: mega-quixai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mega-quixai
  template:
    metadata:
      labels:
        app: mega-quixai
    spec:
      containers:
      - name: mega-quixai
        image: megaquixai:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: anthropic
        - name: DB_HOST
          value: postgres
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: user
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: mega-quixai-service
spec:
  selector:
    app: mega-quixai
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mega-quixai-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mega-quixai
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 3. Production Systemd Service

```ini
# /etc/systemd/system/mega-quixai.service

[Unit]
Description=MEGA QUIXAI Multi-Agent System
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=quixai
WorkingDirectory=/opt/mega-quixai
Environment="ENVIRONMENT=production"
ExecStart=/usr/bin/docker compose up -d
ExecReload=/usr/bin/docker compose restart
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable mega-quixai
sudo systemctl start mega-quixai
sudo systemctl status mega-quixai
```

---

## 4. CI/CD Pipeline (GitHub Actions)

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
        image: pgvector/pgvector:pg16-latest
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_mega_quixai
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install uv
      run: curl -LsSf https://astral.sh/uv/install.sh | sh

    - name: Install dependencies
      run: /root/.cargo/bin/uv pip install -r <(uv pip compile pyproject.toml)

    - name: Lint with ruff
      run: ruff check .

    - name: Type check with mypy
      run: mypy src --strict

    - name: Run tests
      run: pytest test/ --cov=src --cov-fail-under=80
      env:
        DB_HOST: localhost
        DB_USER: postgres
        DB_PASSWORD: test

    - name: Upload coverage
      uses: codecov/codecov-action@v3

  build:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'

    steps:
    - uses: actions/checkout@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Login to Docker Hub
      uses: docker/login-action@v2
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}

    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: |
          megaquixai:latest
          megaquixai:${{ github.sha }}
        cache-from: type=registry,ref=megaquixai:buildcache
        cache-to: type=registry,ref=megaquixai:buildcache,mode=max

  deploy:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'

    steps:
    - uses: actions/checkout@v3

    - name: Deploy to production
      run: |
        ssh deploy@prod.megaquixai.com << 'EOF'
          cd /opt/mega-quixai
          docker pull megaquixai:latest
          docker compose down
          docker compose up -d
          docker compose exec mega_quixai python -m alembic upgrade head
        EOF
      env:
        SSH_KEY: ${{ secrets.PROD_SSH_KEY }}
```

---

## 5. Monitoring & Logging

### 5.1 Prometheus Metrics

```python
# src/monitoring/prometheus.py

from prometheus_client import Counter, Histogram, Gauge
import time

# Counters
agent_invocations = Counter(
    'agent_invocations_total',
    'Total agent invocations',
    ['agent_id', 'status']
)

api_calls = Counter(
    'api_calls_total',
    'Total API calls',
    ['model', 'agent_id']
)

# Gauges
monthly_spend = Gauge(
    'monthly_spend_usd',
    'Monthly API spend',
    ['agent_id']
)

leads_in_pipeline = Gauge(
    'leads_in_pipeline',
    'Current leads in pipeline',
    ['stage']
)

# Histograms
agent_latency = Histogram(
    'agent_latency_seconds',
    'Agent execution latency',
    ['agent_id']
)

def track_agent_execution(agent_id: str):
    """Decorator to track agent execution."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                agent_invocations.labels(agent_id=agent_id, status='success').inc()
                return result
            except Exception as e:
                agent_invocations.labels(agent_id=agent_id, status='error').inc()
                raise
            finally:
                duration = time.time() - start
                agent_latency.labels(agent_id=agent_id).observe(duration)
        return wrapper
    return decorator
```

### 5.2 ELK Stack Configuration

```yaml
# docker-compose.yml (logging services)

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  kibana:
    image: docker.elastic.co/kibana/kibana:8.0.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.0.0
    volumes:
      - ./logs:/var/log/mega_quixai:ro
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
    depends_on:
      - elasticsearch
```

---

## 6. Licensing Strategy

### 6.1 Licensing Model

MEGA QUIXAI uses a **SaaS Licensing Model**:

```
Base License: 200€/month
├─ 1 agent deployment
├─ Up to 100 leads/month
├─ LangFuse observability
└─ Email support

Advanced License: 500€/month
├─ 2 concurrent agents
├─ Up to 500 leads/month
├─ Priority support
└─ Custom integrations

Enterprise License: 2000€+/month
├─ 3+ concurrent agents
├─ Unlimited leads
├─ Dedicated infrastructure
├─ Phone + email support
└─ Custom SLA
```

### 6.2 License Verification

```python
# src/licensing/license_manager.py

from datetime import datetime, timedelta
from typing import Optional
import jwt
from pydantic import BaseModel

class LicenseInfo(BaseModel):
    customer_id: str
    license_tier: str  # "base", "advanced", "enterprise"
    agent_limit: int
    lead_limit_monthly: int
    expires_at: datetime
    features: list[str]

class LicenseManager:
    """Verify and enforce licenses."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def verify_license(self, license_token: str) -> Optional[LicenseInfo]:
        """Verify license token."""

        try:
            payload = jwt.decode(license_token, self.secret_key, algorithms=["HS256"])

            license_info = LicenseInfo(**payload)

            if license_info.expires_at < datetime.now():
                return None  # License expired

            return license_info

        except jwt.InvalidTokenError:
            return None

    def generate_license(
        self,
        customer_id: str,
        tier: str,
        duration_days: int = 365,
    ) -> str:
        """Generate new license token."""

        tiers = {
            "base": {
                "agent_limit": 1,
                "lead_limit_monthly": 100,
                "features": ["basic_agents", "langfuse"],
            },
            "advanced": {
                "agent_limit": 2,
                "lead_limit_monthly": 500,
                "features": ["basic_agents", "langfuse", "custom_integrations"],
            },
            "enterprise": {
                "agent_limit": 999,
                "lead_limit_monthly": 999999,
                "features": ["all"],
            },
        }

        tier_info = tiers.get(tier, tiers["base"])

        payload = {
            "customer_id": customer_id,
            "license_tier": tier,
            "agent_limit": tier_info["agent_limit"],
            "lead_limit_monthly": tier_info["lead_limit_monthly"],
            "expires_at": (datetime.now() + timedelta(days=duration_days)).isoformat(),
            "features": tier_info["features"],
        }

        token = jwt.encode(payload, self.secret_key, algorithm="HS256")

        return token

    def check_lead_quota(self, license_info: LicenseInfo, current_month_leads: int) -> bool:
        """Check if lead usage is within quota."""

        return current_month_leads < license_info.lead_limit_monthly

    def check_agent_quota(self, license_info: LicenseInfo, active_agents: int) -> bool:
        """Check if agent count is within quota."""

        return active_agents <= license_info.agent_limit
```

### 6.3 Billing Integration (Stripe)

```python
# src/billing/stripe_integration.py

import stripe
from typing import Optional

class BillingManager:
    """Manage billing via Stripe."""

    def __init__(self, api_key: str):
        stripe.api_key = api_key

    def create_subscription(
        self,
        customer_email: str,
        tier: str,
        billing_cycle_anchor: Optional[int] = None,
    ) -> dict:
        """Create Stripe subscription."""

        prices = {
            "base": "price_base_monthly",
            "advanced": "price_advanced_monthly",
            "enterprise": "price_enterprise_monthly",
        }

        # Create customer
        customer = stripe.Customer.create(
            email=customer_email,
            metadata={"tier": tier},
        )

        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": prices.get(tier)}],
            payment_behavior="default_incomplete",
        )

        return {
            "customer_id": customer.id,
            "subscription_id": subscription.id,
            "status": subscription.status,
        }

    def cancel_subscription(self, subscription_id: str):
        """Cancel subscription."""

        stripe.Subscription.delete(subscription_id)

    def get_invoice_history(self, customer_id: str) -> list:
        """Get customer invoices."""

        invoices = stripe.Invoice.list(customer=customer_id)

        return [
            {
                "id": inv.id,
                "amount": inv.amount_paid / 100,
                "date": inv.created,
                "status": inv.status,
            }
            for inv in invoices
        ]
```

---

## 7. Scaling Strategy

### Phase 1: Single Server (MVP)
- 1 VPS (8GB RAM, 4 CPU)
- PostgreSQL local
- Redis local
- Max: 100 leads/month

### Phase 2: Distributed Services
- PostgreSQL on managed service (AWS RDS)
- Redis on managed service (ElastiCache)
- 2-3 application servers
- Load balancer
- Max: 1000 leads/month

### Phase 3: Kubernetes Cluster
- 3+ worker nodes
- Managed database
- Auto-scaling pods
- Max: 10000+ leads/month

---

## 8. Production Checklist

Before deploying to production:

- [ ] All tests passing (80%+ coverage)
- [ ] Security audit completed
- [ ] SSL/TLS certificates configured
- [ ] Database backups automated (daily)
- [ ] Monitoring configured (Prometheus, ELK)
- [ ] Alerts configured (Slack, PagerDuty)
- [ ] Rate limiting enabled
- [ ] V-Code safety system active
- [ ] License verification enabled
- [ ] Disaster recovery plan documented
- [ ] Staff training completed
- [ ] Documentation up-to-date

---

*Document Version*: 1.0
*Date*: 2026-03-14
*Status*: COMPLETE
