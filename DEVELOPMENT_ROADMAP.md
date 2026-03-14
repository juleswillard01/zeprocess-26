# MEGA QUIXAI Development Roadmap

**Phase**: Agent CLOSING Implementation (Phase 1 Core Infrastructure Complete)
**Status**: Ready for Phase 2 (LangGraph Node Development)
**Last Updated**: 2026-03-14

---

## What's Done (Phase 1)

### Infrastructure ✅
- Docker Compose with 5 services (nginx, api, postgres, redis, langfuse)
- systemd units for autonomous 24/7 agent operation
- GitHub Actions CI/CD pipeline (lint → test → build → deploy)
- PostgreSQL schema with pgvector support
- Complete deployment guide (10 phases, 2-3 hours)

### Agent CLOSING Core ✅
- **state_machine.py**: ClosingState dataclass with 11-stage flow
- **llm_interface.py**: Claude API wrapper with token tracking
- **rag_interface.py**: pgvector semantic search for RAG
- **payment_manager.py**: Stripe integration for checkout
- **settings.py**: Pydantic settings for configuration
- **FastAPI app**: Basic app structure with health checks

### Testing Foundation ✅
- pytest configuration with 80% coverage gate
- Test fixtures for prospects, state, and mocks
- Unit tests for LLM interface (complete)
- Test structure: unit, integration, fixtures

---

## What's Next (Phase 2: Immediate Priority)

### A. LangGraph Node Implementation (130 hours total)

**Estimated Timeline**: 2-3 weeks (40 hrs/week)

#### Step 1: Initialize Node (4 hours)
**File**: `agents/closing/nodes.py`

```python
# Skeleton to implement:
async def node_init(state: ClosingState) -> ClosingState:
    """INIT node: Load prospect, generate opening message."""
    # 1. Load prospect from database
    # 2. Get segment-specific opening template
    # 3. Use RAG to find relevant content
    # 4. Call LLM to personalize opening
    # 5. Send via Twilio WhatsApp
    # 6. Update state: stage="opening_sent"
    return state

# Similar stubs for:
# - node_listen (wait for response, 48h timeout)
# - node_converse (multi-turn conversation)
# - node_objection_handling (detect + counter-argue)
# - node_offer_presented (stripe checkout)
```

**Tests to write**:
- `test_node_init_loads_prospect`
- `test_node_init_generates_personalized_opening`
- `test_node_init_sends_whatsapp_message`
- `test_node_init_updates_state`

#### Step 2: Tools Layer (6 hours)
**File**: `agents/closing/tools.py`

```python
# Tools to implement:
class RAGLookupTool:
    async def lookup_objection_counter(objection: str) -> str:
        # Search for training content relevant to objection
        pass

class OfferGeneratorTool:
    async def generate_offer(segment: str, pain_points: list[str]) -> dict:
        # Create pricing offer based on segment
        pass

class ProspectDBTool:
    async def update_prospect_stage(prospect_id: str, stage: str) -> bool:
        # Persist stage changes
        pass

class WhatsAppSenderTool:
    async def send_message(prospect_id: str, message: str) -> bool:
        # Send via Twilio WhatsApp API
        pass

class StripeCheckoutTool:
    async def create_session(prospect_id: str, amount: float) -> str:
        # Create Stripe checkout session
        pass
```

**Tests**: `tests/unit/test_tools.py` (8 test cases)

#### Step 3: Build LangGraph (5 hours)
**File**: `agents/closing/graph_builder.py`

```python
from langgraph.graph import StateGraph

def build_closing_graph() -> StateGraph:
    """Build 5-node LangGraph for agent CLOSING."""
    graph = StateGraph(ClosingState)
    
    # Add nodes
    graph.add_node("init", node_init)
    graph.add_node("listen", node_listen)
    graph.add_node("converse", node_converse)
    graph.add_node("objection_handling", node_objection_handling)
    graph.add_node("offer_presented", node_offer_presented)
    
    # Add edges (routing logic)
    graph.add_edge("init", "listen")
    graph.add_conditional_edges(
        "listen",
        should_route_to_converse,  # function that checks if response received
        {
            True: "converse",
            False: "listen",  # retry
        }
    )
    # ... etc
    
    return graph.compile()
```

**Tests**: `tests/integration/test_state_machine.py` (6 test cases)

#### Step 4: Prompts & Templates (3 hours)
**File**: `agents/closing/prompts.py`

```python
PROMPT_TEMPLATES = {
    "opening_high_value": """
    You are a sales expert. Prospect is a {name} from {company}.
    Their pain point is {pain_point}.
    
    Generate a personalized, warm opening message (2-3 sentences).
    Make it personal, not salesy.
    """,
    
    "opening_mid_market": "...",
    "opening_startup": "...",
    
    "objection_handler_price": """
    Prospect objected: "{objection_text}"
    
    Using this training content:
    {rag_context}
    
    Generate a brief (1-2 sentence) counter-argument.
    """,
    
    # ... 20+ other templates
}
```

**Tests**: `tests/unit/test_prompts.py` (verify all templates render)

#### Step 5: Observability & Metrics (4 hours)
**File**: `agents/closing/analytics.py`

```python
class ClosingAnalytics:
    """Track metrics: response rate, conversion, cost per lead."""
    
    async def record_response(prospect_id: str, response: str) -> None:
        # Track when prospect responds
        
    async def record_conversion(prospect_id: str, amount: float) -> None:
        # Track when sale is made
        
    async def get_dashboard_metrics(timeframe: str) -> dict:
        # Return: response_rate, conversion_rate, cost_per_lead, ROI
```

**Tests**: `tests/unit/test_analytics.py` (8 test cases)

#### Step 6: Error Handling & Recovery (3 hours)
**File**: Add to `nodes.py`

```python
# For each node:
async def node_<name>_with_retry(state: ClosingState) -> ClosingState:
    """Node with exponential backoff retry."""
    max_retries = state.max_retries
    for attempt in range(max_retries):
        try:
            return await node_<name>(state)
        except Exception as e:
            if attempt == max_retries - 1:
                state.last_error = str(e)
                state.stage = "declined"  # or appropriate fallback
                return state
            await asyncio.sleep(2 ** attempt)  # exponential backoff
```

**Tests**: `tests/unit/test_error_handling.py` (5 test cases)

---

### B. Database Schema Updates (2 hours)

**File**: `database/migrations/001_create_closing_tables.sql`

```sql
-- Prospects table
CREATE TABLE prospects (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    whatsapp_id VARCHAR(50),
    segment VARCHAR(50),
    qualification_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    prospect_id UUID REFERENCES prospects(id),
    stage VARCHAR(50),
    messages JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Closing metrics table
CREATE TABLE closing_metrics (
    id UUID PRIMARY KEY,
    prospect_id UUID REFERENCES prospects(id),
    response_count INT,
    objection_count INT,
    conversion_amount FLOAT,
    stripe_session_id VARCHAR(255),
    created_at TIMESTAMP
);
```

---

### C. Integration Tests (4 hours)

**File**: `tests/integration/test_closing_e2e.py`

Test the complete flow:
1. Prospect enters system
2. Opening message sent
3. Mock response received
4. Objection detected and handled
5. Offer presented
6. Payment processed (mock Stripe webhook)
7. State persisted to database

```python
@pytest.mark.integration
async def test_closing_happy_path():
    """Test complete closing flow: prospect → conversion."""
    # Setup
    prospect = await create_test_prospect()
    state = ClosingState(prospect=prospect)
    graph = build_closing_graph()
    
    # Run
    result = await graph.ainvoke(state)
    
    # Assert
    assert result.stage == "converted"
    assert result.converted == True
    assert result.final_amount > 0
```

---

## Implementation Checklist

### Week 1 (Mon-Fri)
- [ ] **Mon-Tue**: Implement `node_init` + tests (8 hrs)
- [ ] **Tue-Wed**: Implement `node_listen`, `node_converse` (10 hrs)
- [ ] **Wed-Thu**: Tools layer + tests (8 hrs)
- [ ] **Thu-Fri**: Prompts + LangGraph builder (8 hrs)

### Week 2
- [ ] **Mon-Tue**: Objection handling node + tests (8 hrs)
- [ ] **Tue-Wed**: Offer node + payment integration (8 hrs)
- [ ] **Wed-Thu**: Analytics + observability (6 hrs)
- [ ] **Thu-Fri**: Error handling + database schema (6 hrs)

### Week 3
- [ ] **Mon**: Integration tests (4 hrs)
- [ ] **Tue-Thu**: Fix bugs, optimize, add edge cases (12 hrs)
- [ ] **Fri**: Code review, documentation (4 hrs)

---

## Code Structure (Copy-Paste Ready)

All templates and stubs are in `.claude/03-closing-agent-implementation-guide.md`

Key locations:
- LLM interface: Already done (agents/closing/llm_interface.py)
- RAG interface: Already done (agents/closing/rag_interface.py)
- Payment manager: Already done (agents/closing/payment_manager.py)
- State machine: Already done (agents/closing/state_machine.py)

Next to implement:
- **nodes.py**: 200 lines (5 node functions)
- **tools.py**: 250 lines (5 tool classes)
- **graph_builder.py**: 100 lines (graph definition)
- **prompts.py**: 150 lines (message templates)
- **analytics.py**: 200 lines (metrics tracking)

**Total**: ~900 lines of core agent code

---

## Testing Coverage

Target: **80% overall coverage** + 100% coverage of critical paths

### Unit Tests (70% coverage)
- `test_nodes.py`: 12 test cases
- `test_tools.py`: 10 test cases
- `test_prompts.py`: 5 test cases
- `test_analytics.py`: 8 test cases
- `test_error_handling.py`: 5 test cases

### Integration Tests (10% coverage)
- `test_closing_e2e.py`: 4 end-to-end scenarios
- `test_payment_flow.py`: Payment processing with Stripe mock

### Run Tests
```bash
pytest tests/ --cov=agents/closing --cov-fail-under=80

# Run with detailed output
pytest tests/unit/test_nodes.py -v --tb=short
```

---

## Dependencies Already Installed

Run `uv sync` to install:

```bash
# From pyproject.toml
anthropic>=0.28.0           ✅ (Claude API)
langgraph>=0.2.0            ✅ (State machine)
langchain>=0.1.0            ✅ (Tool integrations)
stripe>=7.8.0               ✅ (Payments)
twilio>=8.10.0              ✅ (WhatsApp)
fastapi>=0.104.0            ✅ (API)
asyncpg>=0.29.0             ✅ (Postgres)
sentence-transformers>=5.3  ✅ (Embeddings)
pytest>=7.4.0               ✅ (Testing)
```

---

## Common Pitfalls to Avoid

1. **State mutations**: Always return new ClosingState, never mutate in place
2. **Async/await**: All node functions must be `async`
3. **Token tracking**: Count tokens in LLM calls, not just in result
4. **Error handling**: Use try/except in each node, never let exceptions bubble
5. **Database**: Always use connection pool, never sync queries
6. **Testing**: Mock Stripe, Twilio, and Anthropic API in tests
7. **Logging**: Log state transitions, LLM calls, and errors with context

---

## Next Steps (After Phase 2)

### Phase 3: Scaling & Optimization (2 weeks)
- Load test: 1000 concurrent prospects
- Prompt optimization: A/B test opening messages
- Cost optimization: Token reduction strategies
- Performance tuning: Cache RAG results, batch LLM calls

### Phase 4: Agent FOLLOW (Customer Retention)
- Build onboarding automation
- Monitor usage and engagement
- Trigger upsell campaigns
- Measure churn prevention

### Phase 5: Production Monitoring
- Real-time metrics dashboard
- Alert thresholds (low conversion, high costs)
- Cost tracking and optimization
- Customer success tracking

---

## Questions / Support

**Architecture**: See `.claude/02-agent-closing-architecture.md`
**Use Cases**: See `.claude/04-closing-agent-use-cases-and-diagrams.md`
**Code Templates**: See `.claude/03-closing-agent-implementation-guide.md`
**Setup**: See `DEPLOYMENT_GUIDE.md`

---

**Status**: Ready to start Phase 2 (Week 1: LangGraph nodes)
**Owner**: Backend Engineering Team
**Estimated Effort**: 130 hours (3-4 weeks at 40 hrs/week)
