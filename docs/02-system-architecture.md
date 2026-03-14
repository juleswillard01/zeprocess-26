# Implementation Guide - MEGA QUIXAI

## Phase 1: Foundation (Weeks 1-2)

### 1.1 Environment Setup

```bash
# Clone and setup
cd /home/jules/Documents/3-git/zeprocess/main

# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Setup environment variables
cat > .env << 'EOF'
# Claude API
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_BUDGET_USD=5000

# Database
DB_HOST=localhost
DB_USER=quixai
DB_PASSWORD=secure_password_here
DB_NAME=mega_quixai

# LangFuse
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-...

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Instagram
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...

# LangGraph
LANGCHAIN_API_KEY=...
LANGCHAIN_TRACING_V2=true

# Observability
SENTRY_DSN=...
LOG_LEVEL=INFO
EOF

# Add to .gitignore
echo ".env" >> .gitignore
```

### 1.2 Database Initialization

```bash
# Start PostgreSQL
docker compose up -d postgres

# Wait for healthy status
docker compose exec postgres pg_isready -U quixai

# Initialize schema
docker compose exec postgres psql -U quixai -d mega_quixai < sql/schema.sql

# Verify pgvector
docker compose exec postgres psql -U quixai -d mega_quixai -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 1.3 Claude SDK Integration Test

```python
# /home/julius/Documents/3-git/zeprocess/main/test_claude_setup.py

from src.llm.claude_sdk_config import ClaudeSDKManager

# Test basic setup
sdk = ClaudeSDKManager()

# Test routing
print("Testing model routing...")
print(f"Haiku tasks: {sdk.models['haiku'].use_cases}")
print(f"Sonnet tasks: {sdk.models['sonnet'].use_cases}")
print(f"Opus tasks: {sdk.models['opus'].use_cases}")

# Test invocation
response = sdk.invoke(
    messages=[{"role": "user", "content": "Hello, test this"}],
    task="test_routing",
    complexity=0.3,
)

print(f"Model used: {response['metadata']['model_tier']}")
print(f"Cost: ${response['metadata']['cost_usd']:.4f}")
print(f"Tokens: {response['metadata']['total_tokens']}")

# Verify budget tracking
print(f"Remaining budget: ${response['metadata']['remaining_budget']:.2f}")
```

Run: `python test_claude_setup.py`

---

## Phase 2: Agent Development (Weeks 3-4)

### 2.1 LEAD ACQUISITION Agent

```python
# /home/julius/Documents/3-git/zeprocess/main/src/agents/lead_acquisition_agent.py
# (Already provided in architecture doc)

# Test implementation
python -m pytest test/agents/test_lead_acquisition.py -v
```

**Test Suite**:
```python
# test/agents/test_lead_acquisition.py

import pytest
from uuid import uuid4
from src.agents.lead_acquisition_agent import LeadAcquisitionAgent
from src.agents.base_agent import AgentState
from src.llm.claude_sdk_config import ClaudeSDKManager

@pytest.fixture
def agent():
    sdk = ClaudeSDKManager()
    db_client = MockDB()
    return LeadAcquisitionAgent(sdk, db_client)

def test_score_icp_high_match(agent):
    lead_data = {
        "age": 28,
        "bio": "Intéressé par la séduction et développement personnel",
        "engagement_rate": 0.08,
        "follower_count": 500,
        "following_count": 200,
    }
    score = agent._score_icp(lead_data)
    assert score > 0.7

def test_score_icp_low_match(agent):
    lead_data = {
        "age": 65,
        "bio": "Retraité, pas intéressé",
        "engagement_rate": 0.01,
        "follower_count": 50000,
        "following_count": 100,
    }
    score = agent._score_icp(lead_data)
    assert score < 0.3

def test_spam_detection_bots(agent):
    lead_data = {
        "username": "bot_fake_followers_2024",
        "bio": "follow4follow #bot",
        "follower_count": 10000,
        "following_count": 50,
    }
    assert agent._check_spam(lead_data) == True

def test_first_contact_generation(agent):
    lead_data = {
        "username": "jean_paris",
        "bio": "Cherche à améliorer ma confiance",
        "age": 26,
    }
    message = agent._generate_first_contact(lead_data)
    assert len(message) < 300
    assert "jean" not in message.lower()  # No spam-like personalization
```

---

### 2.2 SÉDUCTION Agent

```python
# Run with RAG context
pytest test/agents/test_seduction.py -v

# Manual test with RAG
python -c "
from src.agents.seduction_agent import SeductionAgent
from src.rag.retriever import RAGRetriever
from uuid import uuid4

# Create test context
lead_id = uuid4()
rag_context = {
    'pain_points': ['manque de confiance', 'difficultés en approche'],
    'engagement_level': 'high',
    'recent_topics': ['séduction', 'confiance'],
}

# Test response generation
agent = SeductionAgent(...)
response = agent._generate_response(
    lead_id=lead_id,
    incoming_message='Comment tu as appris tout ça?',
    rag_context=rag_context,
)
print(f'Response: {response}')
"
```

### 2.3 CLOSING Agent

```python
# Test objection handling
pytest test/agents/test_closing.py -v

# Specific objection test
python -c "
from src.agents.closing_agent import ClosingAgent

agent = ClosingAgent(...)

# Test price objection
response = agent._handle_objection_price(
    state=AgentState(...),
    objection='C\'est trop cher, 2000€ c\'est beaucoup'
)
print(f'Response: {response}')
assert 'plan' in response.lower() or 'paiement' in response.lower()
"
```

---

## Phase 3: Integration & Testing (Weeks 5-6)

### 3.1 End-to-End Flow

```python
# test/integration/test_e2e_flow.py

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime

from src.main import MegaQuixaiOrchestrator
from src.agents.base_agent import AgentState

@pytest.fixture
async def orchestrator():
    return MegaQuixaiOrchestrator()

@pytest.mark.asyncio
async def test_lead_to_closing_flow(orchestrator):
    """Test complete pipeline: new lead → closing."""

    # Create test lead
    lead_id = uuid4()
    orchestrator.db_client.create_lead({
        "id": lead_id,
        "source": "instagram",
        "username": "test_prospect",
        "bio": "Intéressé par la séduction",
        "age": 28,
        "status": "new",
    })

    # Stage 1: LEAD_ACQUISITION
    lead_state = AgentState(lead_id=lead_id, agent_id="LEAD_ACQUISITION")
    result = await orchestrator.agents["LEAD_ACQUISITION"].invoke(lead_state)

    assert result.status == "completed"
    assert result.score > 0.5  # ICP match

    # Stage 2: SÉDUCTION
    seduction_state = AgentState(
        lead_id=lead_id,
        agent_id="SEDUCTION",
        conversation_history=[
            {"role": "assistant", "content": "First DM from LEAD_ACQUISITION"},
            {"role": "user", "content": "Salut, ça m'intéresse"},
        ]
    )
    result = await orchestrator.agents["SEDUCTION"].invoke(seduction_state)

    assert result.status == "completed"
    if result.score >= 7:
        # Ready for closing

        # Stage 3: CLOSING
        closing_state = AgentState(
            lead_id=lead_id,
            agent_id="CLOSING",
            conversation_history=seduction_state.conversation_history + [
                {"role": "assistant", "content": "Engaging message"},
                {"role": "user", "content": "Comment ça marche? Quel prix?"},
            ]
        )
        result = await orchestrator.agents["CLOSING"].invoke(closing_state)

        assert result.status in ["closed_won", "objecting"]

@pytest.mark.asyncio
async def test_cost_tracking(orchestrator):
    """Verify cost tracking and budgeting."""

    initial_budget = orchestrator.budget_manager.allocation.total_monthly_usd

    # Run agent
    lead_id = uuid4()
    state = AgentState(lead_id=lead_id, agent_id="LEAD_ACQUISITION")
    result = await orchestrator.agents["LEAD_ACQUISITION"].invoke(state)

    # Verify cost recorded
    assert result.cost_usd > 0

    # Check budget deduction
    orchestrator.budget_manager.deduct("LEAD_ACQUISITION", result.cost_usd)
    remaining = orchestrator.budget_manager._estimate_remaining_budget()

    assert remaining < initial_budget
```

### 3.2 V-Code Safety Testing

```python
# test/safety/test_v_code_review.py

import pytest
from src.safety.v_code_review import VCodeReviewer

@pytest.fixture
def reviewer():
    sdk = ClaudeSDKManager()
    config = {"max_charge_usd": 2000, "require_explicit_consent": True}
    return VCodeReviewer(sdk, config)

@pytest.mark.asyncio
async def test_payment_review_exceeds_limit(reviewer):
    """Reject payments over limit."""

    result = await reviewer.review_before_execute(
        operation="stripe_charge",
        parameters={"amount_usd": 5000},  # Exceeds limit
        agent_id="CLOSING",
    )

    assert result["approved"] == False
    assert result["escalate_to_human"] == True

@pytest.mark.asyncio
async def test_payment_review_approved(reviewer):
    """Approve valid payments."""

    result = await reviewer.review_before_execute(
        operation="stripe_charge",
        parameters={
            "amount_usd": 1500,
            "customer_agreed_at": "2025-03-14T10:00:00Z",
        },
        agent_id="CLOSING",
    )

    assert result["approved"] == True

@pytest.mark.asyncio
async def test_dm_spam_review(reviewer):
    """Flag spammy DMs."""

    result = await reviewer.review_before_execute(
        operation="instagram_dm",
        parameters={
            "content": "FREE FREE FREE!!! BUY NOW!!! AMAZING OFFER!!!",
        },
        agent_id="SEDUCTION",
    )

    assert result["approved"] == False
```

---

## Phase 4: Production Deployment (Weeks 7-8)

### 4.1 Docker Deployment

```bash
# Build images
docker compose build

# Start all services
docker compose up -d

# Verify health
docker compose ps

# Check logs
docker compose logs -f mega_quixai

# Run migrations
docker compose exec mega_quixai python -m alembic upgrade head

# Initialize embeddings index
docker compose exec mega_quixai python -c \
  "from src.rag.indexer import IndexManager; IndexManager().build_indexes()"
```

### 4.2 Monitoring & Alerts

```yaml
# alerting-rules.yaml

- name: HighCostAlert
  condition: daily_cost_usd > 150
  action: slack_notification

- name: AgentErrorAlert
  condition: agent_error_rate > 0.05
  action: pagerduty_alert

- name: BudgetWarningAlert
  condition: remaining_budget_usd < 500
  action: slack_warning

- name: HighLatencyAlert
  condition: agent_response_time_ms > 10000
  action: log_warning
```

### 4.3 LangFuse Dashboard

```python
# Setup LangFuse dashboards

# Dashboard 1: Cost Tracking
# Query: SUM(cost_usd) GROUP BY model_tier, agent_id

# Dashboard 2: Conversion Funnel
# Query: COUNT DISTINCT lead_id BY funnel_stage

# Dashboard 3: Agent Performance
# Query: AVG(response_time_ms), AVG(score) BY agent_id
```

---

## Phase 5: Optimization & Scale (Weeks 9-12)

### 5.1 Performance Tuning

```python
# Profile token usage
python -m cProfile -o profile.prof src/main.py

# Analyze with snakeviz
snakeviz profile.prof

# Identify expensive operations
# Optimize high-cost Claude calls with Haiku
```

### 5.2 Scaling Strategy

```
Week 9:
- 10 simultaneous leads processing
- Monitor cost per lead
- Optimize prompt templates

Week 10:
- 20 simultaneous leads
- A/B test first contact messages
- Refine ICP scoring

Week 11:
- 50 simultaneous leads
- Implement conversation batching
- Optimize embedding retrieval

Week 12:
- 100+ simultaneous leads
- Full production SLA (99% uptime)
- Real-time dashboards
```

---

## Testing Strategy

### Coverage Requirements

```bash
# Minimum 80% coverage
pytest --cov=src --cov-fail-under=80 test/

# By module
pytest --cov=src.agents test/agents/
pytest --cov=src.safety test/safety/
pytest --cov=src.llm test/llm/
```

### Test Scenarios

| Scenario | Agent | Coverage |
|----------|-------|----------|
| Happy path (new lead → qualified) | All 3 | ✓ |
| Low ICP score rejection | LEA | ✓ |
| Spam detection | LEA | ✓ |
| DM response generation | SED | ✓ |
| Qualification scoring | SED | ✓ |
| Objection handling (price/timing/doubt) | CLOSING | ✓ |
| Payment processing | CLOSING | ✓ |
| Budget exceeded | Orchestrator | ✓ |
| V-Code approval/rejection | Safety | ✓ |
| Rate limiting | Safety | ✓ |

---

## Troubleshooting

### Common Issues

#### Issue: High Token Usage
**Solution**: Route to Haiku for filtering tasks
```python
# Before: Using Sonnet for filtering
complexity = 0.7  # Too high

# After: Using Haiku
complexity = 0.2
```

#### Issue: Database Connection Errors
**Solution**: Check pgvector container
```bash
docker compose logs postgres
docker compose restart postgres
```

#### Issue: LangFuse Not Tracking
**Solution**: Verify API keys
```bash
echo $LANGFUSE_SECRET_KEY
echo $LANGFUSE_PUBLIC_KEY
# Ensure they're set in .env
```

#### Issue: Instagram API Rate Limits
**Solution**: Add exponential backoff
```python
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=2, max=10))
def send_dm(message):
    # API call with automatic retry
    pass
```

---

## Success Metrics

### Track These KPIs

```sql
SELECT
  DATE(created_at) as date,
  COUNT(*) as leads_processed,
  AVG(icp_match_score) as avg_icp_score,
  SUM(cost_usd) as daily_cost,
  COUNT(CASE WHEN status='qualified' THEN 1 END) as qualified_count,
  ROUND(100.0 * COUNT(CASE WHEN status='qualified' THEN 1 END) / COUNT(*), 2) as qualification_rate
FROM leads
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;
```

### Targets

| Metric | Target | Current |
|--------|--------|---------|
| Leads processed/day | 30-50 | - |
| ICP match rate | >70% | - |
| Qualification rate | >30% | - |
| Cost per lead | <5€ | - |
| Agent response time | <10s | - |
| System uptime | 99% | - |

---

*Document Version*: 1.0
*Date*: 2026-03-14
*Status*: READY FOR IMPLEMENTATION
