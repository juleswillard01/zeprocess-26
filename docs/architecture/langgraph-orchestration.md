# LangGraph Orchestration Architecture - MEGA QUIXAI

**Project**: MEGA QUIXAI - Multi-Agent Autonomous AI System for Sales & Lead Generation
**Date**: 2026-03-14
**Stack**: LangGraph + LangChain + Claude SDK + PostgreSQL/pgvector + LangFuse

---

## Executive Summary

MEGA QUIXAI is a three-agent autonomous system orchestrated via LangGraph that manages the complete sales funnel for coaching/personal development in the male self-improvement niche:

1. **Lead Acquisition Agent**: Identifies and scores prospects from Instagram/YouTube/forums
2. **Seduction Agent**: Engages leads, generates content, qualifies prospects via DMs
3. **Closing Agent**: Converts qualified leads into paying customers via specialized conversations

The orchestration layer (LangGraph) coordinates these agents with:
- **Shared state management** (leads, conversations, scores)
- **Intelligent routing** (conditional handoffs between agents)
- **Supervisor pattern** (central monitoring and error handling)
- **Parallel processing** (multiple leads simultaneously)
- **Checkpoint persistence** (recovery from failures)
- **LangFuse observability** (monitoring + analytics)

This document describes the complete orchestration system, state schemas, routing logic, and implementation patterns.

---

## 1. System Architecture Overview

### 1.1 High-Level Graph Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SUPERVISOR NODE                              │
│                  (Orchestrates + Routes)                            │
└─────────────────────────────────────────────────────────────────────┘
        ↓                        ↓                        ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ LEAD ACQUISITION │  │   SEDUCTION      │  │    CLOSING       │
│     AGENT        │  │      AGENT       │  │      AGENT       │
│                  │  │                  │  │                  │
│ • Scrape sources │  │ • Generate posts │  │ • Sales calls    │
│ • Score ICP      │  │ • Engage DMs     │  │ • Objection hdl  │
│ • Initiate reach │  │ • Qualify leads  │  │ • Convert deals  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
        │                      │                        │
        └──────────┬───────────┴────────────┬───────────┘
                   │                        │
        ┌──────────▼────────────┐  ┌───────▼──────────┐
        │   SHARED STATE        │  │   PERSISTENCE    │
        │   (PostgreSQL)        │  │   (Checkpoints)  │
        │ • Leads              │  │ • Graph state    │
        │ • Conversations      │  │ • Agent memory   │
        │ • Scores             │  │ • Error logs     │
        └───────────────────────┘  └──────────────────┘
                   │
        ┌──────────▼──────────┐
        │     LangFuse        │
        │   (Observability)   │
        │ • Traces            │
        │ • Metrics           │
        │ • Cost tracking     │
        └─────────────────────┘
```

### 1.2 Data Flow

```
External Sources (Instagram, YouTube, Forums)
          ↓
    [LEAD ACQUISITION]
          ↓
    Lead Storage (Scored, ICP-matched)
          ↓
    [SEDUCTION] - Content generation + engagement
          ↓
    Qualified Leads (High intent signals)
          ↓
    [CLOSING] - Sales conversation
          ↓
    Deal Closed / Lost / Recycled
```

### 1.3 Agent Specializations

| Agent | Role | Inputs | Outputs | Tools | LLM |
|-------|------|--------|---------|-------|-----|
| **Lead Acquisition** | Scout & Score | Sources (API/scrape) | Leads + Scores | Instagram API, YouTube API, Web scraper, ICP matcher | Claude 3.5 Haiku |
| **Seduction** | Engage & Qualify | Raw leads, RAG context | Messages, Content, Engagement metrics | Instagram DM, Content generator, RAG retrieval, Lead scorer | Claude 3.5 Sonnet |
| **Closing** | Convert | Qualified leads, Conversation history | Deal status, Notes, Follow-ups | Call transcription, Objection handler, Contract generator | Claude 3.5 Opus |

---

## 2. State Management & Data Schema

### 2.1 Global Graph State (TypedDict)

```python
from typing import TypedDict, Literal, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class LeadStatus(str, Enum):
    DISCOVERED = "discovered"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    IN_CLOSING = "in_closing"
    WON = "won"
    LOST = "lost"
    RECYCLED = "recycled"

class Lead(BaseModel):
    """Individual prospect record"""
    lead_id: str = Field(description="Unique identifier (UUID)")
    source: Literal["instagram", "youtube", "forum", "referral"] = Field(description="Where discovered")
    profile_url: str = Field(description="Social profile link")
    username: str = Field(description="Social username")
    email: Optional[str] = Field(default=None, description="Email if available")
    phone: Optional[str] = Field(default=None, description="Phone if available")

    # Scoring
    icp_score: float = Field(ge=0, le=1, description="ICP match 0-1")
    engagement_score: float = Field(ge=0, le=1, description="Engagement signal 0-1")
    conversion_probability: float = Field(ge=0, le=1, description="Predicted conversion 0-1")

    # Status tracking
    status: LeadStatus = Field(default=LeadStatus.DISCOVERED)
    created_at: datetime = Field(default_factory=datetime.now)
    last_contacted: Optional[datetime] = Field(default=None)
    next_follow_up: Optional[datetime] = Field(default=None)

    # Context
    tags: List[str] = Field(default_factory=list, description="Pain points, interests")
    notes: str = Field(default="", description="Agent observations")
    conversation_history_id: Optional[str] = Field(default=None)

class ConversationMessage(BaseModel):
    """Single message in conversation"""
    role: Literal["agent", "lead", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_name: Literal["acquisition", "seduction", "closing"]
    metadata: dict = Field(default_factory=dict)

class Conversation(BaseModel):
    """Conversation history per lead per agent"""
    conversation_id: str
    lead_id: str
    agent_name: Literal["acquisition", "seduction", "closing"]
    messages: List[ConversationMessage] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    status: Literal["active", "paused", "closed"] = Field(default="active")

class GraphState(TypedDict):
    """Global state managed by LangGraph"""

    # Lead management
    lead_id: str  # Current lead being processed
    leads: dict[str, Lead]  # All known leads {lead_id: Lead}

    # Conversations
    conversations: dict[str, Conversation]  # {conversation_id: Conversation}

    # Current processing context
    current_agent: Literal["supervisor", "acquisition", "seduction", "closing"]
    message: str  # Current message/input

    # Agent decisions
    next_agent: Optional[Literal["acquisition", "seduction", "closing"]] = None
    routing_decision: Optional[dict] = None  # Metadata about routing choice

    # System state
    iteration_count: int = 0
    error_count: int = 0
    batch_id: Optional[str] = None  # For bulk processing
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = {}  # Extensible for agent-specific data
```

### 2.2 PostgreSQL Schema

```sql
-- Leads table
CREATE TABLE leads (
    lead_id UUID PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    profile_url TEXT NOT NULL,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),

    icp_score DECIMAL(3,2) CHECK (icp_score BETWEEN 0 AND 1),
    engagement_score DECIMAL(3,2) CHECK (engagement_score BETWEEN 0 AND 1),
    conversion_probability DECIMAL(3,2) CHECK (conversion_probability BETWEEN 0 AND 1),

    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_contacted TIMESTAMP WITH TIME ZONE,
    next_follow_up TIMESTAMP WITH TIME ZONE,

    tags TEXT[],
    notes TEXT,
    conversation_history_id VARCHAR(255),

    created_by_agent VARCHAR(50),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_icp_score ON leads(icp_score DESC);
CREATE INDEX idx_leads_next_followup ON leads(next_follow_up);

-- Conversations table
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY,
    lead_id UUID NOT NULL REFERENCES leads(lead_id),
    agent_name VARCHAR(50) NOT NULL,

    messages JSONB NOT NULL DEFAULT '[]',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50) NOT NULL,

    metadata JSONB DEFAULT '{}',

    FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
);

CREATE INDEX idx_conversations_lead_id ON conversations(lead_id);
CREATE INDEX idx_conversations_agent_name ON conversations(agent_name);

-- Agent execution logs
CREATE TABLE agent_logs (
    log_id UUID PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    lead_id UUID REFERENCES leads(lead_id),
    conversation_id UUID REFERENCES conversations(conversation_id),

    action VARCHAR(255) NOT NULL,
    input_tokens INT,
    output_tokens INT,
    cost_usd DECIMAL(8,4),
    latency_ms INT,

    status VARCHAR(50) NOT NULL, -- success, failure, error
    error_message TEXT,

    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_agent_name ON agent_logs(agent_name);
CREATE INDEX idx_agent_logs_lead_id ON agent_logs(lead_id);
CREATE INDEX idx_agent_logs_timestamp ON agent_logs(timestamp);

-- RAG vector embeddings (for DDP content)
CREATE TABLE rag_embeddings (
    embedding_id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(1536), -- for Claude embeddings

    source VARCHAR(255), -- "ddp_garconniere" etc
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_rag_embeddings_source ON rag_embeddings(source);
```

### 2.3 State Persistence (Checkpoints)

LangGraph uses PostgreSQL checkpoints for:
- **Graph state snapshots** after each node execution
- **Recovery from crashes** (resume from last checkpoint)
- **Audit trails** (replay any execution)

```python
# Checkpoint schema (LangGraph built-in)
{
    "checkpoint_ns": "main",
    "checkpoint_id": "uuid",
    "checkpoint_map": {
        "supervisor": {"state_key": "value", ...},
        "acquisition": {"state_key": "value", ...},
        # ... per node
    },
    "timestamp": "2026-03-14T10:30:00Z",
    "metadata": {
        "thread_id": "batch_001",
        "user_id": "system",
        "tags": ["production", "lead_batch_1"]
    }
}
```

---

## 3. Routing Logic & State Transitions

### 3.1 Supervisor Routing Rules

The **Supervisor** node decides which agent should process each lead based on:

1. **Lead Status** → Which agents can operate on it
2. **Agent Availability** → Queue management
3. **Lead Scores** → Qualification thresholds
4. **Conversation History** → Previous agent outcomes
5. **Time-based Rules** → Follow-up scheduling

```python
class RoutingDecision(BaseModel):
    next_agent: Literal["acquisition", "seduction", "closing"]
    reason: str
    confidence: float  # 0-1
    fallback_agent: Optional[str] = None
    retry_after_seconds: Optional[int] = None

def supervisor_logic(state: GraphState) -> RoutingDecision:
    """
    Route lead to appropriate agent based on status & scores.
    """
    lead = state["leads"][state["lead_id"]]

    # Rule 1: Newly discovered leads → Acquisition agent sends first contact
    if lead.status == LeadStatus.DISCOVERED:
        return RoutingDecision(
            next_agent="acquisition",
            reason="New lead, needs initial outreach",
            confidence=1.0
        )

    # Rule 2: Contacted leads with engagement → Seduction agent
    if (lead.status in [LeadStatus.CONTACTED, LeadStatus.ENGAGED]
        and lead.engagement_score > 0.4):
        return RoutingDecision(
            next_agent="seduction",
            reason=f"Engagement signal detected (score={lead.engagement_score})",
            confidence=lead.engagement_score
        )

    # Rule 3: Qualified leads → Closing agent
    if (lead.status == LeadStatus.QUALIFIED
        and lead.conversion_probability > 0.6):
        return RoutingDecision(
            next_agent="closing",
            reason=f"Lead qualified for sales (prob={lead.conversion_probability})",
            confidence=lead.conversion_probability
        )

    # Rule 4: No engagement after N days → Re-engage via seduction
    days_since_contact = (datetime.now() - lead.last_contacted).days
    if (lead.status == LeadStatus.CONTACTED
        and days_since_contact > 3
        and days_since_contact < 14):
        return RoutingDecision(
            next_agent="seduction",
            reason=f"Re-engagement: {days_since_contact} days since contact",
            confidence=0.7
        )

    # Rule 5: Lost lead → Recycle back to acquisition with different approach
    if (lead.status == LeadStatus.LOST
        and (datetime.now() - lead.last_contacted).days > 30):
        return RoutingDecision(
            next_agent="acquisition",
            reason="Recycling lost lead (30+ days)",
            confidence=0.5
        )

    # Default: No action needed
    return RoutingDecision(
        next_agent="supervisor",
        reason="No routing rule matched, keep monitoring",
        confidence=0.1,
        retry_after_seconds=3600  # Check again in 1 hour
    )
```

### 3.2 State Transition Diagram

```
DISCOVERED
    ↓ (Supervisor: new lead)
[ACQUISITION] → qualifies + initiates contact
    ↓
CONTACTED
    ↓ (Supervisor: engagement detected)
[SEDUCTION] → generates content, engages DMs
    ↓ (high engagement)
ENGAGED
    ↓ (Supervisor: ready for sales)
[CLOSING] → conversion attempt
    ↓
┌─────────┬──────────┐
│         │          │
WON   LOST (30d)  RECYCLED
         │
    [ACQUISITION] → re-approach
         ↓
    CONTACTED (new attempt)
```

### 3.3 Agent Handoff Protocol

When Supervisor routes lead to Agent X:

```python
def execute_agent(agent_name: str, state: GraphState) -> dict:
    """
    Execute agent node, handle handoff, update state.
    """
    lead = state["leads"][state["lead_id"]]

    # 1. Retrieve or create conversation
    conv_id = f"{lead.lead_id}_{agent_name}_{datetime.now().isoformat()}"
    conversation = state["conversations"].get(conv_id,
                                              Conversation(conversation_id=conv_id,
                                                          lead_id=lead.lead_id,
                                                          agent_name=agent_name))

    # 2. Call agent node (LangChain + Claude)
    agent_output = agent_nodes[agent_name](conversation, lead, state)

    # 3. Extract decision
    decision = parse_agent_output(agent_output)

    # 4. Update lead state
    lead = update_lead_from_agent_output(lead, agent_output)

    # 5. Store conversation
    conversation.messages.extend(agent_output.messages)
    conversation.last_updated = datetime.now()
    state["conversations"][conv_id] = conversation

    # 6. Store updated lead
    state["leads"][lead.lead_id] = lead

    # 7. Route to next agent (or supervisor for re-evaluation)
    state["current_agent"] = agent_name
    state["message"] = f"Agent {agent_name} processed lead {lead.lead_id}"

    return state
```

---

## 4. Agent Node Implementations

### 4.1 Acquisition Agent Node

**Purpose**: Identify, score, and initiate contact with prospects.

```python
from langchain.agents import AgentExecutor, create_tool_use_agent
from langchain_anthropic import ChatAnthropic

class AcquisitionAgentNode:
    def __init__(self, llm: ChatAnthropic, tools: list):
        self.llm = llm
        self.tools = tools  # Instagram API, YouTube API, scraper, ICP matcher
        self.agent = create_tool_use_agent(self.llm, self.tools)
        self.executor = AgentExecutor(agent=self.agent, tools=self.tools)

    async def __call__(self, state: GraphState) -> dict:
        """
        Main execution: discover leads + score + initiate outreach.
        """
        lead = state["leads"][state["lead_id"]]

        # Conversation for this execution
        conv_id = f"{lead.lead_id}_acquisition_{uuid.uuid4()}"
        conv = state["conversations"].get(conv_id,
                                         Conversation(conversation_id=conv_id,
                                                     lead_id=lead.lead_id,
                                                     agent_name="acquisition"))

        # System prompt: ICP definition + outreach strategy
        system_prompt = f"""
You are the Lead Acquisition Agent for a male personal development/seduction coaching business.

Your responsibilities:
1. Identify prospects from Instagram/YouTube/forums who match our ICP
2. Score leads 0-1 on: demographics, pain points, engagement, conversion likelihood
3. Initiate first contact with personalized, value-first messaging

ICP Profile:
- Age: 20-45, males
- Pain points: Dating anxiety, social confidence, self-improvement
- Interests: Personal development, seduction, fitness, stoicism
- Engagement signals: Follows related accounts, comments on similar content, saves posts

Lead: {lead.model_dump_json()}

Instructions:
- Be respectful, non-pushy, consultative
- Reference DDP Garçonnière content where relevant (via RAG)
- Rate engagement potential 0-1
- Suggest specific follow-up timing
- Return structured JSON with scores + proposed outreach message
"""

        # Execute agent loop
        result = await self.executor.ainvoke({
            "input": f"Process lead {lead.lead_id}. Score ICP match, engagement, conversion. Propose outreach.",
            "system": system_prompt,
            "context": lead.model_dump_json()
        })

        # Parse output
        agent_message = ConversationMessage(
            role="agent",
            content=result.get("output", ""),
            agent_name="acquisition",
            metadata=result.get("intermediate_steps", {})
        )
        conv.messages.append(agent_message)

        # Extract scores from structured output
        scores = parse_agent_scores(result.get("output"))
        lead.icp_score = scores.get("icp_score", lead.icp_score)
        lead.engagement_score = scores.get("engagement_score", lead.engagement_score)
        lead.conversion_probability = scores.get("conversion_probability", lead.conversion_probability)

        # Update lead status
        if lead.status == LeadStatus.DISCOVERED:
            lead.status = LeadStatus.CONTACTED
            lead.last_contacted = datetime.now()

        # Return updated state
        state["leads"][lead.lead_id] = lead
        state["conversations"][conv_id] = conv

        return {
            "lead_id": lead.lead_id,
            "conversation_id": conv_id,
            "agent_output": result,
            "next_routing": "supervisor"  # Let supervisor decide next step
        }
```

### 4.2 Seduction Agent Node

**Purpose**: Engage prospects, generate content, qualify through conversation.

```python
class SeductionAgentNode:
    def __init__(self, llm: ChatAnthropic, rag_retriever, tools: list):
        self.llm = llm
        self.rag = rag_retriever  # Access to DDP Garçonnière content
        self.tools = tools  # Instagram DM, content generator, RAG
        self.agent = create_tool_use_agent(self.llm, self.tools)
        self.executor = AgentExecutor(agent=self.agent, tools=self.tools)

    async def __call__(self, state: GraphState) -> dict:
        """
        Main execution: engage via DM, generate content, qualify lead.
        """
        lead = state["leads"][state["lead_id"]]
        conv_id = f"{lead.lead_id}_seduction_{uuid.uuid4()}"
        conv = Conversation(conversation_id=conv_id,
                           lead_id=lead.lead_id,
                           agent_name="seduction")

        # Retrieve relevant DDP content via RAG
        pain_points = lead.tags or []
        rag_context = await self.rag.aretrieve(
            query=f"coaching techniques for {', '.join(pain_points)}",
            top_k=3
        )

        system_prompt = f"""
You are the Seduction/Engagement Agent. You build relationships, generate content, and qualify leads.

Your responsibilities:
1. Send personalized Instagram DMs that provide value
2. Generate Instagram stories/reels/posts relevant to lead's interests
3. Engage authentically, never pushy
4. Assess lead's pain points, buying signals, fit
5. Qualify: is this lead ready for coaching conversation?

Lead Profile:
- Username: {lead.username}
- ICP Score: {lead.icp_score:.2%}
- Engagement Score: {lead.engagement_score:.2%}
- Pain Points: {', '.join(lead.tags)}

Available DDP Garçonnière Content (RAG):
{json.dumps(rag_context, indent=2)}

Instructions:
- Every message should provide genuine value
- Ask discovery questions about their situation
- Reference DDP methods where natural, never salesy
- Rate engagement signals: 0-1 (are they interested?)
- Recommend next step (more engagement, move to closing, pause)
- Keep messages conversational, authentic
"""

        # Execute agent
        result = await self.executor.ainvoke({
            "input": f"Engage lead {lead.username}. Send value-first DM, assess fit.",
            "system": system_prompt,
            "conversation_history": json.dumps([
                {"role": m.role, "content": m.content}
                for m in conv.messages
            ])
        })

        # Record exchange
        agent_message = ConversationMessage(
            role="agent",
            content=result.get("output", ""),
            agent_name="seduction",
            metadata={"rag_sources": [r.get("source") for r in rag_context]}
        )
        conv.messages.append(agent_message)

        # Update engagement score
        engagement = parse_engagement_score(result.get("output"))
        lead.engagement_score = engagement

        # Update status
        if lead.status == LeadStatus.CONTACTED:
            lead.status = LeadStatus.ENGAGED

        # Extract qualification signal
        qualified = parse_qualification_signal(result.get("output"))
        if qualified:
            lead.status = LeadStatus.QUALIFIED
            lead.conversion_probability = 0.7  # Ready for closing

        state["leads"][lead.lead_id] = lead
        state["conversations"][conv_id] = conv

        return {
            "lead_id": lead.lead_id,
            "conversation_id": conv_id,
            "agent_output": result,
            "engagement_score": engagement,
            "next_routing": "supervisor"
        }
```

### 4.3 Closing Agent Node

**Purpose**: Convert qualified leads into paying customers.

```python
class ClosingAgentNode:
    def __init__(self, llm: ChatAnthropic, tools: list):
        self.llm = llm  # Use Opus for closing (complex reasoning)
        self.tools = tools  # Call handler, objection handler, contract generator
        self.agent = create_tool_use_agent(self.llm, self.tools)
        self.executor = AgentExecutor(agent=self.agent, tools=self.tools)

    async def __call__(self, state: GraphState) -> dict:
        """
        Main execution: sales call, objection handling, deal closure.
        """
        lead = state["leads"][state["lead_id"]]
        conv_id = f"{lead.lead_id}_closing_{uuid.uuid4()}"
        conv = Conversation(conversation_id=conv_id,
                           lead_id=lead.lead_id,
                           agent_name="closing")

        # Retrieve conversation history for context
        prev_convs = [
            c for c in state["conversations"].values()
            if c.lead_id == lead.lead_id and c.agent_name != "closing"
        ]

        system_prompt = f"""
You are the Closing Agent. You convert qualified leads into paying customers.

Your responsibilities:
1. Conduct sales conversations (DM or phone call based on lead preference)
2. Uncover core pain points and desired outcomes
3. Handle objections confidently, with evidence
4. Present offers: 1:1 coaching, group programs, training courses
5. Guide to contract/payment
6. Document deal status clearly

Lead Profile:
- Username: {lead.username}
- Email: {lead.email}
- Phone: {lead.phone}
- Previous engagement: {len(prev_convs)} conversations
- Tags: {', '.join(lead.tags)}
- Conversion probability: {lead.conversion_probability:.2%}

Previous Conversation Context:
{json.dumps([{"agent": c.agent_name, "summary": summarize_conv(c)} for c in prev_convs], indent=2)}

Offers to mention:
1. 1:1 Coaching Package: €500-2000/month (12+ weeks commitment)
2. Group Program: €199-499 (12-week cohort)
3. Training Course: €99-299 (self-paced video)

Instructions:
- Be consultative: listen 70%, talk 30%
- Specific: name concrete outcomes ("In 90 days, you'll approach women confidently")
- Social proof: use testimonials where relevant
- Urgency: mention limited spots or pricing increases
- Clear CTA: "Next step is to schedule a call with my program director"
- Document: do they want to move forward? Why or why not?
"""

        # Execute agent
        result = await self.executor.ainvoke({
            "input": f"Close lead {lead.username}. Run sales conversation, handle objections, guide to deal.",
            "system": system_prompt,
            "conversation_history": json.dumps([
                {"role": m.role, "content": m.content}
                for m in conv.messages
            ])
        })

        # Record interaction
        agent_message = ConversationMessage(
            role="agent",
            content=result.get("output", ""),
            agent_name="closing"
        )
        conv.messages.append(agent_message)

        # Parse deal outcome
        deal_outcome = parse_deal_outcome(result.get("output"))

        # Update lead status based on outcome
        if deal_outcome.get("status") == "won":
            lead.status = LeadStatus.WON
            lead.notes += f"\n[{datetime.now().isoformat()}] DEAL CLOSED: {deal_outcome.get('deal_value')}"
        elif deal_outcome.get("status") == "lost":
            lead.status = LeadStatus.LOST
            lead.notes += f"\n[{datetime.now().isoformat()}] DEAL LOST: {deal_outcome.get('reason')}"
            # Schedule recycle
            lead.next_follow_up = datetime.now() + timedelta(days=30)
        elif deal_outcome.get("status") == "pending":
            lead.status = LeadStatus.IN_CLOSING
            lead.next_follow_up = datetime.now() + timedelta(hours=24)

        state["leads"][lead.lead_id] = lead
        state["conversations"][conv_id] = conv

        return {
            "lead_id": lead.lead_id,
            "conversation_id": conv_id,
            "agent_output": result,
            "deal_outcome": deal_outcome,
            "next_routing": "supervisor"
        }
```

---

## 5. Supervisor Node & Central Orchestration

### 5.1 Supervisor Implementation

```python
class SupervisorNode:
    """
    Central orchestrator: monitors all agents, makes routing decisions.
    """
    def __init__(self, llm: ChatAnthropic, agents_dict: dict):
        self.llm = llm
        self.agents = agents_dict  # {"acquisition": Agent, "seduction": Agent, "closing": Agent}

        # Tools for supervisor
        self.tools = [
            self._get_lead_status,
            self._get_agent_metrics,
            self._trigger_agent,
            self._escalate_to_human,
            self._recycle_lead,
            self._pause_lead
        ]

        self.agent = create_tool_use_agent(self.llm, self.tools)
        self.executor = AgentExecutor(agent=self.agent, tools=self.tools)

    async def __call__(self, state: GraphState) -> dict:
        """
        Main loop: evaluate all leads, make routing decisions.
        """

        system_prompt = """
You are the Supervisor Agent for MEGA QUIXAI. You orchestrate 3 specialized agents.

Your responsibilities:
1. Monitor all active leads and conversations
2. Route leads to appropriate agent based on status and scores
3. Handle escalations and errors
4. Optimize pipeline flow
5. Make data-driven decisions

Available agents:
- Acquisition: discover and score leads
- Seduction: engage and qualify
- Closing: convert to customers

Decision rules:
- DISCOVERED → Acquisition (new lead outreach)
- CONTACTED + high engagement → Seduction (deepen engagement)
- ENGAGED + high signals → Closing (sales conversation)
- LOST (30+ days) → Acquisition (recycle with fresh approach)
- ERROR → escalate to human

Current system status:
- Active leads: {total_leads}
- In pipeline: {pipeline_distribution}
- Agent queue depth: {agent_queues}
- Error rate (24h): {error_rate}

Make decisions efficiently. Return JSON with next action per lead.
"""

        # Aggregate current state
        state_summary = {
            "total_leads": len(state["leads"]),
            "by_status": self._group_by_status(state["leads"]),
            "agent_queues": self._get_agent_queue_depth(state),
            "error_rate": self._get_error_rate(),
            "timestamp": datetime.now().isoformat()
        }

        # Call supervisor agent
        result = await self.executor.ainvoke({
            "input": f"Review state: {json.dumps(state_summary)}. Make routing decisions.",
            "system": system_prompt
        })

        # Parse routing decisions
        decisions = parse_routing_decisions(result.get("output"))

        # Apply decisions: route leads to agents
        state["routing_decisions"] = decisions

        return state

    def _get_lead_status(self, lead_id: str) -> dict:
        """Tool: retrieve lead status"""
        pass

    def _get_agent_metrics(self, agent_name: str) -> dict:
        """Tool: get agent performance metrics"""
        pass

    def _trigger_agent(self, agent_name: str, lead_id: str) -> dict:
        """Tool: queue lead for agent processing"""
        pass

    def _escalate_to_human(self, lead_id: str, reason: str) -> dict:
        """Tool: escalate to human operator"""
        pass

    def _recycle_lead(self, lead_id: str) -> dict:
        """Tool: reset lead status, send back to acquisition"""
        pass

    def _pause_lead(self, lead_id: str, until: datetime) -> dict:
        """Tool: pause lead processing until specified time"""
        pass
```

### 5.2 Error Handling & Escalation

```python
class ErrorHandlingMiddleware:
    """
    Handles agent failures, retries, and escalations.
    """

    async def execute_with_retry(
        self,
        agent_node: callable,
        state: GraphState,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> dict:
        """
        Execute agent node with exponential backoff retry.
        """
        for attempt in range(max_retries):
            try:
                result = await agent_node(state)

                # Log success
                await self._log_execution(
                    agent_name=state["current_agent"],
                    lead_id=state["lead_id"],
                    status="success",
                    metadata=result
                )

                return result

            except Exception as e:
                error_msg = str(e)

                # Log error
                await self._log_execution(
                    agent_name=state["current_agent"],
                    lead_id=state["lead_id"],
                    status="error",
                    error=error_msg
                )

                # Transient errors: retry with backoff
                if self._is_transient_error(e) and attempt < max_retries - 1:
                    wait_time = (backoff_factor ** attempt)
                    await asyncio.sleep(wait_time)
                    continue

                # Permanent errors: escalate
                else:
                    return await self._escalate_error(state, e, attempt)

    async def _escalate_error(self, state: GraphState, error: Exception, attempt: int) -> dict:
        """
        Escalate error to human operator.
        """

        escalation = {
            "type": "AGENT_FAILURE",
            "agent": state["current_agent"],
            "lead_id": state["lead_id"],
            "error": str(error),
            "attempts": attempt,
            "timestamp": datetime.now().isoformat(),
            "recommendation": self._suggest_action(error)
        }

        # Store escalation ticket
        await self._store_escalation(escalation)

        # Notify human (Slack, email, dashboard)
        await self._notify_operators(escalation)

        # Update lead status
        lead = state["leads"][state["lead_id"]]
        lead.status = LeadStatus.RECYCLED
        state["leads"][lead.lead_id] = lead

        return {
            "status": "escalated",
            "escalation_id": escalation["timestamp"],
            "next_routing": "human_review"
        }

    def _is_transient_error(self, error: Exception) -> bool:
        """Classify error as transient (retry-able)"""
        transient_types = (
            ConnectionError, TimeoutError, IOError,
            # API rate limits
            RateLimitError, ServiceUnavailableError
        )
        return isinstance(error, transient_types)

    def _suggest_action(self, error: Exception) -> str:
        """Suggest remediation"""
        if isinstance(error, RateLimitError):
            return "Wait 1 hour before retry (API rate limit)"
        elif isinstance(error, APIKeyError):
            return "Check API credentials configuration"
        elif isinstance(error, TimeoutError):
            return "Check network connectivity, increase timeout"
        else:
            return "Manual review required"
```

---

## 6. Concurrency & Parallel Processing

### 6.1 Multi-Lead Batch Processing

```python
class BatchProcessor:
    """
    Process multiple leads in parallel (thread pool).
    """

    def __init__(self, graph: CompiledGraph, max_workers: int = 5):
        self.graph = graph
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = asyncio.Semaphore(max_workers)

    async def process_batch(
        self,
        lead_ids: list[str],
        initial_state: GraphState,
        callback: Optional[callable] = None
    ) -> dict[str, dict]:
        """
        Process multiple leads concurrently.
        """

        tasks = [
            self._process_single_lead(lead_id, initial_state, callback)
            for lead_id in lead_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        output = {}
        for lead_id, result in zip(lead_ids, results):
            if isinstance(result, Exception):
                output[lead_id] = {"status": "error", "error": str(result)}
            else:
                output[lead_id] = result

        return output

    async def _process_single_lead(
        self,
        lead_id: str,
        state: GraphState,
        callback: Optional[callable]
    ) -> dict:
        """
        Process single lead, respect semaphore limit.
        """
        async with self.semaphore:
            try:
                # Set current lead
                state["lead_id"] = lead_id
                state["batch_id"] = uuid.uuid4()

                # Execute graph (from supervisor to final state)
                result = await self.graph.ainvoke(state)

                if callback:
                    await callback(lead_id, "success", result)

                return result

            except Exception as e:
                if callback:
                    await callback(lead_id, "error", str(e))

                raise
```

### 6.2 Agent Queue Management

```python
class AgentQueueManager:
    """
    Manages queues per agent, distributes load fairly.
    """

    def __init__(self):
        self.queues = {
            "acquisition": asyncio.Queue(),
            "seduction": asyncio.Queue(),
            "closing": asyncio.Queue()
        }

        # Metrics
        self.metrics = {
            agent: {"processed": 0, "failed": 0, "avg_latency_ms": 0}
            for agent in self.queues.keys()
        }

    async def enqueue(self, agent_name: str, lead_id: str, priority: int = 0) -> None:
        """
        Add lead to agent's queue (lower priority = higher urgency).
        """
        await self.queues[agent_name].put((priority, lead_id))

    async def dequeue_batch(self, agent_name: str, batch_size: int = 5) -> list[str]:
        """
        Retrieve batch of leads for agent.
        """
        batch = []
        for _ in range(batch_size):
            try:
                _, lead_id = self.queues[agent_name].get_nowait()
                batch.append(lead_id)
            except asyncio.QueueEmpty:
                break
        return batch

    async def get_queue_depth(self) -> dict[str, int]:
        """
        Current queue size per agent.
        """
        return {
            agent: self.queues[agent].qsize()
            for agent in self.queues.keys()
        }

    async def get_metrics(self) -> dict:
        """
        Performance metrics per agent.
        """
        return {
            agent: {
                "queue_depth": self.queues[agent].qsize(),
                **self.metrics[agent]
            }
            for agent in self.queues.keys()
        }
```

---

## 7. Persistence & Checkpointing

### 7.1 LangGraph Checkpoint Strategy

```python
from langgraph.checkpoint.postgres import PostgresSaver

# Initialize checkpointer
checkpointer = PostgresSaver(
    connection_string="postgresql://user:password@localhost:5432/langgraph"
)

# Build graph with checkpointing
graph = StateGraph(GraphState)

# ... add nodes and edges ...

compiled_graph = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["supervisor"],  # Interrupt before major decisions
    # This allows inspection + manual override if needed
)
```

### 7.2 Recovery from Checkpoints

```python
class CheckpointRecovery:
    """
    Recover from failures using checkpoints.
    """

    def __init__(self, checkpointer: PostgresSaver):
        self.checkpointer = checkpointer

    async def recover_from_thread_id(
        self,
        thread_id: str,
        graph: CompiledGraph
    ) -> dict:
        """
        Resume execution from last checkpoint.
        """

        # Get last checkpoint
        checkpoint = await self.checkpointer.aget(
            config={"configurable": {"thread_id": thread_id}}
        )

        if not checkpoint:
            raise ValueError(f"No checkpoint found for thread {thread_id}")

        # Resume from checkpoint
        state = checkpoint["values"]

        # Continue execution
        result = await graph.ainvoke(
            None,  # Don't reinvoke, just resume
            config={"configurable": {"thread_id": thread_id}}
        )

        return result

    async def list_checkpoints(self, thread_id: str) -> list[dict]:
        """
        List all checkpoints for a thread (audit trail).
        """
        checkpoints = await self.checkpointer.alist(
            config={"configurable": {"thread_id": thread_id}}
        )
        return checkpoints
```

---

## 8. LangFuse Integration (Observability)

### 8.1 Tracing Configuration

```python
from langfuse.decorators import observe
from langfuse import Langfuse

# Initialize Langfuse
langfuse = Langfuse(
    public_key="pk_...",
    secret_key="sk_...",
    host="https://cloud.langfuse.com"
)

# Trace each agent execution
@observe()
async def agent_with_tracing(agent_name: str, state: GraphState):
    """Wrap agent execution with Langfuse tracing."""

    trace = langfuse.trace(
        name=f"agent_{agent_name}",
        user_id=state.get("batch_id"),
        metadata={
            "lead_id": state["lead_id"],
            "agent": agent_name,
            "timestamp": datetime.now().isoformat()
        }
    )

    # Execute agent
    result = await agent_node[agent_name](state)

    # Log metrics
    trace.update(
        output=result,
        metadata={
            "tokens_in": result.get("tokens_in", 0),
            "tokens_out": result.get("tokens_out", 0),
            "cost_usd": result.get("cost_usd", 0.0),
            "latency_ms": result.get("latency_ms", 0)
        }
    )

    return result

# Track supervisor decisions
@observe()
async def supervisor_with_tracing(state: GraphState) -> dict:
    trace = langfuse.trace(
        name="supervisor_routing",
        metadata={
            "leads_count": len(state["leads"]),
            "timestamp": datetime.now().isoformat()
        }
    )

    result = await supervisor_node(state)

    trace.update(
        output=result,
        metadata={
            "routing_decisions": len(result.get("routing_decisions", {}))
        }
    )

    return result
```

### 8.2 Metrics & Dashboarding

Key metrics tracked in LangFuse:

```python
METRICS = {
    "agent_latency_ms": "Per-agent execution time",
    "tokens_per_lead": "Total tokens consumed per lead",
    "cost_per_lead": "LLM cost per lead processed",
    "conversion_rate": "Leads → Won deals",
    "error_rate": "Failed executions %",
    "lead_cycle_time": "Avg days from discovery to deal",
    "queue_depth": "Pending leads per agent",
    "escalation_rate": "% leads requiring human intervention",
    "rag_retrieval_accuracy": "Relevance of retrieved DDP content",
    "agent_tool_usage": "Which tools used most per agent"
}

# Monthly cost tracking (budget monitoring)
MONTHLY_BUDGET_TRACKING = {
    "api_costs": {
        "claude_calls": "count * model_price",
        "instagram_api": "monthly_rate",
        "youtube_api": "monthly_rate",
        "total_monthly": "sum"
    },
    "infrastructure_costs": {
        "postgresql": "managed DB costs",
        "langfuse": "observability platform",
        "servers": "compute (if any)"
    },
    "budget_limit": 10000  # USD/month max
}
```

---

## 9. Implementation Roadmap & Project Structure

### 9.1 Repository Structure

```
mega-quixai/
├── .env                          # Secrets (API keys, DB credentials)
├── .env.example                  # Template
├── docker-compose.yml            # PostgreSQL + services
├── pyproject.toml               # Dependencies
│
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point: run graph
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── schema.py            # GraphState, Lead, Conversation, etc.
│   │   └── persistence.py       # Checkpoint management
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── builder.py           # Construct LangGraph
│   │   ├── router.py            # Routing logic (supervisor)
│   │   └── edges.py             # Conditional routing edges
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py              # Base agent class
│   │   ├── acquisition.py       # Lead Acquisition Agent
│   │   ├── seduction.py         # Seduction Agent
│   │   ├── closing.py           # Closing Agent
│   │   └── supervisor.py        # Supervisor Agent
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── instagram.py         # Instagram API tools
│   │   ├── youtube.py           # YouTube scraping
│   │   ├── icp_matcher.py       # ICP scoring
│   │   ├── rag_retriever.py     # DDP content retrieval
│   │   ├── call_handler.py      # Phone call simulation
│   │   ├── objection_handler.py # Sales objection responses
│   │   └── contract_generator.py # Deal documentation
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── postgresql.py        # DB operations
│   │   ├── langfuse_client.py   # Observability integration
│   │   └── instagram_dm.py      # DM sending (if API available)
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logging.py           # Structured logging
│   │   ├── error_handling.py    # Error classification
│   │   ├── parsing.py           # Parse agent outputs
│   │   └── metrics.py           # Metric collection
│   │
│   └── batch/
│       ├── __init__.py
│       ├── processor.py         # Batch processing
│       └── queue_manager.py     # Queue management
│
├── tests/
│   ├── unit/
│   │   ├── test_agents.py
│   │   ├── test_routing.py
│   │   └── test_state.py
│   ├── integration/
│   │   ├── test_graph_flow.py
│   │   └── test_persistence.py
│   └── fixtures.py
│
├── scripts/
│   ├── init_db.py               # Initialize PostgreSQL schema
│   ├── load_rag.py              # Load DDP content to pgvector
│   ├── run_batch.py             # Run batch of leads
│   └── monitor.py               # Real-time metrics dashboard
│
├── docs/
│   ├── architecture.md           # This file
│   ├── api_reference.md          # Tool & state API
│   ├── deployment.md             # Production deployment
│   ├── troubleshooting.md        # Common issues
│   └── examples.md               # Usage examples
│
└── README.md
```

### 9.2 Dependencies (pyproject.toml)

```toml
[project]
name = "mega-quixai"
version = "0.1.0"
description = "Multi-agent autonomous system for coaching sales"

dependencies = [
    # Core
    "python==3.12",
    "langgraph>=0.1.0",
    "langchain>=0.2.0",
    "langchain-anthropic>=0.1.0",
    "langchain-community>=0.1.0",

    # Data & Storage
    "sqlalchemy>=2.0",
    "psycopg2-binary>=2.9",
    "pgvector>=0.2",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",

    # APIs
    "httpx>=0.25",
    "python-instagram>=1.0",
    "yt-dlp>=2024.1",
    "instagrapi>=2.0",  # Alternative Instagram library

    # Observability
    "langfuse>=2.0",
    "opentelemetry-api>=1.20",

    # Utilities
    "python-dotenv>=1.0",
    "click>=8.0",  # CLI tools
    "aiofiles>=23.0",
    "tenacity>=8.0",  # Retry logic
    "structlog>=23.0",  # Structured logging
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.22",
    "pytest-cov>=4.0",
    "black>=23.0",
    "ruff>=0.1",
    "mypy>=1.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

---

## 10. Sample Execution Flow

### 10.1 Single Lead Processing

```python
# 1. Initialize
import asyncio
from src.graph.builder import build_graph
from src.state.schema import GraphState, Lead, LeadStatus
from datetime import datetime
import uuid

async def process_single_lead():
    # Build compiled graph
    graph = build_graph()

    # Create test lead
    test_lead = Lead(
        lead_id=str(uuid.uuid4()),
        source="instagram",
        profile_url="https://instagram.com/testuser",
        username="testuser",
        email=None,
        phone=None,
        icp_score=0.0,
        engagement_score=0.0,
        conversion_probability=0.0,
        status=LeadStatus.DISCOVERED,
        tags=["dating_anxiety", "confidence"],
        notes="Found through hashtag #seduction"
    )

    # Initialize state
    initial_state: GraphState = {
        "lead_id": test_lead.lead_id,
        "leads": {test_lead.lead_id: test_lead},
        "conversations": {},
        "current_agent": "supervisor",
        "message": "New lead discovered",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": None,
        "timestamp": datetime.now(),
        "metadata": {}
    }

    # 2. Execute graph
    # Graph loop:
    # - Supervisor evaluates lead
    # - Routes to Acquisition agent
    # - Acquisition scores + initiates contact
    # - Supervisor checks result, decides next step
    # - ... continues until done or error

    final_state = await graph.ainvoke(initial_state)

    # 3. Extract results
    lead = final_state["leads"][test_lead.lead_id]
    conversations = [
        c for c in final_state["conversations"].values()
        if c.lead_id == test_lead.lead_id
    ]

    print(f"Lead {lead.username}: status={lead.status}, icp={lead.icp_score:.2%}")
    for conv in conversations:
        print(f"  - Agent {conv.agent_name}: {len(conv.messages)} messages")

    return final_state

# Run
if __name__ == "__main__":
    result = asyncio.run(process_single_lead())
```

### 10.2 Batch Processing (Multiple Leads)

```python
async def process_batch(lead_ids: list[str]):
    from src.batch.processor import BatchProcessor

    graph = build_graph()
    processor = BatchProcessor(graph, max_workers=5)

    # Initial state
    initial_state: GraphState = {
        "lead_id": "",  # Will be set per lead
        "leads": {},    # Will be populated
        "conversations": {},
        "current_agent": "supervisor",
        "message": "Batch processing started",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": str(uuid.uuid4()),
        "timestamp": datetime.now(),
        "metadata": {}
    }

    # Process callback
    async def on_lead_processed(lead_id: str, status: str, result: dict):
        print(f"Lead {lead_id}: {status}")

    # Execute batch
    results = await processor.process_batch(
        lead_ids=lead_ids,
        initial_state=initial_state,
        callback=on_lead_processed
    )

    # Summary
    successful = sum(1 for r in results.values() if r.get("status") != "error")
    print(f"\nBatch complete: {successful}/{len(lead_ids)} successful")

    return results

# Usage
lead_ids = [str(uuid.uuid4()) for _ in range(10)]
results = asyncio.run(process_batch(lead_ids))
```

---

## 11. Error Handling & Edge Cases

### 11.1 Common Failure Scenarios

| Scenario | Cause | Handling | Recovery |
|----------|-------|----------|----------|
| **API Rate Limit** | Too many Instagram/YouTube calls | Exponential backoff (2s → 4s → 8s) | Retry after 1 hour |
| **Lead Data Missing** | Email/phone not available | Mark as incomplete, escalate | Manual enrichment |
| **Conversation Stuck** | Agent loops endlessly | Timeout after 5 min | Escalate to human |
| **Poor Engagement Score** | Lead shows low interest | Move to re-engagement queue | Retry in 7 days |
| **Database Connection Lost** | PostgreSQL unavailable | Use in-memory state temporarily | Reconnect + replay checkpoints |
| **LLM Generation Failed** | Claude API error | Log + backoff | Retry with degraded model |
| **RAG Content Empty** | No DDP content matches query | Use fallback generic responses | Skip RAG, proceed with base knowledge |

### 11.2 Escalation Criteria

```python
ESCALATION_TRIGGERS = {
    "high_value_lead": {
        "condition": "conversion_probability > 0.9",
        "action": "Assign to top closer",
        "priority": "CRITICAL"
    },
    "agent_error": {
        "condition": "error_count > 3",
        "action": "Manual review required",
        "priority": "HIGH"
    },
    "unclear_intent": {
        "condition": "engagement_score between 0.3 and 0.6",
        "action": "Human qualification call",
        "priority": "MEDIUM"
    },
    "objection_unhandled": {
        "condition": "closing_agent returns 'unresolved_objection'",
        "action": "Route to expert salesperson",
        "priority": "HIGH"
    }
}
```

---

## 12. Security & Data Protection

### 12.1 API Key Management

```python
# .env template
ANTHROPIC_API_KEY=sk_...
INSTAGRAM_API_TOKEN=...
YOUTUBE_API_KEY=...
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
DATABASE_URL=postgresql://user:pass@localhost:5432/langgraph
REDIS_URL=redis://localhost:6379  # Optional, for caching
```

### 12.2 Database Encryption

```python
# Sensitive fields in PostgreSQL
ALTER TABLE leads ADD COLUMN email_encrypted TEXT;
ALTER TABLE leads ADD COLUMN phone_encrypted TEXT;

# Use application-level encryption for PII
from cryptography.fernet import Fernet

def encrypt_pii(value: str) -> str:
    key = os.getenv("ENCRYPTION_KEY").encode()
    cipher = Fernet(key)
    return cipher.encrypt(value.encode()).decode()

def decrypt_pii(encrypted: str) -> str:
    key = os.getenv("ENCRYPTION_KEY").encode()
    cipher = Fernet(key)
    return cipher.decrypt(encrypted.encode()).decode()
```

### 12.3 PII Handling

- Never log conversation content with PII
- Mask emails/phones in debug output
- Encrypt at rest in PostgreSQL
- Use VPN/TLS for API calls
- Implement audit trail for data access

---

## 13. Cost Estimation & Budget Tracking

### 13.1 Per-Lead Cost Breakdown

```
Acquisition Agent per lead:
  - Claude 3.5 Haiku (scoring): ~500 tokens × $0.80/1M = $0.0004
  - Instagram API calls: $0 (free tier up to 100/hour)
  - Total: ~$0.0004

Seduction Agent per lead:
  - Claude 3.5 Sonnet (engagement): ~2000 tokens × $3/1M = $0.006
  - RAG retrieval (pgvector): ~0.0001 (minimal DB cost)
  - Total: ~$0.006

Closing Agent per lead:
  - Claude 3.5 Opus (sales): ~3000 tokens × $15/1M = $0.045
  - Total: ~$0.045

Total per lead (full cycle): ~$0.051

Monthly budget at 10k leads:
  10,000 leads × $0.051 = $510 API cost
  + $500 infrastructure (DB, LangFuse, compute)
  = $1,010/month (well under $10k budget)
```

### 13.2 Budget Monitoring Script

```python
class BudgetMonitor:
    """Track API spending against monthly budget."""

    def __init__(self, monthly_limit: float = 10000.0):
        self.monthly_limit = monthly_limit
        self.spent = 0.0

    async def track_agent_execution(self, agent: str, tokens_in: int, tokens_out: int):
        # Calculate cost based on model
        costs = {
            "acquisition": self._cost_haiku(tokens_in, tokens_out),
            "seduction": self._cost_sonnet(tokens_in, tokens_out),
            "closing": self._cost_opus(tokens_in, tokens_out)
        }

        cost = costs.get(agent, 0.0)
        self.spent += cost

        # Alert if approaching limit
        if self.spent > self.monthly_limit * 0.8:
            await self._send_alert(f"Budget 80% consumed: ${self.spent:.2f}")

        if self.spent > self.monthly_limit:
            await self._send_alert(f"BUDGET EXCEEDED: ${self.spent:.2f}")
            raise BudgetExceededError()

    def _cost_haiku(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * 0.80 + tokens_out * 1.60) / 1_000_000

    def _cost_sonnet(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * 3.00 + tokens_out * 15.00) / 1_000_000

    def _cost_opus(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * 15.00 + tokens_out * 75.00) / 1_000_000
```

---

## 14. Deployment & Operations

### 14.1 Local Development Setup

```bash
# Clone repo
git clone https://github.com/your-org/mega-quixai.git
cd mega-quixai

# Setup environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev]"

# Initialize database
python scripts/init_db.py

# Load RAG content (DDP)
python scripts/load_rag.py --source ddp_garconniere

# Run tests
pytest tests/ -v --cov=src

# Start local graph execution
python -m src.main --mode single --lead-id <uuid>
```

### 14.2 Production Deployment (Docker)

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv pip install --system -r pyproject.toml

# Copy source
COPY src/ src/
COPY scripts/ scripts/

# Run
CMD ["python", "-m", "src.main", "--mode", "batch", "--workers", "5"]
```

```yaml
# docker-compose.yml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: langgraph
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  graph:
    build: .
    depends_on:
      - postgres
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/langgraph
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
    ports:
      - "8000:8000"  # If exposing API endpoint
    command: python -m src.main --mode batch

volumes:
  postgres_data:
```

### 14.3 Monitoring Dashboard (Pseudo-code)

```python
# scripts/monitor.py - Real-time metrics dashboard

import streamlit as st
from src.integrations.postgresql import get_db
from src.integrations.langfuse_client import get_metrics

st.set_page_config(page_title="MEGA QUIXAI Monitor", layout="wide")

# Sidebar filters
agent_filter = st.sidebar.selectbox("Agent", ["All", "Acquisition", "Seduction", "Closing"])
date_range = st.sidebar.date_input("Date Range", value=(date.today() - timedelta(days=7), date.today()))

# Main metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Leads", get_total_leads())
col2.metric("Conversion Rate", f"{get_conversion_rate():.1%}")
col3.metric("Avg Cost/Lead", f"${get_avg_cost():.2f}")
col4.metric("Monthly Budget Used", f"${get_budget_used():.0f}")

# Charts
st.subheader("Leads by Status")
status_chart = get_leads_by_status_chart()
st.bar_chart(status_chart)

st.subheader("Agent Performance")
agent_metrics = get_agent_performance()
st.table(agent_metrics)

st.subheader("Recent Escalations")
escalations = get_recent_escalations()
st.dataframe(escalations)
```

---

## 15. Success Metrics & KPIs

### 15.1 Core KPIs

| KPI | Target | Measurement |
|-----|--------|-------------|
| **Conversion Rate** | 5-10% | (Deals Won) / (Qualified Leads) |
| **Lead Volume** | 100+/day | New leads discovered daily |
| **Cost per Lead** | <$0.10 | Total API cost / leads processed |
| **Cycle Time** | 7-14 days | Days from discovery to deal |
| **Error Rate** | <1% | Failed executions / total |
| **Availability** | 99.5% | Uptime of graph system |
| **Agent Efficiency** | 80%+ | Leads routed correctly / total |

### 15.2 Agent-Specific KPIs

```python
ACQUISITION_KPI = {
    "leads_discovered_per_day": 100,
    "icp_match_accuracy": 0.85,  # True positives / all scored
    "initial_engagement_rate": 0.30,  # Reply to first message
    "cost_per_qualified_lead": 0.05
}

SEDUCTION_KPI = {
    "engagement_score_improvement": (0.60 - 0.30),  # Start → end
    "qualification_rate": 0.40,  # ENGAGED → QUALIFIED
    "response_rate": 0.70,  # Replies to sent messages
    "conversation_length_msgs": 5
}

CLOSING_KPI = {
    "win_rate": 0.10,  # Closed deals / attempted closes
    "avg_deal_value": 500,  # EUR
    "objection_resolution": 0.75,  # Handled objections
    "follow_up_required": 0.20  # Need additional touches
}
```

---

## 16. Conclusion

MEGA QUIXAI's orchestration architecture leverages **LangGraph's strength** in state management and routing to coordinate 3 specialized agents through a complete sales funnel. The system is:

- **Resilient**: Checkpointing + error handling + human escalation
- **Observable**: Full tracing via LangFuse + PostgreSQL audit logs
- **Scalable**: Concurrent processing, queue management, batch operations
- **Cost-controlled**: Budget tracking, efficient token usage (~$0.05/lead)
- **Maintainable**: Clear separation of concerns, modular agent design

Key architectural decisions:
1. **Supervisor pattern** for central routing (not agent-to-agent handoffs)
2. **PostgreSQL for all state** (reliable, queryable, checkpointable)
3. **Model selection by agent** (Haiku→Sonnet→Opus by complexity)
4. **RAG integration** in Seduction agent (leverage DDP content)
5. **Async/concurrent processing** for multi-lead batches

This design is production-ready and can scale to handle thousands of leads simultaneously within the $3k-$10k budget.

---

**Next Steps**:
1. Implement base code skeleton (`src/` directory structure)
2. Build individual agent nodes with LangChain tools
3. Construct LangGraph with routing logic
4. Set up PostgreSQL + LangFuse integration
5. Run batch tests with synthetic leads
6. Deploy to staging environment
7. Monitor KPIs and optimize routing rules

