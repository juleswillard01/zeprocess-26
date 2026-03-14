# Agent CLOSING - Implementation Guide
## Step-by-step Code Structure & Configuration

**Document**: Implementation roadmap with code examples
**Target Audience**: Development team ready to build
**Timeline**: 5-6 weeks to production

---

## File Structure

```
zeprocess/main/
├── agents/
│   ├── closing/
│   │   ├── __init__.py
│   │   ├── state_machine.py          # LangGraph orchestrator
│   │   ├── nodes.py                  # 5 main nodes (init, converse, etc.)
│   │   ├── tools.py                  # 5 main tools (RAG, offer, payment)
│   │   ├── prompts.py                # Prompt templates (opening, objection, relance)
│   │   ├── llm_interface.py           # Claude API wrapper
│   │   ├── rag_interface.py           # pgvector RAG search
│   │   ├── message_queue.py           # WhatsApp/Email sender
│   │   ├── payment_manager.py         # Stripe integration
│   │   └── analytics.py               # Metrics & observability
│   │
│   ├── seduction/                     # Agent #1 (already exists)
│   └── follow/                        # Agent #3 (onboarding/upsell)
│
├── database/
│   ├── schema.sql                     # CRM + metrics tables
│   ├── migrations/
│   │   ├── 001_create_prospects.sql
│   │   ├── 002_create_conversations.sql
│   │   ├── 003_create_closing_metrics.sql
│   │   └── 004_create_payment_tracking.sql
│   └── seeders/
│       ├── segment_rules.py           # Load SEGMENT_RULES
│       └── prompt_templates.py        # Load all templates
│
├── api/
│   ├── main.py                        # FastAPI app
│   ├── routes/
│   │   ├── closing.py                 # POST /api/closing/start
│   │   ├── webhooks.py                # Stripe + Twilio webhooks
│   │   └── metrics.py                 # GET /api/metrics/dashboard
│   └── middleware.py                  # Auth, rate limiting, logging
│
├── scripts/
│   ├── run_agent.py                   # CLI: python run_agent.py --prospect_id=xxx
│   ├── test_objection_handler.py      # Unit test objections
│   ├── load_test.py                   # Simulate 1000 concurrent prospects
│   └── dashboard_server.py            # Streamlit metrics dashboard
│
├── config/
│   ├── settings.py                    # Environment variables
│   ├── segment_rules.json             # Pricing & positioning by segment
│   ├── prompt_templates.json          # All message templates
│   └── feature_flags.yaml             # A/B testing config
│
├── tests/
│   ├── unit/
│   │   ├── test_nodes.py
│   │   ├── test_tools.py
│   │   ├── test_rag_interface.py
│   │   └── test_payment_manager.py
│   ├── integration/
│   │   ├── test_state_machine.py
│   │   ├── test_end_to_end.py
│   │   └── test_stripe_webhook.py
│   └── fixtures/
│       ├── mock_prospects.json
│       ├── mock_stripe_webhooks.json
│       └── mock_rag_results.json
│
└── docs/
    ├── API.md                         # REST endpoint docs
    ├── DEPLOYMENT.md                  # Docker/K8s setup
    ├── TROUBLESHOOTING.md             # Common issues
    └── CONTRIBUTING.md                # Dev guidelines

```

---

## Phase 1: Core State Machine Setup

### Step 1.1: Create State Definition

**File**: `agents/closing/state_machine.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal

@dataclass
class ProspectProfile:
    """Lead data from Agent SÉDUCTION"""
    id: str
    name: str
    email: str
    phone: str
    whatsapp_id: Optional[str]
    segment: Literal["high_value", "mid_market", "startup"]
    pain_points: list[str]
    budget_range: str
    qualification_score: float
    created_at: datetime
    first_message_sent_at: Optional[datetime] = None
    notes: str = ""

@dataclass
class Message:
    """Single message in conversation"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    source: str = "manual"  # manual | node_init | node_objection_handling

@dataclass
class Objection:
    """Tracked objection"""
    id: str
    type: Literal["price", "timing", "trust", "urgency", "other"]
    text: str
    severity: float  # 0.0-1.0
    detected_at: datetime
    counter_arg: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class ProposedOffer:
    """Pricing offer"""
    price: float
    description: str
    stripe_session_id: str
    stripe_url: str
    created_at: datetime
    expires_at: datetime

@dataclass
class ClosingState:
    """LangGraph state for Agent CLOSING"""
    # Core
    prospect: ProspectProfile

    # Conversation
    messages: list[Message] = field(default_factory=list)
    conversation_turns: int = 0

    # Stage
    stage: Literal[
        "init",
        "opening_sent",
        "waiting_response",
        "conversing",
        "objection_detected",
        "objection_handling",
        "offer_presented",
        "payment_pending",
        "converted",
        "declined",
        "archived"
    ] = "init"

    # Objections
    detected_objections: list[Objection] = field(default_factory=list)

    # Offer
    proposed_offer: Optional[ProposedOffer] = None

    # RAG context
    relevant_content: list[dict] = field(default_factory=list)

    # Metrics
    api_calls_count: int = 0
    total_tokens_used: int = 0
    rag_searches: int = 0
    llm_cost_usd: float = 0.0

    # Status
    converted: bool = False
    conversion_timestamp: Optional[datetime] = None
    final_amount: Optional[float] = None
    stripe_payment_id: Optional[str] = None

    # Error handling
    last_error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
```

### Step 1.2: Create LLM Interface

**File**: `agents/closing/llm_interface.py`

```python
from __future__ import annotations
import logging
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

class LLMInterface:
    """Claude API wrapper with token tracking"""

    def __init__(self, model: str = "claude-opus-4-1"):
        self.client = AsyncAnthropic()
        self.model = model
        self.total_tokens = 0
        self.total_cost = 0.0

    async def generate(
        self,
        template: str,
        variables: dict,
        max_tokens: int = 500
    ) -> tuple[str, int]:
        """
        Generate text using Claude.
        Returns: (text, tokens_used)
        """
        from agents.closing.prompts import PROMPT_TEMPLATES

        prompt_template = PROMPT_TEMPLATES.get(template, "")
        if not prompt_template:
            raise ValueError(f"Template not found: {template}")

        prompt = prompt_template.format(**variables)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        self.total_tokens += tokens
        self._estimate_cost(tokens)

        logger.info(f"LLM call completed", extra={
            "tokens": tokens,
            "template": template,
            "model": self.model
        })

        return text, tokens

    async def classify(
        self,
        text: str,
        categories: list[str],
        max_tokens: int = 20
    ) -> str:
        """Classify text into category"""
        prompt = f"""Classify this text into one of: {', '.join(categories)}.

Text: "{text}"

Classification (single word only):"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        tokens = response.usage.input_tokens + response.usage.output_tokens
        self.total_tokens += tokens

        return response.content[0].text.strip().lower()

    async def extract_objection(self, text: str) -> dict:
        """Extract objection details"""
        prompt = f"""Extract objection details from this prospect message.

Message: "{text}"

Return JSON:
{{
    "type": "price|timing|trust|urgency|other",
    "severity": 0.0-1.0,
    "key_phrase": "quoted phrase"
}}

JSON:"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        tokens = response.usage.input_tokens + response.usage.output_tokens
        self.total_tokens += tokens

        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            return {"type": "other", "severity": 0.5, "key_phrase": text[:50]}

    def _estimate_cost(self, tokens: int):
        """Estimate API cost (update pricing as needed)"""
        # Claude Opus pricing (as of Mar 2026)
        cost = (tokens / 1000) * 0.003  # $3 per 1M tokens
        self.total_cost += cost
```

### Step 1.3: Create RAG Interface

**File**: `agents/closing/rag_interface.py`

```python
from __future__ import annotations
import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RAGInterface:
    """pgvector semantic search"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(self.db_url)
        await self.pool.fetchval("SELECT 1 FROM pg_extension WHERE extname='vector'")
        logger.info("RAG interface connected to pgvector")

    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5
    ) -> list[dict]:
        """
        Search YouTube transcriptions by semantic similarity.

        Args:
            query: Text to search for
            top_k: Number of results
            threshold: Minimum similarity score

        Returns:
            List of relevant chunks with metadata
        """
        if not self.pool:
            raise RuntimeError("RAG interface not connected")

        # Step 1: Generate embedding for query
        from agents.closing.embeddings import embed_text
        embedding = await embed_text(query)

        # Step 2: Vector search
        results = await self.pool.fetch("""
            SELECT
                vc.id,
                vc.video_id,
                v.title,
                v.playlist,
                vc.content,
                vc.timestamp_start,
                vc.timestamp_end,
                1 - (vc.embedding <-> $1::vector) as similarity
            FROM video_chunks vc
            JOIN videos v ON vc.video_id = v.id
            WHERE 1 - (vc.embedding <-> $1::vector) > $2
            ORDER BY vc.embedding <-> $1::vector
            LIMIT $3
        """, embedding, threshold, top_k)

        logger.info(f"RAG search completed", extra={
            "query": query[:50],
            "results": len(results),
            "top_similarity": results[0]["similarity"] if results else None
        })

        return [
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "playlist": r["playlist"],
                "snippet": r["content"][:300],
                "timestamp": f"{r['timestamp_start']}-{r['timestamp_end']}",
                "relevance_score": float(r["similarity"])
            }
            for r in results
        ]
```

### Step 1.4: Create Message Queue

**File**: `agents/closing/message_queue.py`

```python
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class MessageQueueManager:
    """Send/receive messages (WhatsApp, Email, etc.)"""

    def __init__(self, whatsapp_token: str, twilio_sid: str, twilio_auth: str):
        self.whatsapp_token = whatsapp_token
        self.twilio_sid = twilio_sid
        self.twilio_auth = twilio_auth

        # Initialize Twilio client
        from twilio.rest import Client
        self.twilio = Client(twilio_sid, twilio_auth)

    async def send(
        self,
        contact_id: str,
        message: str,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Send message to prospect.

        Args:
            contact_id: WhatsApp phone or email
            message: Message text
            metadata: Extra tracking data

        Returns:
            True if sent successfully
        """
        metadata = metadata or {}

        try:
            if contact_id.startswith("whatsapp:"):
                # Send via WhatsApp
                phone = contact_id.replace("whatsapp:", "+")
                msg = await self._send_whatsapp(phone, message)
                msg_id = msg.sid
                channel = "whatsapp"

            else:
                # Send via Email (not implemented here)
                raise NotImplementedError("Email channel not yet implemented")

            # Log to database
            import asyncpg
            db = asyncpg.connect()
            await db.execute("""
                INSERT INTO messages (contact_id, content, direction, channel, msg_id, metadata, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, contact_id, message, "outbound", channel, msg_id, metadata, datetime.now())

            logger.info(f"Message sent", extra={
                "contact_id": contact_id,
                "channel": channel,
                "length": len(message)
            })

            return True

        except Exception as e:
            logger.error(f"Message send failed", exc_info=True)
            return False

    async def _send_whatsapp(self, phone: str, message: str):
        """Send via Twilio WhatsApp API"""
        try:
            msg = self.twilio.messages.create(
                from_="whatsapp:+14155552671",  # Twilio sandbox number
                body=message,
                to=phone
            )
            return msg
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            raise
```

---

## Phase 2: Node Implementations

### Step 2.1: INIT Node

**File**: `agents/closing/nodes.py` (partial)

```python
from __future__ import annotations
import logging
from datetime import datetime
from agents.closing.state_machine import ClosingState, Message

logger = logging.getLogger(__name__)

async def node_init(
    state: ClosingState,
    llm: LLMInterface,
    rag: RAGInterface,
    message_queue: MessageQueueManager,
    db: asyncpg.Pool
) -> ClosingState:
    """
    INIT node: Load prospect, prepare opening message.
    """

    # 1. Load segment rules
    from config.segment_rules import SEGMENT_RULES
    rules = SEGMENT_RULES.get(state.prospect.segment, {})

    # 2. RAG lookup for context
    pain_point = state.prospect.pain_points[0] if state.prospect.pain_points else "general"
    context_videos = await rag.search(
        f"How to solve {pain_point}",
        top_k=3
    )
    state.relevant_content = context_videos

    # 3. Generate opening message
    opening_prompt = f"opening_message_{state.prospect.segment}"
    opening_msg, tokens = await llm.generate(
        template=opening_prompt,
        variables={
            "name": state.prospect.name,
            "pain_point": pain_point,
            "segment": state.prospect.segment
        },
        max_tokens=150
    )
    state.api_calls_count += 1
    state.total_tokens_used += tokens

    # 4. Send opening message
    success = await message_queue.send(
        state.prospect.whatsapp_id,
        opening_msg,
        metadata={"agent": "closing", "stage": "opening", "prospect_id": state.prospect.id}
    )

    if not success:
        state.last_error = "Failed to send opening message"
        state.retry_count += 1
        return state

    # 5. Add to message history
    state.messages.append(Message(
        role="assistant",
        content=opening_msg,
        timestamp=datetime.now(),
        source="node_init"
    ))

    # 6. Update database
    await db.execute("""
        UPDATE prospects
        SET first_message_sent_at = $1, status = 'opening_sent'
        WHERE id = $2
    """, datetime.now(), state.prospect.id)

    state.stage = "opening_sent"
    logger.info(f"INIT node completed", extra={"prospect_id": state.prospect.id})

    return state
```

### Step 2.2: CONVERSE Node

```python
async def node_converse(
    state: ClosingState,
    llm: LLMInterface,
    rag: RAGInterface,
    message_queue: MessageQueueManager,
    db: asyncpg.Pool
) -> ClosingState:
    """
    CONVERSE node: Multi-turn conversation, detect objections.
    """

    if not state.messages:
        logger.warning("No messages to process")
        return state

    # Get latest prospect message
    prospect_msg = state.messages[-1]

    # 1. Classify message intent
    classification, tokens = await llm.classify(
        prospect_msg.content,
        categories=["positive", "question", "objection", "disinterest"]
    )
    state.api_calls_count += 1
    state.total_tokens_used += tokens

    # 2. If objection detected
    if classification == "objection":
        objection_details = await llm.extract_objection(prospect_msg.content)
        state.detected_objections.append(Objection(
            id=str(uuid.uuid4()),
            type=objection_details.get("type", "other"),
            text=prospect_msg.content,
            severity=objection_details.get("severity", 0.5),
            detected_at=datetime.now()
        ))
        state.stage = "objection_detected"
        logger.info(f"Objection detected", extra={
            "type": objection_details.get("type"),
            "prospect_id": state.prospect.id
        })
        return state

    # 3. Generate conversational response
    response, tokens = await llm.generate(
        template="conversation_response",
        variables={
            "name": state.prospect.name,
            "last_message": prospect_msg.content,
            "segment": state.prospect.segment,
            "turn_count": state.conversation_turns
        },
        max_tokens=300
    )
    state.api_calls_count += 1
    state.total_tokens_used += tokens

    state.messages.append(Message(
        role="assistant",
        content=response,
        timestamp=datetime.now(),
        source="node_converse"
    ))
    state.conversation_turns += 1

    # 4. Send response
    await message_queue.send(state.prospect.whatsapp_id, response)

    # 5. Check if ready for offer
    if state.conversation_turns >= 3 or "ready to see" in response.lower():
        state.stage = "offer_presented"
    else:
        state.stage = "conversing"

    return state
```

---

## Phase 3: Database Schema

**File**: `database/schema.sql`

```sql
-- Prospects (from Agent SÉDUCTION)
CREATE TABLE IF NOT EXISTS prospects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    whatsapp_id VARCHAR(50),
    name VARCHAR(255) NOT NULL,
    segment VARCHAR(50) NOT NULL CHECK (segment IN ('high_value', 'mid_market', 'startup')),
    pain_points TEXT[] DEFAULT '{}',
    budget_range VARCHAR(50),
    qualification_score FLOAT CHECK (qualification_score >= 0.0 AND qualification_score <= 1.0),
    status VARCHAR(50) DEFAULT 'qualified' CHECK (status IN (
        'qualified', 'conversing', 'objection_detected', 'offer_presented',
        'converted', 'declined', 'archived'
    )),
    first_message_sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    CONSTRAINT valid_phone CHECK (phone IS NULL OR phone ~ '^\+?[0-9]{10,}$')
);

CREATE INDEX idx_prospects_status ON prospects(status);
CREATE INDEX idx_prospects_segment ON prospects(segment);
CREATE INDEX idx_prospects_created ON prospects(created_at);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    messages JSONB DEFAULT '[]',  -- [{role, content, timestamp, source}]
    stage VARCHAR(50) DEFAULT 'init',
    objections JSONB DEFAULT '[]',  -- [{type, text, severity, resolved, counter_arg}]
    proposed_offer JSONB,  -- {price, stripe_session_id, stripe_url, expires_at}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(prospect_id)
);

CREATE INDEX idx_conversations_stage ON conversations(stage);
CREATE INDEX idx_conversations_updated ON conversations(updated_at);

-- Closing Metrics
CREATE TABLE IF NOT EXISTS closing_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    conversation_turns INT DEFAULT 0,
    api_calls INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    rag_searches INT DEFAULT 0,
    objections_count INT DEFAULT 0,
    objections_resolved INT DEFAULT 0,
    conversion_achieved BOOLEAN DEFAULT FALSE,
    final_amount FLOAT,
    stripe_session_id VARCHAR(255),
    stripe_payment_id VARCHAR(255),
    llm_cost_usd FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_closing_metrics_prospect ON closing_metrics(prospect_id);
CREATE INDEX idx_closing_metrics_conversion ON closing_metrics(conversion_achieved);
CREATE INDEX idx_closing_metrics_created ON closing_metrics(created_at);

-- Payment Tracking
CREATE TABLE IF NOT EXISTS stripe_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id UUID NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    payment_intent_id VARCHAR(255),
    amount_usd FLOAT NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'expired')),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_stripe_payments_prospect ON stripe_payments(prospect_id);
CREATE INDEX idx_stripe_payments_status ON stripe_payments(status);
CREATE INDEX idx_stripe_payments_session ON stripe_payments(session_id);
```

---

## Phase 4: Testing Strategy

**File**: `tests/unit/test_nodes.py`

```python
import pytest
import asyncio
from datetime import datetime
from agents.closing.state_machine import ClosingState, ProspectProfile, Message
from agents.closing.nodes import node_init, node_converse

@pytest.fixture
def mock_prospect():
    return ProspectProfile(
        id="test-123",
        name="John Doe",
        email="john@example.com",
        phone="+12025551234",
        whatsapp_id="whatsapp:+12025551234",
        segment="mid_market",
        pain_points=["sales automation"],
        budget_range="$5k-$10k",
        qualification_score=0.75,
        created_at=datetime.now()
    )

@pytest.fixture
def mock_state(mock_prospect):
    return ClosingState(prospect=mock_prospect)

@pytest.mark.asyncio
async def test_node_init_creates_opening_message(mock_state):
    """Test that INIT node generates and sends opening message"""

    # Mock dependencies
    llm = AsyncMock()
    llm.generate.return_value = ("Check this out...", 150)

    rag = AsyncMock()
    rag.search.return_value = [{"video_id": "vid-1", "snippet": "test"}]

    message_queue = AsyncMock()
    message_queue.send.return_value = True

    db = AsyncMock()

    # Run node
    result = await node_init(mock_state, llm, rag, message_queue, db)

    # Assertions
    assert result.stage == "opening_sent"
    assert len(result.messages) == 1
    assert result.messages[0].role == "assistant"
    assert llm.generate.called
    assert message_queue.send.called

@pytest.mark.asyncio
async def test_node_converse_detects_objection(mock_state):
    """Test that CONVERSE detects price objection"""

    # Add prospect message
    mock_state.messages.append(Message(
        role="user",
        content="That's way too expensive for us right now",
        timestamp=datetime.now()
    ))

    # Mock dependencies
    llm = AsyncMock()
    llm.classify.return_value = ("objection", 50)
    llm.extract_objection.return_value = {
        "type": "price",
        "severity": 0.8
    }

    rag = AsyncMock()
    message_queue = AsyncMock()
    db = AsyncMock()

    # Run node
    result = await node_converse(mock_state, llm, rag, message_queue, db)

    # Assertions
    assert result.stage == "objection_detected"
    assert len(result.detected_objections) == 1
    assert result.detected_objections[0].type == "price"
    assert result.detected_objections[0].severity == 0.8
```

---

## Phase 5: Production Deployment

**File**: `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml uv.lock ./

# Install Python dependencies via uv
RUN pip install uv && uv pip install -e .

# Copy source
COPY agents agents/
COPY database database/
COPY api api/
COPY config config/

# Run FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**File**: `api/main.py`

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

app = FastAPI(title="MEGA QUIXAI - Agent CLOSING")

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Routes
from api.routes import closing, webhooks, metrics

app.include_router(closing.router, prefix="/api/closing", tags=["closing"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Configuration Files

**File**: `config/segment_rules.json`

```json
{
  "high_value": {
    "positioning": "Enterprise solution with dedicated support",
    "base_price": 199,
    "price_range": "$150-250",
    "objection_triggers": ["ROI", "integration", "support"],
    "tone": "professional, consultative",
    "top_3_objections": ["price", "trust", "timing"]
  },
  "mid_market": {
    "positioning": "Affordable growth accelerator",
    "base_price": 99,
    "price_range": "$75-125",
    "objection_triggers": ["budget", "ease of use", "results"],
    "tone": "friendly, practical",
    "top_3_objections": ["timing", "price", "urgency"]
  },
  "startup": {
    "positioning": "Bootstrap-friendly tool",
    "base_price": 49,
    "price_range": "$35-65",
    "objection_triggers": ["cash flow", "simplicity", "trial"],
    "tone": "energetic, supportive",
    "top_3_objections": ["price", "trust", "timing"]
  }
}
```

**File**: `config/prompt_templates.json`

```json
{
  "opening_message_high_value": "Hey {name},\n\nI saw your background in {pain_point}. Most {segment} struggle with [specific challenge].\n\nWe recently helped {similar_case} by [result]. Curious if we could do the same?\n\nNo pressure—just exploring possibilities.",

  "opening_message_mid_market": "Hi {name},\n\nQuick question: Is {pain_point} still your biggest bottleneck?\n\nAsking because we just launched something getting great results with teams like yours. Happy to show you in 15 mins if interested.",

  "opening_message_startup": "{name},\n\nYour {pain_point} setup caught my attention. Think we could help, but want to understand your situation first.\n\nOpen to a quick chat?",

  "conversation_response": "Thanks for that context, {name}.\n\nSounds like {pain_point} is affecting [specific impact]. That's exactly what we solve for {segment}.\n\nTwo questions:\n1. [Clarifying Q1]\n2. [Clarifying Q2]\n\nThis'll help me show you the best fit.",

  "objection_counter_price": "I get it—{name}, most people think about cost upfront.\n\nHere's what we usually see:\n• Without [solution], you're spending ~${estimate}/month on [inefficiency]\n• Our package costs ${price}, pays for itself in {months} months\n• Plus: recover {pct}% of your time for other priorities\n\nThat's the ROI that got {case} to say yes.\n\nWant to see the numbers for your situation?"
}
```

---

## Monitoring & Alerts

**File**: `api/middleware.py`

```python
import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)

async def log_requests(request: Request, call_next):
    """Log all API requests"""
    start = time.time()

    response = await call_next(request)

    duration = time.time() - start
    logger.info(f"Request completed", extra={
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": int(duration * 1000)
    })

    # Alert if slow
    if duration > 5.0:
        logger.warning(f"Slow request detected", extra={
            "path": request.url.path,
            "duration_ms": int(duration * 1000)
        })

    return response

# Monitor cost per day
async def cost_monitor():
    """Daily cost tracking"""
    daily_cost = await db.query("""
        SELECT SUM(llm_cost_usd) as total
        FROM closing_metrics
        WHERE created_at > NOW() - INTERVAL '1 day'
    """)

    if daily_cost[0]["total"] > 100:  # Alert if > $100/day
        logger.warning(f"Daily cost exceeded threshold", extra={
            "daily_cost": daily_cost[0]["total"],
            "threshold": 100
        })
```

---

## Success Checklist

- [ ] State machine compiles and runs
- [ ] All 5 nodes execute without errors
- [ ] RAG search works (pgvector)
- [ ] WhatsApp integration sends messages
- [ ] Stripe webhook receives payments
- [ ] Metrics dashboard updates in real-time
- [ ] Unit tests: 80%+ coverage
- [ ] Integration tests: E2E flow successful
- [ ] Load test: 1000 concurrent prospects
- [ ] Cost tracking < $0.30 per lead
- [ ] Production deployment successful
- [ ] Monitoring alerts configured

---

**Next**: Begin Phase 1 implementation.

