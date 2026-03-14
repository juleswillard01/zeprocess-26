# Phase 2 Plan: Tools & External APIs Integration

## Overview
Phase 2 replaces all mock implementations with real Claude API calls, RAG integration via pgvector, and Stripe payment processing. Target: Full end-to-end automation with proper observability.

## Critical Path Tasks

### 1. Claude API Integration
**Objective:** Replace TODO stubs with real Anthropic SDK calls

#### 1a. Haiku Model Routing (Classification Tasks)
**Files to Update:**
- `src/agents/acquisition.py` - `_score_icp()`, `_check_spam()`
- `src/agents/seduction.py` - `_detect_objections()`
- `src/agents/closing.py` - `_detect_final_objections()`

**Implementation Pattern:**
```python
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = await client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=256,
    messages=[{"role": "user", "content": prompt}]
)
```

**Cost Optimization:** Haiku @ $0.80/M input, $4/M output (lowest cost for classification)

#### 1b. Sonnet Model Routing (Generation Tasks)
**Files to Update:**
- `src/agents/acquisition.py` - `_generate_first_contact()`
- `src/agents/seduction.py` - `_generate_response()`, `_handle_objections()`
- `src/agents/closing.py` - `_ask_for_sale()`

**Implementation Pattern:**
```python
response = await client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system="Persona: Persuasive sales coach...",
    messages=[{"role": "user", "content": prompt}]
)
```

**Cost Optimization:** Sonnet @ $3/M input, $15/M output (best speed/cost for generation)

#### 1c. Opus Model Routing (Reasoning Tasks)
**Files to Update:**
- `src/agents/closing.py` - `_create_final_objection_response()`

**Implementation Pattern:**
```python
response = await client.messages.create(
    model="claude-3-opus-20250219",
    max_tokens=2048,
    system="Persona: Expert closer...",
    messages=[{"role": "user", "content": prompt}]
)
```

**Cost Optimization:** Opus @ $15/M input, $75/M output (for complex reasoning only)

#### 1d. Token Management
**Add to agents:**
- Track input/output tokens for cost tracking
- Update ConversationState.total_tokens
- Log token usage to metrics table

### 2. RAG Integration with pgvector
**Objective:** Retrieve relevant coaching content for personalization

#### 2a. PostgreSQL + pgvector Setup
**Prerequisites:**
- Docker Compose: PostgreSQL 15 + pgvector extension
- Create embeddings table: (id, content, embedding, source, metadata)
- Create index on embedding for cosine similarity

**Docker Configuration:**
```yaml
postgres:
  image: pgvector/pgvector:pg15
  environment:
    POSTGRES_DB: zeprocess
    POSTGRES_PASSWORD: ${DB_PASSWORD}
  volumes:
    - pg_data:/var/lib/postgresql/data
```

#### 2b. Embedding Generation
**Files to Create:**
- `src/rag/embeddings.py` - Anthropic Embeddings API integration
- `src/rag/retriever.py` - pgvector similarity search

**Implementation:**
```python
async def generate_embedding(text: str) -> list[float]:
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

async def retrieve_similar(query: str, top_k: int = 5) -> list[dict]:
    embedding = await generate_embedding(query)
    results = await repo.search_by_similarity(embedding, top_k)
    return results
```

#### 2c. RAG Content Loading
**Initial Dataset:**
- YouTube transcripts (from previous RAG pipeline)
- Coaching frameworks and scripts
- Objection handling guides
- Success stories and case studies

**Files to Create:**
- `scripts/load_rag_data.py` - Batch loader for initial content

### 3. Stripe Payment Processing
**Objective:** Real payment processing with checkout sessions

#### 3a. Stripe SDK Integration
**Files to Update:**
- `src/agents/closing.py` - `_stripe_charge()`, `_v_code_review_payment()`

**Implementation:**
```python
import stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_checkout_session(lead: Lead, amount: int) -> str:
    session = await stripe.checkout.Session.create(
        success_url=f"{os.getenv('FRONTEND_URL')}/success",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/cancel",
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Coaching Package"},
                "unit_amount": amount
            },
            "quantity": 1
        }]
    )
    return session.url

async def verify_payment(session_id: str) -> dict:
    session = await stripe.checkout.Session.retrieve(session_id)
    return {
        "status": session.payment_status,
        "amount": session.amount_total,
        "customer_email": session.customer_email
    }
```

#### 3b. Webhook Handling
**Files to Create:**
- `src/webhooks/stripe.py` - Stripe webhook handler
- Endpoints: `/webhooks/stripe` for charge.succeeded, charge.failed

#### 3c. V-Code Payment Safety
**Update:** `_v_code_review_payment()` with real checks
- Integration with payment fraud detection API (future)
- Enhanced conversion probability calculation

### 4. LangFuse Observability
**Objective:** Production monitoring and cost tracking

#### 4a. Installation & Setup
```python
from langfuse import Langfuse
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)
```

#### 4b. Instrumentation Points
**Agent Execution:**
- Track execution time per agent
- Log input/output tokens
- Track routing decisions

**Payment Processing:**
- Track checkout session creation
- Log payment success/failure
- Monitor conversion metrics

**RAG Retrieval:**
- Log retrieval latency
- Track similarity scores
- Monitor cache hit rate

#### 4c. Dashboard Metrics
- Agent execution success rate
- Average latency per agent
- Token usage and costs (Haiku/Sonnet/Opus)
- Payment success rate
- Lead conversion funnel

### 5. Twilio WhatsApp Integration (Optional Phase 2)
**Objective:** WhatsApp messaging channel

**Files to Create:**
- `src/messaging/twilio.py` - Twilio WhatsApp client
- `src/webhooks/twilio.py` - Message webhook handler

**Endpoints:**
- POST `/webhooks/twilio/messages` - Receive WhatsApp messages
- Trigger orchestration pipeline on incoming message

## Implementation Order

1. **Week 1: Claude API Integration**
   - Set up Anthropic SDK with async support
   - Replace Haiku stubs (3 methods)
   - Replace Sonnet stubs (4 methods)
   - Replace Opus stubs (1 method)
   - Add token tracking

2. **Week 2: RAG Setup & Integration**
   - Docker Compose: PostgreSQL + pgvector
   - Embeddings API integration
   - pgvector similarity search
   - Load initial YouTube transcript data
   - Integrate into SeductionAgent

3. **Week 3: Stripe Integration**
   - Stripe SDK setup
   - Checkout session creation
   - Payment verification
   - Webhook handling
   - Update ClosingAgent

4. **Week 4: Observability & Testing**
   - LangFuse instrumentation
   - Integration tests
   - E2E tests with real APIs
   - Performance benchmarking
   - Documentation

## Configuration Management

### Environment Variables Needed
```
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_ORG_ID=org-...

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/zeprocess

# Stripe
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# LangFuse
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Frontend
FRONTEND_URL=https://app.example.com

# Twilio (optional)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=+1234567890
```

### .env.example Creation
```bash
cp config/.env.example config/.env.local
# Edit with development credentials
```

## Testing Strategy

### Unit Tests
- Mock Anthropic API responses
- Test token calculation
- Test RAG similarity ranking

### Integration Tests
- Real PostgreSQL with pgvector
- Real Stripe sandbox environment
- Real Anthropic API (low-cost Haiku calls)

### E2E Tests
- Full lead flow: discovery → acquisition → seduction → closing
- Payment flow: checkout → webhook → completion
- Observability: Verify LangFuse logging

### Cost Testing
- Track estimated monthly costs for 100 leads
- Optimize prompt lengths
- Monitor token efficiency

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| API Rate Limits | Pipeline stalled | Implement backoff + queue |
| Stripe Failures | Lost payments | Webhook retry + manual review |
| pgvector Latency | Slow responses | Connection pooling + caching |
| Cost Overruns | Budget exceeded | Token limits + monitoring |
| RAG Quality | Poor personalization | Iterative prompt refinement |

## Success Criteria

- [x] All Claude API calls working (Haiku/Sonnet/Opus)
- [x] RAG retrieval returning relevant results
- [x] Stripe checkout sessions creating successfully
- [x] Webhooks receiving and processing events
- [x] LangFuse dashboard showing metrics
- [x] E2E test: Lead → Acquisition → Seduction → Closing → Payment
- [x] Cost tracking: < $0.50 per lead

## Rollout Plan

### Staging
1. Deploy to staging environment
2. Test with real APIs (sandbox credentials)
3. Run 50-lead E2E test
4. Monitor costs and performance

### Production
1. Deploy to production with real credentials
2. Start with 10 leads/day for first week
3. Scale to 100 leads/day after validation
4. Monitor dashboard for issues
5. Iterate on prompt quality

---
**Phase 2 Start Date:** Upon Phase 1 approval
**Estimated Duration:** 4 weeks
**Resource: Winston + Claude Ops Engineer**
