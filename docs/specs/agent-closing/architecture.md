# Architecture Détaillée : Agent CLOSING
## MEGA QUIXAI — Agent #2 (Autonomous Sales Closing)

**Version**: 1.0
**Date**: 2026-03-14
**Status**: Architecture Design Complete (Ready for Implementation)
**Budget Estimé**: 2000-4000$ de crédits API (3 agents × 6-12 mois)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [LangGraph State Machine](#langgraph-state-machine)
4. [Component Architecture](#component-architecture)
5. [Tools & Integrations](#tools--integrations)
6. [Closing Scripts & Objection Handling](#closing-scripts--objection-handling)
7. [Relance & Follow-up Pipeline](#relance--follow-up-pipeline)
8. [Payment Integration](#payment-integration)
9. [Metrics & Success Measurement](#metrics--success-measurement)
10. [Risk Analysis & Mitigation](#risk-analysis--mitigation)
11. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

The **Agent CLOSING** is a LangGraph-based autonomous agent that:
- Takes qualified leads from Agent Séduction (↑ ~50% qualification rate)
- Conducts sales conversations via DM/WhatsApp/Email
- Handles objections using RAG-backed arguments from YouTube training content
- Proposes adaptive pricing offers based on prospect profile
- Automates follow-ups with optimal timing
- Measures conversion rate, revenue per lead, and objection success rates
- Integrates with Stripe for one-click checkout

### Key Metrics (Target)
| Metric | Target | Logic |
|--------|--------|-------|
| **Conversation Start Rate** | 85% | Leads that respond to first message |
| **Objection Handling Success** | 70% | Prospects convinced to continue after objection |
| **Conversion Rate** | 35-40% | Qualified leads → paid customers |
| **Revenue Per Lead** | $45-80 | Average offer value |
| **Relance ROI** | 15% | Follow-ups that re-engage inactive leads |
| **Cost Per Acquisition** | $5-12 | API credits burned per customer |

### Budget Breakdown
- **Base Cost**: 3000-4000$ API credits / 12 months
- **Per Lead**: ~$0.20-0.30 (1-3 LLM calls)
- **Volume**: 10-20 qualified leads/day = 3000-6000/month
- **Payback**: If $50 avg revenue × 35% conversion = $17.50/lead → profitable at scale

---

## Architecture Overview

### System Context Diagram
```
┌──────────────────────────────────────────────────────────────────┐
│                    MEGA QUIXAI SYSTEM                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Agent SÉDUCTION               Agent CLOSING         Agent FOLLOW │
│  (Qualification)              (Sales Conversion)    (Retention)   │
│  ┌────────────────┐          ┌──────────────────┐  ┌──────────┐  │
│  │ Leads Gen      │─Qualified→│ Conversation Mgr  │  │ Onboard  │  │
│  │ Profile Scan   │           │ Objection Handler │→ │ Upsell   │  │
│  │ DM Draft       │           │ Offer Proposer    │  │ Winback  │  │
│  └────────────────┘          │ Checkout Integr.  │  └──────────┘  │
│         ↓                     │ Analytics         │        ↑       │
│    YouTube RAG                └──────────────────┘        │        │
│    (Training Content)                ↓                    │        │
│                              Stripe / Payment Gateway    │        │
│                                      ↓                    │        │
│                              CRM Database (PostgreSQL)─────┘        │
│                                      ↓                             │
│                              Metrics & Feedback Loop              │
└──────────────────────────────────────────────────────────────────┘
```

### High-Level Data Flow
```
Qualified Lead (from Agent SÉDUCTION)
    ↓
    └─→ [1. INIT] Load prospect profile, retrieve segment rules
        ↓
    └─→ [2. OPEN] Send opening message (personalized via Langsmith)
        ↓ [No response after 48h? → Relance Pipeline]
    └─→ [3. CONVERSE] LLM conversation (multi-turn, RAG-backed)
        ↓
    ├─→ [4a. OBJECTION] Detected? → RAG lookup + Counter-argument
    │   ↓
    │   └─→ Objection Resolved? → OFFER
    │   └─→ Objection Not Resolved? → RELANCE
    │
    └─→ [4b. OFFER] Present price + payment link
        ↓
        ├─→ [5a. PAYMENT] Stripe checkout → Conversion!
        │   ↓
        │   └─→ Log to CRM, trigger Agent FOLLOW
        │
        └─→ [5b. DECLINED] Rejected offer? → RELANCE or ARCHIVE

```

### Component Stack
```
LangGraph                  LangChain              Integration Layer
├─ State Machine           ├─ LLM Calls           ├─ YouTube RAG (Vector Search)
├─ Nodes (5 main)          ├─ Prompt Templates    ├─ Stripe API (Checkout)
├─ Edges (Conditions)      ├─ Tools Integration   ├─ WhatsApp / Email API
└─ Checkpointing           └─ Memory             ├─ PostgreSQL (CRM)
                                                 └─ LangFuse (Observability)
```

---

## LangGraph State Machine

### State Definition
```python
from typing import Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ProspectProfile:
    """Prospect data from Agent SÉDUCTION"""
    id: str
    name: str
    email: str
    phone: str
    whatsapp_id: Optional[str]
    segment: Literal["high_value", "mid_market", "startup"]
    pain_points: list[str]
    budget_range: str
    qualification_score: float  # 0.0-1.0
    first_message_sent_at: Optional[datetime]
    notes: str

@dataclass
class ClosingState:
    """LangGraph state for Agent CLOSING"""
    # Prospect info
    prospect: ProspectProfile

    # Conversation history
    messages: list[dict] = field(default_factory=list)  # [{role, content, timestamp}]

    # Current stage
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
        "relanced"
    ] = "init"

    # Objection tracking
    detected_objections: list[dict] = field(default_factory=list)
    # [{type: str, text: str, severity: float, resolved: bool, counter_arg: str}]

    # Offer details
    proposed_offer: Optional[dict] = None  # {price, items, stripe_link, expires_at}

    # RAG context
    relevant_content: list[dict] = field(default_factory=list)
    # [{video_id, timestamp, snippet, relevance_score}]

    # Metrics
    conversation_turns: int = 0
    api_calls_count: int = 0
    total_tokens_used: int = 0
    rag_searches: int = 0

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

### Node Definitions (5 Main Nodes)

#### Node 1: INIT
```
Purpose: Load prospect profile, validate data, prepare opening message
Inputs: Qualified lead from Agent SÉDUCTION
Outputs: Updated state with opening message queued

Tasks:
  1. Fetch prospect profile from CRM (PostgreSQL)
  2. Determine segment-specific rules (pricing, positioning)
  3. Retrieve top 3 relevant RAG videos for this segment
  4. Generate personalized opening message
  5. Queue message for sending
  6. Transition: opening_sent

Conditions:
  - Valid prospect data → OPENING_SENT
  - Invalid data → ERROR (log, escalate)
```

**Code Skeleton**:
```python
async def node_init(state: ClosingState) -> ClosingState:
    # 1. Fetch from CRM
    prospect = await db.get_prospect(state.prospect.id)

    # 2. Get segment rules
    rules = SEGMENT_RULES[prospect.segment]

    # 3. RAG lookup for context
    context_videos = await rag_search(
        f"solution for {prospect.pain_points[0]}",
        top_k=3
    )
    state.relevant_content = context_videos

    # 4. Generate opening
    opening_msg = await llm.generate(
        template="opening_messages",
        variables={
            "name": prospect.name,
            "pain_point": prospect.pain_points[0],
            "segment": prospect.segment
        }
    )

    # 5. Queue
    await message_queue.send(
        prospect.whatsapp_id,
        opening_msg,
        metadata={"agent": "closing", "stage": "opening"}
    )

    state.stage = "opening_sent"
    state.messages.append({
        "role": "assistant",
        "content": opening_msg,
        "timestamp": datetime.now(),
        "source": "INIT_node"
    })

    return state
```

#### Node 2: LISTEN_RESPONSE
```
Purpose: Wait for prospect response, detect if no response (relance)
Timeout: 48 hours
Inputs: Opening message sent
Outputs: Either prospect reply or escalate to relance

Tasks:
  1. Poll message queue for responses
  2. If response received:
     - Add to conversation history
     - Transition: CONVERSING
  3. If no response after 48h:
     - Transition: RELANCE (schedule first follow-up)

Conditions:
  - Response received → CONVERSING
  - Timeout (48h) → RELANCE
```

#### Node 3: CONVERSE
```
Purpose: Multi-turn conversation, detect objections, guide toward offer
Inputs: Prospect message
Outputs: Agent response + objection detection

Tasks:
  1. Add prospect message to history
  2. LLM analysis: Classify message type
     - Positive interest?
     - Asking questions?
     - Objection detected?
  3. If objection → OBJECTION_HANDLING
  4. If neutral/positive → Generate conversational response
  5. If ready-for-offer signal → OFFER_PRESENTED

Conditions:
  - Objection detected → OBJECTION_HANDLING
  - Engagement signals → CONVERSE (loop)
  - Ready for offer → OFFER_PRESENTED
  - No response after N hours → RELANCE
```

**Code Skeleton**:
```python
async def node_converse(state: ClosingState) -> ClosingState:
    # Add prospect message
    prospect_msg = state.messages[-1]  # Latest message

    # 1. Classify message intent
    classification = await llm.classify(
        prospect_msg["content"],
        categories=["positive", "question", "objection", "disinterest"]
    )

    # 2. If objection, don't respond yet
    if classification == "objection":
        objection = await llm.extract_objection(prospect_msg["content"])
        state.detected_objections.append({
            "type": objection["type"],  # price, timing, trust, urgency
            "text": objection["text"],
            "severity": objection.get("severity", 0.5),
            "resolved": False
        })
        state.stage = "objection_detected"
        return state

    # 3. Generate response
    response = await llm.generate(
        template="conversation_response",
        variables={
            "prospect_name": state.prospect.name,
            "last_message": prospect_msg["content"],
            "segment": state.prospect.segment,
            "pain_points": state.prospect.pain_points
        }
    )

    state.messages.append({
        "role": "assistant",
        "content": response,
        "timestamp": datetime.now(),
        "source": "CONVERSE_node"
    })
    state.conversation_turns += 1

    # 4. Check if ready for offer (heuristic or explicit signal)
    if "ready to see pricing" in response.lower() or \
       state.conversation_turns >= 3:
        state.stage = "offer_presented"
    else:
        state.stage = "conversing"

    return state
```

#### Node 4: OBJECTION_HANDLING
```
Purpose: Counter objections using RAG + LLM reasoning
Inputs: Detected objection + conversation history
Outputs: Counter-argument message + objection resolution status

Tasks:
  1. Classify objection type (price, timing, trust, urgency)
  2. RAG search for relevant counter-argument content
     - Query: "how to overcome {objection_type}"
  3. LLM generates personalized response
  4. Send counter-argument
  5. Monitor if resolved:
     - If prospect accepts → resume CONVERSE
     - If prospect persists → escalate or RELANCE

Conditions:
  - Objection resolved → CONVERSE
  - Objection persists → RELANCE
  - Multiple objections → DECLINED
```

**Code Skeleton**:
```python
async def node_objection_handling(state: ClosingState) -> ClosingState:
    # Get latest unresolved objection
    objection = [o for o in state.detected_objections if not o["resolved"]][-1]

    # 1. RAG search for counter-arguments
    rag_results = await rag_search(
        f"overcome {objection['type']} objection {state.prospect.segment}",
        top_k=5
    )
    state.relevant_content.extend(rag_results)

    # 2. Build context for LLM
    context = "\n".join([
        f"Video: {r['video_title']}\nSnippet: {r['snippet']}\nTime: {r['timestamp']}"
        for r in rag_results[:3]
    ])

    # 3. Generate counter-argument
    counter = await llm.generate(
        template="objection_counter",
        variables={
            "objection_type": objection["type"],
            "objection_text": objection["text"],
            "segment": state.prospect.segment,
            "rag_context": context
        }
    )

    state.messages.append({
        "role": "assistant",
        "content": counter,
        "timestamp": datetime.now(),
        "source": "OBJECTION_HANDLING_node"
    })

    objection["counter_arg"] = counter
    state.stage = "objection_handling"

    return state
```

#### Node 5: OFFER_PRESENTED
```
Purpose: Present pricing + create Stripe checkout link
Inputs: Prospect ready to hear offer
Outputs: Payment link + tracking

Tasks:
  1. Calculate offer based on segment + custom rules
  2. Create Stripe checkout session
  3. Generate personalized offer message
  4. Send offer + payment link
  5. Start payment monitoring

Conditions:
  - Payment completed → CONVERTED
  - Payment declined → Relance or DECLINED
  - No action after 24h → Relance
```

**Code Skeleton**:
```python
async def node_offer_presented(state: ClosingState) -> ClosingState:
    # 1. Calculate offer
    price = calculate_offer_price(
        segment=state.prospect.segment,
        qualification_score=state.prospect.qualification_score,
        objections_count=len(state.detected_objections)
    )

    # 2. Create Stripe checkout
    checkout = await stripe_client.create_checkout_session(
        customer_email=state.prospect.email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"Package - {state.prospect.segment}"},
                    "unit_amount": int(price * 100)  # cents
                },
                "quantity": 1
            }
        ],
        success_url=f"https://yourdomain.com/success?lead_id={state.prospect.id}",
        cancel_url=f"https://yourdomain.com/cancelled?lead_id={state.prospect.id}",
        expires_in=86400  # 24 hours
    )

    state.proposed_offer = {
        "price": price,
        "stripe_session_id": checkout.id,
        "stripe_url": checkout.url,
        "expires_at": datetime.now() + timedelta(hours=24)
    }

    # 3. Generate message
    offer_msg = await llm.generate(
        template="offer_message",
        variables={
            "prospect_name": state.prospect.name,
            "price": price,
            "items": f"Premium package for {state.prospect.segment}",
            "segment": state.prospect.segment
        }
    )

    offer_msg_with_link = f"{offer_msg}\n\n[Click to pay →](${state.proposed_offer['stripe_url']})"

    # 4. Send
    await message_queue.send(
        state.prospect.whatsapp_id,
        offer_msg_with_link,
        metadata={"agent": "closing", "stage": "offer", "stripe_id": checkout.id}
    )

    state.messages.append({
        "role": "assistant",
        "content": offer_msg_with_link,
        "timestamp": datetime.now(),
        "source": "OFFER_PRESENTED_node"
    })

    state.stage = "payment_pending"

    # 5. Start monitoring
    asyncio.create_task(monitor_stripe_payment(state))

    return state
```

### State Machine Graph

```
                    ┌──────────┐
                    │  START   │
                    └─────┬────┘
                          │
                          ↓
                    ┌──────────────┐
                    │  INIT        │
                    │ Load profile │
                    └─────┬────────┘
                          │
                          ↓
                    ┌──────────────────┐
                    │  OPENING_SENT    │
                    │ Queue message    │
                    └─────┬────────────┘
                          │
                          ↓
        ┌─────────────┬────────────────┬──────────────┐
        │  48h timeout?                │               │
        │  No response → RELANCE       │               │
        │                              │               │
        │ [else: response received]    │               │
        │                              │               │
        └──────────────┬───────────────┘               │
                       │                               │
                       ↓                               │
                ┌──────────────┐                       │
                │  CONVERSING  │                       │
                │ Multi-turn   │                       │
                └──┬─────────┬─┘                       │
                   │         │                         │
        ┌──────────┴┐        └────────────┐            │
        │ Objection │                     │            │
        │ detected? │                     │ Ready for  │
        │           │                     │ offer?     │
        └─────┬─────┘                     │            │
              │ YES                       │ YES        │
              ↓                           │            │
        ┌──────────────┐                  │            │
        │  OBJECTION   │                  │            │
        │  HANDLING    │                  │            │
        └──┬─────────┬─┘                  │            │
           │         │                    │            │
        ┌──┴─┐    ┌──┴──┐                 │            │
        │    │    │     │                 │            │
        │    ↓    │     │                 │            │
        │ Resolved? RELANCE               │            │
        │    │         │                  │            │
        │ YES│         │                  │            │
        │    │         │                  │            │
        └────┼─────────┼──────────────────┘            │
             │         │                               │
             ↓         │                               ↓
        ┌─────────────┐│                    ┌──────────────────┐
        │  CONVERSE   ││                    │ OFFER_PRESENTED  │
        │  (continue) ││                    │ Stripe link      │
        └──┬──────────┘│                    └─────┬────────────┘
           │ │         │                         │ │
           │ └─────────┼─────────────────────────┘ │
           │           │                           │
           │           └───────────────────────────┤
           │                                       │
           └────────────────┬──────────────────────┴──────┐
                            │                             │
                    ┌───────┴────────────┐                │
                    │ 24h timeout        │                │
                    │ or declined?       │                │
                    │                    │                │
                    │ [else: payment ok]↓
                    │         ┌──────────────────┐
                    ├────────→│  CONVERTED       │
                    │         │  Log transaction │
                    │         └──────────────────┘
                    │
                    └─→ RELANCE (if declined or no action)


Legend:
  INIT              = Load prospect, prepare opening
  OPENING_SENT      = Message queued
  CONVERSING        = Multi-turn conversation
  OBJECTION_HANDLING= Counter-argument RAG
  OFFER_PRESENTED   = Send pricing + Stripe link
  CONVERTED         = Payment successful
  RELANCE           = Follow-up pipeline
```

### Edge Conditions (Decision Logic)

```python
# Edge 1: Init → Opening_Sent
Condition: prospect data valid
Action: send opening message

# Edge 2: Opening_Sent → Conversing
Condition: response received within 48h
Action: add to conversation history

# Edge 3: Opening_Sent → Relance
Condition: no response after 48h
Action: trigger first follow-up

# Edge 4: Conversing → Objection_Handling
Condition: LLM classification = "objection"
Action: extract objection details

# Edge 5: Conversing → Offer_Presented
Condition: conversation_turns >= 3 OR explicit signal
Action: calculate price, create Stripe session

# Edge 6: Objection_Handling → Conversing
Condition: objection resolved = True
Action: continue conversation

# Edge 7: Objection_Handling → Relance
Condition: prospect persists on objection OR silent
Action: schedule follow-up

# Edge 8: Offer_Presented → Converted
Condition: Stripe webhook confirms payment
Action: log to CRM, trigger Agent FOLLOW

# Edge 9: Offer_Presented → Relance
Condition: no payment after 24h OR payment declined
Action: schedule second follow-up
```

---

## Component Architecture

### 1. Core LangGraph Orchestrator
**File**: `closing_agent.py`
**Responsibility**: State machine logic, node execution, edge routing

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres import PostgresSaver

# Initialize graph
graph_builder = StateGraph(ClosingState)

# Add nodes
graph_builder.add_node("init", node_init)
graph_builder.add_node("listen_response", node_listen_response)
graph_builder.add_node("converse", node_converse)
graph_builder.add_node("objection_handling", node_objection_handling)
graph_builder.add_node("offer_presented", node_offer_presented)

# Add edges with conditions
graph_builder.add_edge("init", "opening_sent")
graph_builder.add_conditional_edges(
    "listen_response",
    lambda state: "conversing" if state.messages else "relance",
    {
        "conversing": "converse",
        "relance": "relance"
    }
)

# ... more edges

# Compile with checkpointing (for recovery)
graph = graph_builder.compile(checkpointer=PostgresSaver(conn_string))

# Run
async def run_closing_agent(lead: ProspectProfile) -> ClosingState:
    state = ClosingState(prospect=lead)
    result = await graph.ainvoke(
        state,
        config={"configurable": {"thread_id": lead.id}}
    )
    return result
```

### 2. LLM Interface Layer
**File**: `llm_interface.py`
**Responsibility**: Claude API calls, prompt management, token tracking

```python
from anthropic import AsyncAnthropic
from langsmith import traceable

class LLMInterface:
    def __init__(self, model: str = "claude-opus-4"):
        self.client = AsyncAnthropic()
        self.model = model

    @traceable(run_type="llm")
    async def generate(self, template: str, variables: dict) -> str:
        """Generate text using Claude"""
        prompt = PROMPT_TEMPLATES[template].format(**variables)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    @traceable(run_type="llm")
    async def classify(self, text: str, categories: list[str]) -> str:
        """Classify text into categories"""
        prompt = f"""Classify this text into one of: {', '.join(categories)}.

Text: {text}

Classification:"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip().lower()
```

### 3. RAG Integration
**File**: `rag_interface.py`
**Responsibility**: Vector search against YouTube transcriptions

```python
import pgvector
from pgvector.psycopg import register_vector

class RAGInterface:
    def __init__(self, db_url: str):
        self.pool = asyncpg.create_pool(db_url)
        register_vector(self.pool)

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search YouTube transcriptions by semantic similarity"""

        # 1. Generate embedding for query
        embedding = await embed_text(query)

        # 2. Vector search in pgvector
        results = await self.pool.fetch("""
            SELECT
                v.id, v.video_id, v.title, v.playlist,
                v.content, v.timestamp,
                1 - (embeddings <-> $1) as similarity
            FROM video_chunks v
            ORDER BY embeddings <-> $1
            LIMIT $2
        """, embedding, top_k)

        return [
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "snippet": r["content"][:200],
                "timestamp": r["timestamp"],
                "relevance_score": r["similarity"]
            }
            for r in results
        ]
```

### 4. Message Queue Manager
**File**: `message_queue.py`
**Responsibility**: Send/receive messages (WhatsApp, Email, Telegram)

```python
from twilio.rest import Client as TwilioClient

class MessageQueueManager:
    def __init__(self, whatsapp_token: str, email_provider: str):
        self.twilio = TwilioClient(account_sid, auth_token)
        self.email_provider = EmailProvider(email_provider)

    async def send(self, contact_id: str, message: str, metadata: dict):
        """Send message to prospect"""

        # Determine channel (WhatsApp preferred, fallback to Email)
        if contact_id.startswith("whatsapp:"):
            await self._send_whatsapp(contact_id, message, metadata)
        else:
            await self._send_email(contact_id, message, metadata)

        # Log in database
        await db.insert_message({
            "contact_id": contact_id,
            "message": message,
            "direction": "outbound",
            "metadata": metadata,
            "sent_at": datetime.now()
        })

    async def listen(self, callback_data: dict) -> Optional[str]:
        """Inbound webhook callback (Twilio, etc.)"""
        return callback_data.get("message_body")
```

### 5. Stripe Payment Integration
**File**: `payment_integration.py`
**Responsibility**: Checkout creation, webhook handling

```python
import stripe

class PaymentManager:
    def __init__(self, stripe_key: str):
        stripe.api_key = stripe_key

    async def create_checkout(self, prospect_id: str, amount: float) -> str:
        """Create Stripe checkout session"""

        session = stripe.checkout.Session.create(
            customer_email=prospect.email,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Service Package - {prospect.segment}",
                        "images": ["https://...logo.png"]
                    },
                    "unit_amount": int(amount * 100)
                },
                "quantity": 1
            }],
            mode="payment",
            success_url=f"https://yourdomain.com/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"https://yourdomain.com/cancelled?prospect_id={prospect_id}",
            expires_in=86400
        )

        return session.url

    async def verify_payment(self, session_id: str) -> bool:
        """Verify payment via webhook"""
        session = stripe.checkout.Session.retrieve(session_id)
        return session.payment_status == "paid"
```

### 6. CRM Database
**File**: `crm_db.py`
**Responsibility**: Prospect tracking, conversation history, metrics

```sql
-- Table: prospects
CREATE TABLE prospects (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    whatsapp_id VARCHAR(50),
    name VARCHAR(255),
    segment VARCHAR(50),
    pain_points TEXT[],
    qualification_score FLOAT,
    status VARCHAR(50),  -- qualified, conversing, converted, declined
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSONB
);

-- Table: conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    prospect_id UUID REFERENCES prospects(id),
    messages JSONB,  -- [{role, content, timestamp}]
    stage VARCHAR(50),
    objections JSONB,
    proposed_offer JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Table: metrics
CREATE TABLE closing_metrics (
    id UUID PRIMARY KEY,
    prospect_id UUID REFERENCES prospects(id),
    conversation_turns INT,
    api_calls INT,
    total_tokens INT,
    rag_searches INT,
    objections_count INT,
    conversion_achieved BOOLEAN,
    final_amount FLOAT,
    stripe_id VARCHAR(255),
    created_at TIMESTAMP
);
```

### 7. Analytics & Observability
**File**: `analytics.py`
**Responsibility**: Real-time metrics, LangFuse integration

```python
from langfuse import Langfuse

class Analytics:
    def __init__(self):
        self.langfuse = Langfuse()

    async def track_conversion(self, state: ClosingState):
        """Log successful conversion"""
        await db.insert_metric({
            "prospect_id": state.prospect.id,
            "conversion_achieved": True,
            "final_amount": state.final_amount,
            "stripe_id": state.stripe_payment_id,
            "conversation_turns": state.conversation_turns,
            "api_calls": state.api_calls_count,
            "objections_handled": len([o for o in state.detected_objections if o["resolved"]]),
            "rag_searches": state.rag_searches
        })

        self.langfuse.flush()

    async def get_dashboard_data(self) -> dict:
        """Aggregate metrics for dashboard"""
        return await db.query("""
            SELECT
                COUNT(*) as total_leads,
                COUNT(CASE WHEN conversion_achieved THEN 1 END) as conversions,
                COUNT(CASE WHEN conversion_achieved THEN 1 END)::FLOAT /
                    COUNT(*) * 100 as conversion_rate,
                AVG(final_amount) as avg_revenue,
                AVG(conversation_turns) as avg_turns,
                AVG(total_tokens) as avg_tokens
            FROM closing_metrics
            WHERE created_at > NOW() - INTERVAL '30 days'
        """)
```

---

## Tools & Integrations

### Tool #1: RAG Content Lookup
**Purpose**: Find counter-arguments for objections
**API**: pgvector semantic search
**Cost**: Minimal (already indexed)

```python
@tool
async def lookup_objection_content(
    objection_type: str,
    segment: str,
    max_results: int = 5
) -> list[str]:
    """
    Lookup RAG content for overcoming objections.

    Args:
        objection_type: "price" | "timing" | "trust" | "urgency"
        segment: "high_value" | "mid_market" | "startup"
        max_results: Number of video chunks to return

    Returns:
        List of relevant content snippets with timestamps
    """
    query = f"How to overcome {objection_type} objection for {segment}"
    results = await rag.search(query, top_k=max_results)
    return results
```

### Tool #2: Generate Personalized Offer
**Purpose**: Calculate dynamic pricing
**API**: Internal pricing engine
**Cost**: Free (logic only)

```python
@tool
async def generate_offer(
    prospect_id: str,
    segment: str,
    qualification_score: float,
    objections_count: int
) -> dict:
    """
    Generate personalized offer based on prospect profile.

    Logic:
      - Base price by segment
      - Discount for high qualification (%)
      - Slight discount if objections overcome (%)

    Returns:
        {price, offer_description, expiry_hours}
    """
    base_prices = {
        "high_value": 199,
        "mid_market": 99,
        "startup": 49
    }

    price = base_prices[segment]

    # Qualification discount (10% per 0.1 points above 0.5)
    qual_discount = max(0, (qualification_score - 0.5) * 0.1)

    # Objection overcome bonus (5% per objection)
    objection_discount = objections_count * 0.05

    final_price = price * (1 - qual_discount - objection_discount)

    return {
        "price": round(final_price, 2),
        "description": f"Premium Package for {segment}",
        "expiry_hours": 24,
        "base_price": price
    }
```

### Tool #3: Stripe Checkout Integration
**Purpose**: Create payment links
**API**: Stripe API
**Cost**: 2.9% + $0.30 per transaction

```python
@tool
async def create_payment_link(
    prospect_id: str,
    amount: float,
    currency: str = "usd"
) -> str:
    """
    Create Stripe checkout link.

    Args:
        prospect_id: Unique ID
        amount: Price in USD
        currency: "usd" | "eur" | etc.

    Returns:
        Stripe checkout URL
    """
    prospect = await db.get_prospect(prospect_id)

    url = await payment_manager.create_checkout(prospect, amount)

    await db.update_prospect(prospect_id, {
        "payment_link_created_at": datetime.now(),
        "payment_link_expires_at": datetime.now() + timedelta(hours=24)
    })

    return url
```

### Tool #4: Schedule Follow-up
**Purpose**: Queue relance messages
**API**: Internal task scheduler
**Cost**: Free

```python
@tool
async def schedule_followup(
    prospect_id: str,
    delay_hours: int,
    reason: str
) -> bool:
    """
    Schedule automatic follow-up message.

    Args:
        prospect_id: Who to follow up
        delay_hours: When (24, 72, etc.)
        reason: "no_response" | "objection_persist" | "payment_declined"

    Returns:
        True if scheduled successfully
    """
    task = {
        "prospect_id": prospect_id,
        "type": "followup",
        "reason": reason,
        "scheduled_for": datetime.now() + timedelta(hours=delay_hours),
        "created_at": datetime.now()
    }

    await scheduler.enqueue(task)

    return True
```

### Tool #5: Prospect Segmentation Analysis
**Purpose**: Determine best approach per segment
**API**: Internal rules engine
**Cost**: Free

```python
@tool
async def analyze_prospect_segment(prospect_id: str) -> dict:
    """
    Analyze prospect segment and return tailored strategy.

    Returns:
        {segment, positioning, price_range, objection_triggers, messaging_tone}
    """
    prospect = await db.get_prospect(prospect_id)

    rules = SEGMENT_RULES[prospect.segment]

    return {
        "segment": prospect.segment,
        "positioning": rules["positioning"],
        "price_range": rules["price_range"],
        "objection_triggers": rules["likely_objections"],
        "messaging_tone": rules["tone"],
        "expected_objections": rules["top_3_objections"]
    }
```

---

## Closing Scripts & Objection Handling

### Opening Messages (Segment-Specific)

#### High-Value Segment
```
Hey {name},

I saw your background in [pain_point]. Honestly, most [segment] struggle with the exact same thing.

We recently helped {similar_case} reduce [metric] by 40% in 3 weeks. Curious if we could do the same for you?

No pressure either way — just want to show you what's possible.
```

#### Mid-Market Segment
```
Hi {name},

Quick question: Is [pain_point] still your biggest bottleneck right now?

Asking because we just launched something that's been getting great results with teams like yours. Happy to show you in 15 mins if you're interested.
```

#### Startup Segment
```
{name},

Your {pain_point} setup caught my attention. I think we have something that could help, but want to understand your situation first.

Are you open to a quick chat?
```

### Objection Handling Scripts

#### Objection: "It's Too Expensive"

**Severity**: HIGH
**Success Rate Target**: 60%
**RAG Query**: "how to handle price objection budget constraints"

**Counter-Argument Template**:
```
I get it — {name}, most people think about cost upfront.

But here's what we usually see:
- Without [solution], you're spending ~${estimate_waste}/month on [inefficiency]
- Our package costs ${price}, which pays for itself in {months} months
- Plus: you recover {X}% of your time/resources for other priorities

That's actually the ROI angle that got {similar_case} to say yes.

Want to see the numbers for your specific situation?
```

**Decision Tree**:
```
Prospect says: "Price is too high"
    ├─→ Response: "I understand. Can I show you the ROI breakdown?"
    │   ├─→ Accepts ROI discussion → Continue
    │   └─→ Still refuses → Move to RELANCE (schedule 3-day follow-up)
    │
    └─→ Prospect says: "Don't have budget right now"
        ├─→ Response: "Makes sense. What timeline would work?"
        │   ├─→ Says "3 months" → "Let me send you a reminder for then"
        │   └─→ Says "Never" → RELANCE (30-day follow-up, probably won't convert)
```

#### Objection: "We're Not Ready / It's Not The Right Time"

**Severity**: MEDIUM
**Success Rate Target**: 50%
**RAG Query**: "timing objection when to implement solution"

**Counter-Argument Template**:
```
That's actually a common one, {name}.

Most teams think "we'll get ready later" but here's what happens:
→ Later becomes 3 months, then 6 months
→ Problems get worse, not better
→ New priorities pile up

What if we start with a 30-day pilot? Low commitment, and you'll see results immediately. If it doesn't work, zero hard feelings.

What's your biggest blocker right now?
```

#### Objection: "I Don't Know If I Trust You / We"

**Severity**: CRITICAL
**Success Rate Target**: 70%
**RAG Query**: "social proof testimonials case studies credibility"

**Counter-Argument Template**:
```
I totally understand the skepticism, {name}. Trust is earned, not given.

Here's what I can offer:
1. Speak to {similar_case} — they did exactly what you're considering
2. 14-day trial with money-back guarantee (no questions asked)
3. I'll personally oversee your setup so it works (not leaving you hanging)

Honestly, we've had {X} clients start exactly where you are. Happy to put you in touch with 2-3 if that helps.

Which would help you feel most confident?
```

#### Objection: "We're Already Using [Competitor]"

**Severity**: MEDIUM
**Success Rate Target**: 40%
**RAG Query**: "competitor comparison differentiation advantages"

**Counter-Argument Template**:
```
Good — that means you already know this space matters.

Actually, a lot of our best clients were [competitor] users first. Here's the difference:
- [Competitor] is great for X, but struggles with Y (where you probably are)
- We built specifically for teams that hit that wall

Not saying [competitor] is bad — just different.

What's the main thing you wish [competitor] did better? That's probably where we're strong.
```

### Objection Resolution Scoring

```python
OBJECTION_RESOLUTION_RULES = {
    "price": {
        "signals_resolved": [
            "OK let me think about it",
            "Send me the details",
            "What if we",
            "Can we do {lower_number}",
            "Sounds reasonable"
        ],
        "signals_persist": [
            "Still too much",
            "I need more time",
            "Don't have the budget",
            "No way",
            "That's crazy"
        ],
        "retry_delay_hours": 72,
        "max_attempts": 2
    },
    "timing": {
        "signals_resolved": [
            "OK when can we start",
            "Let's do it",
            "What does onboarding look like",
            "Let me check my calendar"
        ],
        "signals_persist": [
            "Too early",
            "Maybe next quarter",
            "Not this year",
            "I'll let you know"
        ],
        "retry_delay_hours": 168,  # 7 days
        "max_attempts": 1
    },
    "trust": {
        "signals_resolved": [
            "OK that makes sense",
            "Can you send me that",
            "Looks good",
            "Let me review"
        ],
        "signals_persist": [
            "I'm still not sure",
            "Sounds too good",
            "I need proof",
            "I'll research first"
        ],
        "retry_delay_hours": 240,  # 10 days
        "max_attempts": 2
    }
}
```

---

## Relance & Follow-up Pipeline

### Relance Strategy

**Objective**: Re-engage cold leads with graduated timing
**Budget**: Minimal (mostly template-based messages)

### Relance Rules Matrix

| Scenario | Delay | Template | Max Attempts |
|----------|-------|----------|--------------|
| No response after opening | 24h → 48h | Reminder 1 (gentle) | 1 |
| Conversation stalled | 24h | Gentle reminder | 1 |
| Objection unresolved | 72h | Follow-up + new angle | 2 |
| Offer declined | 48h | Alternative offer | 1 |
| Payment pending (24h+) | 24h | Reminder + help | 1 |

### Relance Message Templates

#### Template 1: No Response After 24h (Gentle)
```
Hey {name} 👋

Just checking in — did my message get lost? Happens all the time!

Only reach out if you're interested. No hard feelings either way :)

```

#### Template 2: Objection Unresolved (New Angle)
```
{name},

I was thinking about what you said about {objection}...

Actually, we have an alternative way to approach this that might work better for your situation. Takes 5 mins to explain.

Worth a quick chat?
```

#### Template 3: Offer Declined (Recovery)
```
No worries, {name}. Not everyone's at the same point.

What if we started smaller? Could do a 30-day test at half price — zero risk.

Interested?
```

#### Template 4: Payment Pending (Gentle Reminder)
```
Hi {name},

Just noticed you haven't completed the checkout yet. No pressure!

Sometimes it gets buried in emails. [Re-send link]

Any questions I can answer?
```

### Relance Automation Engine

**File**: `relance_scheduler.py`

```python
class RelanceScheduler:
    """Automated follow-up orchestration"""

    async def evaluate_lead_for_relance(self, prospect_id: str) -> bool:
        """Determine if lead should be relanced"""
        state = await db.get_conversation(prospect_id)

        # Rules
        rules = {
            "no_response_24h": (
                state.stage == "opening_sent" and
                datetime.now() - state.last_message_sent_at > timedelta(hours=24)
            ),
            "conversation_stalled": (
                state.stage == "conversing" and
                datetime.now() - state.last_message_received_at > timedelta(hours=24)
            ),
            "objection_unresolved": (
                len([o for o in state.detected_objections if not o["resolved"]]) > 0
            ),
            "offer_declined": (
                state.stage == "payment_pending" and
                datetime.now() - state.offer_presented_at > timedelta(hours=24)
            )
        }

        return any(rules.values())

    async def schedule_relance(self, prospect_id: str, reason: str):
        """Queue relance task"""
        delays = {
            "no_response": 24,
            "stalled": 24,
            "objection": 72,
            "declined": 48
        }

        task = {
            "prospect_id": prospect_id,
            "type": "relance",
            "reason": reason,
            "scheduled_for": datetime.now() + timedelta(hours=delays[reason]),
            "template": RELANCE_TEMPLATES[reason],
            "attempt": 1
        }

        await scheduler.enqueue(task)
```

### Cron Agent for Relance

**File**: `cron_relance_agent.py`

```python
# Runs every 1 hour
async def relance_cron():
    """Check all prospects for relance eligibility"""

    prospects_due = await db.query("""
        SELECT id FROM prospects
        WHERE status IN ('conversing', 'objection_detected')
        AND last_message_received_at < NOW() - INTERVAL '24 hours'
        AND relance_count < max_relance_attempts
    """)

    for prospect_id in prospects_due:
        await run_closing_agent(prospect_id)
```

---

## Payment Integration

### Stripe Checkout Flow

```
Agent sends offer with Stripe link
    ↓
Prospect clicks link
    ↓
Stripe checkout page
    ├─→ [SUCCESS] Webhook fires → Update CRM → Trigger Agent FOLLOW
    ├─→ [CANCEL] Webhook fires → Schedule relance (24h)
    └─→ [TIMEOUT] (24h) → Schedule relance reminder
```

### Webhook Handler

**File**: `stripe_webhook_handler.py`

```python
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Stripe event handler"""

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JSONResponse({"error": "Invalid payload"}, status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Extract prospect ID from metadata
        prospect_id = session.get("metadata", {}).get("prospect_id")

        # Update CRM
        await db.update_prospect(prospect_id, {
            "status": "converted",
            "stripe_payment_id": session.id,
            "converted_at": datetime.now(),
            "final_amount": session.amount_total / 100
        })

        # Trigger Agent FOLLOW
        await trigger_agent_follow(prospect_id)

        # Log metrics
        await analytics.track_conversion(prospect_id)

    return JSONResponse({"success": True})
```

---

## Metrics & Success Measurement

### KPI Dashboard

**Real-time metrics** (LangFuse + custom PostgreSQL)

```python
class MetricsDashboard:

    async def get_realtime_metrics(self, days: int = 7) -> dict:
        """Fetch live metrics for dashboard"""

        data = await db.query("""
            SELECT
                -- Volume
                COUNT(DISTINCT prospect_id) as total_leads,
                COUNT(DISTINCT CASE WHEN status='converted' THEN prospect_id END) as conversions,

                -- Rates
                ROUND(100.0 * COUNT(DISTINCT CASE WHEN status='converted' THEN prospect_id END) /
                    COUNT(DISTINCT prospect_id), 2) as conversion_rate_pct,

                ROUND(100.0 * COUNT(DISTINCT CASE WHEN messages IS NOT NULL THEN prospect_id END) /
                    COUNT(DISTINCT prospect_id), 2) as response_rate_pct,

                -- Revenue
                ROUND(AVG(CASE WHEN status='converted' THEN final_amount END), 2) as avg_revenue,
                ROUND(SUM(CASE WHEN status='converted' THEN final_amount END), 2) as total_revenue,

                -- Efficiency
                ROUND(AVG(conversation_turns), 1) as avg_turns_to_offer,
                ROUND(AVG(api_calls), 1) as avg_api_calls,

                -- Objections
                COUNT(DISTINCT CASE WHEN objections_count>0 THEN prospect_id END) as leads_with_objections,
                ROUND(100.0 * COUNT(DISTINCT CASE WHEN objections_resolved THEN prospect_id END) /
                    NULLIF(COUNT(DISTINCT CASE WHEN objections_count>0 THEN prospect_id END), 0), 2)
                    as objection_resolution_rate_pct

            FROM closing_metrics
            WHERE created_at >= NOW() - INTERVAL '{days} days'
        """)

        return {
            "summary": data[0],
            "by_segment": await self._get_by_segment(days),
            "by_objection": await self._get_by_objection(days),
            "api_efficiency": {
                "cost_per_conversion": data[0]["total_revenue"] / (data[0]["conversions"] * 0.25) if data[0]["conversions"] > 0 else None,
                "tokens_per_lead": data[0]["total_tokens"] / data[0]["total_leads"]
            }
        }
```

### Segment-Level Analysis

```sql
SELECT
    segment,
    COUNT(*) as leads,
    COUNT(CASE WHEN status='converted' THEN 1 END) as conversions,
    ROUND(100.0 * COUNT(CASE WHEN status='converted' THEN 1 END) / COUNT(*), 2) as conversion_rate,
    AVG(final_amount) as avg_revenue,
    AVG(conversation_turns) as avg_turns,
    AVG(objections_count) as avg_objections
FROM closing_metrics
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY segment
ORDER BY conversion_rate DESC;
```

### Objection Analysis

```sql
SELECT
    objection_type,
    COUNT(*) as occurrences,
    COUNT(CASE WHEN resolved THEN 1 END) as resolved_count,
    ROUND(100.0 * COUNT(CASE WHEN resolved THEN 1 END) / COUNT(*), 2) as resolution_rate,
    AVG(CASE WHEN resolved THEN 1 ELSE 0 END * 100) as avg_follow_up_time_hours
FROM objections
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY objection_type
ORDER BY occurrences DESC;
```

### Cost & ROI Calculation

```python
async def calculate_roi(period_days: int = 30) -> dict:
    """Calculate true cost per acquisition"""

    metrics = await db.query("""
        SELECT
            SUM(total_tokens) as total_tokens,
            COUNT(*) as total_leads,
            COUNT(CASE WHEN status='converted' THEN 1 END) as conversions,
            SUM(CASE WHEN status='converted' THEN final_amount END) as revenue,
            AVG(api_calls) as avg_calls
        FROM closing_metrics
        WHERE created_at >= NOW() - INTERVAL '{period_days} days'
    """)

    # Pricing assumptions
    cost_per_1k_tokens = 0.003  # Claude API

    total_api_cost = metrics["total_tokens"] / 1000 * cost_per_1k_tokens
    cost_per_lead = total_api_cost / metrics["total_leads"]
    cost_per_conversion = total_api_cost / metrics["conversions"]
    roi = metrics["revenue"] / total_api_cost if total_api_cost > 0 else 0

    return {
        "total_api_cost": round(total_api_cost, 2),
        "cost_per_lead": round(cost_per_lead, 2),
        "cost_per_conversion": round(cost_per_conversion, 2),
        "revenue_generated": round(metrics["revenue"], 2),
        "roi_multiplier": round(roi, 2),
        "net_profit": round(metrics["revenue"] - total_api_cost, 2)
    }
```

### Success Criteria

| Metric | Target | Acceptance |
|--------|--------|-----------|
| **Conversation Start Rate** | 85% | 70%+ |
| **Objection Handling Success** | 70% | 55%+ |
| **Conversion Rate** | 40% | 30%+ |
| **Avg Tokens per Conversion** | <5000 | <8000 |
| **Cost per Conversion** | <$8 | <$15 |
| **Revenue per Lead** | $50+ | $30+ |
| **Relance ROI** | 15%+ | 8%+ |

---

## Risk Analysis & Mitigation

### Risk #1: Low Response Rate to Opening Message

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Opening message ignored** | HIGH (40% no response) | Critical | • A/B test opening templates<br/>• Time messages (9am UTC best)<br/>• Use WhatsApp (90% open vs 15% email)<br/>• Add time-sensitive urgency<br/>• Relance after 24h with variant |
| **Impact**: No conversation starts | | | **Expected Outcome**: 80%+ response rate |

**Action**: Implement A/B testing harness on opening templates.

### Risk #2: Objection Handling Ineffectiveness

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **RAG counter-arguments don't resonate** | MEDIUM (40% persist) | High | • Use human-validated counter-args (not pure LLM)<br/>• A/B test by objection type<br/>• Add social proof (testimonials)<br/>• Monitor success rate per objection<br/>• Switch to manual handling if <50% success |
| **LLM response feels generic** | MEDIUM | High | • Fine-tune prompts on successful closures<br/>• Use examples of successful counters<br/>• Add persona-based tone matching<br/>• Add prospect context to RAG query |

**Action**: Build objection success tracker (which counters work best).

### Risk #3: Payment Abandonment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Stripe checkout abandoned** | MEDIUM (25% drop-off) | High | • Email reminder after 12h<br/>• Show ROI on checkout page<br/>• Offer payment plans (Stripe Billing)<br/>• A/B test success page messaging<br/>• Relance with "need help?" |
| **Payment fails (card error, etc.)** | LOW (2-3%) | Medium | • Automatic retry on failure<br/>• SMS notification + alternative payment<br/>• Manual follow-up for high-value leads |

**Action**: Build post-checkout follow-up sequence.

### Risk #4: API Cost Runaway

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Too many LLM calls per lead** | MEDIUM | High | • Set token budget per prospect<br/>• Use cheaper models for classification<br/>• Cache RAG results<br/>• Implement call throttling<br/>• Monitor cost_per_conversion daily |
| **RAG searches explode** | LOW | Medium | • Limit RAG calls per conversation turn<br/>• Cache embeddings<br/>• Use simpler queries (not multi-step) |

**Action**: Implement cost monitoring dashboard + alerts if cost_per_conversion > $15.

### Risk #5: Stripe Integration Failures

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Webhook timeout/missed payment** | LOW (1-2%) | High | • Verify payment status via polling<br/>• Retry failed webhooks 3x<br/>• Log all webhook events (audit trail)<br/>• Manual reconciliation daily<br/>• Alert on failed payment confirmations |

**Action**: Implement webhook retry logic + daily reconciliation cron.

### Risk #6: Data Privacy & Compliance

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **GDPR violation (data retention)** | MEDIUM | Critical | • Delete conversation data after 90 days<br/>• Anonymize for analytics<br/>• Implement "right to be forgotten"<br/>• Log all data access<br/>• Encrypt PII at rest |
| **Unauthorized access to CRM** | LOW | Critical | • Encrypt API keys (dotenv)<br/>• Implement database-level encryption<br/>• Rate limit API endpoints<br/>• Use PostgreSQL row-level security |

**Action**: Implement data retention policy + encryption.

### Risk #7: State Machine Deadlock

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **Prospect stuck in "conversing"** | LOW (5%) | Medium | • Implement state timeout (7 days)<br/>• Auto-escalate to relance if no progress<br/>• Add dead-letter queue for stuck states<br/>• Monitor state duration distribution |

**Action**: Implement state timeout + escalation rules.

---

## Implementation Roadmap

### Phase 1: Core State Machine (Week 1-2)
**Deliverables**: LangGraph state machine + 5 nodes

- [ ] Define ClosingState dataclass
- [ ] Implement INIT node
- [ ] Implement CONVERSE node
- [ ] Implement OBJECTION_HANDLING node
- [ ] Implement OFFER_PRESENTED node
- [ ] Build state machine graph
- [ ] Test state transitions (unit tests)

**Cost**: 100-200$ API (dev/testing)

### Phase 2: Integration Layer (Week 2-3)
**Deliverables**: RAG, Stripe, WhatsApp, CRM

- [ ] Connect pgvector RAG
- [ ] Stripe checkout integration (create session, verify payment)
- [ ] Twilio WhatsApp integration (send/receive)
- [ ] PostgreSQL CRM schema + queries
- [ ] Message queue manager

**Cost**: 100-300$ API

### Phase 3: Scripts & Templates (Week 3)
**Deliverables**: Opening messages, objection counters, relance templates

- [ ] Write segment-specific opening templates (3)
- [ ] Objection counter templates (4 types × 2-3 variants)
- [ ] Relance templates (5)
- [ ] A/B testing harness

**Cost**: Minimal (just LLM for validation)

### Phase 4: Analytics & Observability (Week 4)
**Deliverables**: LangFuse integration, metrics dashboard, monitoring

- [ ] LangFuse instrumentation
- [ ] Metrics database schema
- [ ] Dashboard SQL queries
- [ ] Cost per conversion tracking
- [ ] Real-time alerts

**Cost**: Free (LangFuse free tier)

### Phase 5: Testing & Optimization (Week 4-5)
**Deliverables**: Unit tests, integration tests, production readiness

- [ ] Unit tests (nodes, tools, edges)
- [ ] Integration tests (E2E flow)
- [ ] Load testing (1000 concurrent prospects)
- [ ] Prompt optimization (highest-impact first)
- [ ] Performance benchmarking

**Cost**: 200-500$ API (testing)

### Phase 6: Deployment & Monitoring (Week 5-6)
**Deliverables**: Production deployment, monitoring, alert setup

- [ ] Docker containerization
- [ ] Deploy to production (AWS/GCP)
- [ ] LangFuse dashboard setup
- [ ] Alert rules (cost, conversion rate, errors)
- [ ] Documentation + runbooks

**Cost**: ~100-200$ API (initial)

---

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Orchestration** | LangGraph | Structured state management, checkpointing, multi-turn |
| **LLM** | Claude Opus 4 | Best reasoning for objection handling |
| **Vector DB** | pgvector (PostgreSQL) | Free, local, already in use for YouTube RAG |
| **Message Channel** | Twilio WhatsApp | 90% open rate, global coverage |
| **Payment** | Stripe | 2.9% + $0.30, international support |
| **CRM** | PostgreSQL | Free, structured, already deployed |
| **Observability** | LangFuse | Free tier sufficient, native LangGraph support |
| **Scheduler** | APScheduler | Cron jobs for relance, polling |
| **API Framework** | FastAPI | Async, lightweight, Stripe webhook support |
| **Containerization** | Docker | Consistent deployment |

---

## Deployment Architecture

```
┌────────────────────────────────────────────────────────┐
│                    PRODUCTION ENVIRONMENT              │
├────────────────────────────────────────────────────────┤
│                                                        │
│  FastAPI Service                                       │
│  ├─ LangGraph state machine                           │
│  ├─ REST endpoints (webhook, status)                  │
│  └─ Stripe webhook handler                            │
│         ↓                                              │
│  PostgreSQL (Primary)                                  │
│  ├─ CRM (prospects, conversations)                    │
│  ├─ Metrics (conversions, api_calls)                  │
│  ├─ Video chunks (RAG)                                │
│  └─ pgvector extension (embeddings)                   │
│         ↓                                              │
│  Redis (Cache)                                         │
│  ├─ Session state (ephemeral)                         │
│  ├─ Rate limiting                                     │
│  └─ Message queue (relance tasks)                     │
│         ↓                                              │
│  External APIs                                         │
│  ├─ Anthropic (Claude)                                │
│  ├─ Stripe                                            │
│  ├─ Twilio WhatsApp                                   │
│  └─ LangFuse (observability)                          │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Conclusion

The **Agent CLOSING** is designed as a highly efficient, data-driven autonomous sales system that:

1. **Orchestrates conversations** via LangGraph state machine
2. **Handles objections intelligently** using RAG-backed counter-arguments
3. **Proposes dynamic pricing** based on prospect segments
4. **Integrates payments seamlessly** with Stripe one-click checkout
5. **Automates follow-ups** with optimal timing and messaging
6. **Measures success** in real-time (conversion rate, cost per acquisition, revenue)
7. **Scales efficiently** with minimal API cost ($5-12 per customer)

**Expected Performance**:
- 85% response rate (opening message)
- 70% objection resolution (counterarguments)
- 35-40% conversion rate (qualified leads)
- $45-80 average revenue per lead
- $5-12 cost per acquisition
- 3:1 to 8:1 ROI

Ready for implementation.

---

**Document Version**: 1.0
**Status**: Complete
**Architecture Review**: Approved
**Next Step**: Begin Phase 1 Implementation

