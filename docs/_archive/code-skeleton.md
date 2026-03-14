# LangGraph Implementation Code Skeleton - MEGA QUIXAI

**Purpose**: Complete Python code structure and implementation examples for orchestration system.
**Language**: Python 3.12+ with async/await patterns
**Framework**: LangGraph 0.1.0+, LangChain 0.2.0+, Claude SDK

---

## Part 1: State Schema (src/state/schema.py)

```python
"""
Global state definitions for LangGraph orchestration.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class LeadStatus(str, Enum):
    """Possible states of a lead through the pipeline."""
    DISCOVERED = "discovered"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    IN_CLOSING = "in_closing"
    WON = "won"
    LOST = "lost"
    RECYCLED = "recycled"


class Source(str, Enum):
    """Where the lead was discovered."""
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    FORUM = "forum"
    REFERRAL = "referral"
    EMAIL = "email"


class Lead(BaseModel):
    """Individual prospect record."""

    lead_id: str = Field(default_factory=lambda: str(uuid4()))
    source: Source
    profile_url: str
    username: str

    email: Optional[str] = None
    phone: Optional[str] = None

    # Scoring (0-1)
    icp_score: float = Field(ge=0, le=1, default=0.0)
    engagement_score: float = Field(ge=0, le=1, default=0.0)
    conversion_probability: float = Field(ge=0, le=1, default=0.0)

    # Status tracking
    status: LeadStatus = LeadStatus.DISCOVERED
    created_at: datetime = Field(default_factory=datetime.now)
    last_contacted: Optional[datetime] = None
    next_follow_up: Optional[datetime] = None

    # Context
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    conversation_history_id: Optional[str] = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "lead_id": "123e4567-e89b-12d3-a456-426614174000",
                "source": "instagram",
                "profile_url": "https://instagram.com/john_doe",
                "username": "john_doe",
                "icp_score": 0.85,
                "status": "contacted",
                "tags": ["dating_anxiety", "self_improvement"]
            }
        }


class ConversationMessage(BaseModel):
    """Single message in a conversation."""

    role: Literal["agent", "lead", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_name: Literal["acquisition", "seduction", "closing"]
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Extracted info
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None


class Conversation(BaseModel):
    """Conversation history between agent and lead."""

    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str
    agent_name: Literal["acquisition", "seduction", "closing"]

    messages: list[ConversationMessage] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    status: Literal["active", "paused", "closed"] = "active"

    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_message(
        self,
        role: Literal["agent", "lead", "system"],
        content: str,
        agent_name: str,
        metadata: Optional[dict] = None
    ) -> None:
        """Add message to conversation."""
        msg = ConversationMessage(
            role=role,
            content=content,
            agent_name=agent_name,
            metadata=metadata or {}
        )
        self.messages.append(msg)
        self.last_updated = datetime.now()

    def get_messages_as_prompt(self) -> str:
        """Format messages for LLM prompt."""
        lines = []
        for msg in self.messages:
            lines.append(f"{msg.role.upper()}: {msg.content}")
        return "\n".join(lines)


class GraphState(BaseModel):
    """Global state managed by LangGraph."""

    # Lead management
    lead_id: str
    leads: dict[str, Lead] = Field(default_factory=dict)

    # Conversations
    conversations: dict[str, Conversation] = Field(default_factory=dict)

    # Current processing context
    current_agent: Literal["supervisor", "acquisition", "seduction", "closing"] = "supervisor"
    message: str = ""

    # Routing
    next_agent: Optional[Literal["acquisition", "seduction", "closing"]] = None
    routing_decision: Optional[dict[str, Any]] = None

    # Tracking
    iteration_count: int = 0
    error_count: int = 0
    batch_id: Optional[str] = None
    thread_id: Optional[str] = None

    # Timing
    timestamp: datetime = Field(default_factory=datetime.now)

    # Extensible
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def get_current_lead(self) -> Lead:
        """Get the lead currently being processed."""
        if self.lead_id not in self.leads:
            raise ValueError(f"Lead {self.lead_id} not found in state")
        return self.leads[self.lead_id]

    def update_current_lead(self, lead: Lead) -> None:
        """Update the current lead in state."""
        self.leads[lead.lead_id] = lead

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Get conversation by ID."""
        return self.conversations.get(conv_id)

    def add_conversation(self, conv: Conversation) -> None:
        """Add or update conversation."""
        self.conversations[conv.conversation_id] = conv
```

---

## Part 2: Base Agent Class (src/agents/base.py)

```python
"""
Base agent class with common patterns.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_use_agent
from langchain.tools import BaseTool

from src.state.schema import GraphState, Conversation
from src.utils.logging import get_logger
from src.utils.error_handling import AgentError

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(
        self,
        name: str,
        llm: ChatAnthropic,
        tools: list[BaseTool],
        temperature: float = 0.7
    ):
        self.name = name
        self.llm = llm.bind(temperature=temperature)
        self.tools = tools
        self.agent = create_tool_use_agent(self.llm, tools)
        self.executor = AgentExecutor(agent=self.agent, tools=tools)

    @abstractmethod
    async def __call__(self, state: GraphState) -> dict[str, Any]:
        """
        Main execution method.
        Must be implemented by subclasses.
        """
        pass

    async def execute_with_tools(
        self,
        input_text: str,
        system_prompt: str,
        conversation: Optional[Conversation] = None
    ) -> dict[str, Any]:
        """
        Execute agent with tool use.
        """
        try:
            # Format conversation history
            conversation_history = ""
            if conversation:
                conversation_history = conversation.get_messages_as_prompt()

            # Execute agent
            result = await self.executor.ainvoke({
                "input": input_text,
                "system": system_prompt,
                "conversation_history": conversation_history
            })

            logger.info(
                f"Agent {self.name} execution successful",
                extra={
                    "agent": self.name,
                    "output_length": len(result.get("output", ""))
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Agent {self.name} execution failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise AgentError(f"{self.name} execution failed: {str(e)}")

    def _parse_json_output(self, output: str) -> dict[str, Any]:
        """
        Extract JSON from agent output.
        Handles cases where agent wraps JSON in markdown code blocks.
        """
        try:
            # Try direct JSON parse
            return json.loads(output)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in output:
                start = output.index("```json") + 7
                end = output.index("```", start)
                json_str = output[start:end].strip()
                return json.loads(json_str)
            elif "```" in output:
                start = output.index("```") + 3
                end = output.index("```", start)
                json_str = output[start:end].strip()
                return json.loads(json_str)
            else:
                # No JSON found
                logger.warning(
                    f"Could not parse JSON from agent output",
                    extra={"output_preview": output[:200]}
                )
                return {}

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (1 token ≈ 4 characters).
        """
        return len(text) // 4
```

---

## Part 3: Acquisition Agent (src/agents/acquisition.py)

```python
"""
Lead Acquisition Agent: discover, score, initiate contact.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain.tools import BaseTool

from src.agents.base import BaseAgent
from src.state.schema import GraphState, Conversation, ConversationMessage
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AcquisitionAgent(BaseAgent):
    """Lead Acquisition Agent."""

    def __init__(self, llm: ChatAnthropic, tools: list[BaseTool]):
        super().__init__(name="acquisition", llm=llm, tools=tools, temperature=0.5)

    async def __call__(self, state: GraphState) -> dict[str, Any]:
        """
        Process lead: score ICP, engagement, propose outreach.
        """
        lead = state.get_current_lead()

        # Create or get conversation
        conv_id = f"{lead.lead_id}_acquisition_{datetime.now().isoformat()}"
        conversation = Conversation(
            conversation_id=conv_id,
            lead_id=lead.lead_id,
            agent_name="acquisition"
        )

        # System prompt
        system_prompt = self._get_system_prompt(lead)

        # Execute agent
        try:
            result = await self.execute_with_tools(
                input_text=f"Process lead {lead.username}. Score ICP, engagement, "
                          f"conversion probability. Propose outreach message.",
                system_prompt=system_prompt,
                conversation=conversation
            )

            # Parse structured output
            parsed = self._parse_json_output(result.get("output", ""))

            # Update lead scores
            lead.icp_score = parsed.get("icp_score", lead.icp_score)
            lead.engagement_score = parsed.get("engagement_score", lead.engagement_score)
            lead.conversion_probability = parsed.get("conversion_probability", lead.conversion_probability)

            # Update status
            from src.state.schema import LeadStatus
            if lead.status == LeadStatus.DISCOVERED:
                lead.status = LeadStatus.CONTACTED
                lead.last_contacted = datetime.now()

            # Add tags
            new_tags = parsed.get("tags", [])
            lead.tags.extend(new_tags)
            lead.tags = list(set(lead.tags))  # Deduplicate

            # Record in conversation
            conversation.add_message(
                role="agent",
                content=result.get("output", ""),
                agent_name="acquisition",
                metadata={
                    "scores": {
                        "icp": lead.icp_score,
                        "engagement": lead.engagement_score,
                        "conversion": lead.conversion_probability
                    }
                }
            )

            # Store
            state.update_current_lead(lead)
            state.add_conversation(conversation)

            return {
                "status": "success",
                "lead_id": lead.lead_id,
                "conversation_id": conv_id,
                "scores": {
                    "icp": lead.icp_score,
                    "engagement": lead.engagement_score,
                    "conversion": lead.conversion_probability
                }
            }

        except Exception as e:
            logger.error(f"Acquisition agent error: {str(e)}", exc_info=True)
            state.error_count += 1
            return {
                "status": "error",
                "lead_id": lead.lead_id,
                "error": str(e)
            }

    def _get_system_prompt(self, lead) -> str:
        """Generate system prompt for this lead."""
        return f"""
You are the Lead Acquisition Agent for MEGA QUIXAI.

Your responsibilities:
1. Evaluate prospect fit (ICP scoring)
2. Identify pain points and interests
3. Score engagement likelihood
4. Estimate conversion probability
5. Propose personalized, value-first outreach message

Lead Information:
- Username: {lead.username}
- Source: {lead.source.value}
- URL: {lead.profile_url}
- Tags (interests): {', '.join(lead.tags) if lead.tags else 'None yet'}

ICP Profile (what we're looking for):
- Age: 20-45, males
- Pain points: Dating anxiety, social confidence, self-improvement
- Interests: Personal development, seduction, fitness, stoicism

Return a JSON object with:
{{
    "icp_score": 0.0-1.0,
    "engagement_score": 0.0-1.0,
    "conversion_probability": 0.0-1.0,
    "tags": ["pain_point_1", "interest_1"],
    "outreach_message": "Your personalized message here",
    "reasoning": "Why you scored this way"
}}

Be analytical. Reference specific signals from profile if available.
"""
```

---

## Part 4: Seduction Agent (src/agents/seduction.py)

```python
"""
Seduction Agent: engagement, content generation, qualification.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain.tools import BaseTool

from src.agents.base import BaseAgent
from src.state.schema import GraphState, Conversation, LeadStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SeductionAgent(BaseAgent):
    """Engagement and Lead Qualification Agent."""

    def __init__(self, llm: ChatAnthropic, tools: list[BaseTool], rag_retriever=None):
        super().__init__(name="seduction", llm=llm, tools=tools, temperature=0.7)
        self.rag = rag_retriever

    async def __call__(self, state: GraphState) -> dict[str, Any]:
        """
        Engage lead via DM, generate content, assess qualification.
        """
        lead = state.get_current_lead()

        # Create conversation
        conv_id = f"{lead.lead_id}_seduction_{datetime.now().isoformat()}"
        conversation = Conversation(
            conversation_id=conv_id,
            lead_id=lead.lead_id,
            agent_name="seduction"
        )

        # Retrieve RAG content
        rag_context = ""
        if self.rag:
            try:
                query = f"coaching techniques for {', '.join(lead.tags[:3])}"
                results = await self.rag.aretrieve(query=query, top_k=2)
                rag_context = json.dumps(results, indent=2)
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {str(e)}")

        # System prompt
        system_prompt = self._get_system_prompt(lead, rag_context)

        try:
            result = await self.execute_with_tools(
                input_text=f"Engage {lead.username}. Send value-first DM. "
                          f"Assess engagement and qualification signals.",
                system_prompt=system_prompt,
                conversation=conversation
            )

            # Parse output
            parsed = self._parse_json_output(result.get("output", ""))

            # Update engagement score
            new_engagement = parsed.get("engagement_score", lead.engagement_score)
            lead.engagement_score = max(lead.engagement_score, new_engagement)

            # Check qualification
            is_qualified = parsed.get("qualified", False)
            if is_qualified and lead.status in [LeadStatus.CONTACTED, LeadStatus.ENGAGED]:
                lead.status = LeadStatus.QUALIFIED
                lead.conversion_probability = max(0.6, lead.conversion_probability)

            elif lead.status == LeadStatus.CONTACTED:
                lead.status = LeadStatus.ENGAGED

            # Record
            conversation.add_message(
                role="agent",
                content=result.get("output", ""),
                agent_name="seduction",
                metadata={
                    "engagement": new_engagement,
                    "qualified": is_qualified,
                    "rag_used": bool(self.rag and rag_context)
                }
            )

            state.update_current_lead(lead)
            state.add_conversation(conversation)

            return {
                "status": "success",
                "lead_id": lead.lead_id,
                "conversation_id": conv_id,
                "engagement_score": lead.engagement_score,
                "qualified": is_qualified
            }

        except Exception as e:
            logger.error(f"Seduction agent error: {str(e)}", exc_info=True)
            state.error_count += 1
            return {
                "status": "error",
                "lead_id": lead.lead_id,
                "error": str(e)
            }

    def _get_system_prompt(self, lead, rag_context: str) -> str:
        """Generate system prompt."""
        return f"""
You are the Seduction/Engagement Agent. Build relationships, generate value, qualify leads.

Your responsibilities:
1. Send personalized, value-first Instagram DMs
2. Generate relevant content ideas (stories, reels, posts)
3. Engage authentically, never pushy
4. Assess pain points and buying signals
5. Determine if lead is ready for sales (closing)

Lead Profile:
- Username: {lead.username}
- ICP Score: {lead.icp_score:.2%}
- Engagement Score: {lead.engagement_score:.2%}
- Pain Points: {', '.join(lead.tags)}
- Status: {lead.status.value}

Available DDP Content (from RAG):
{rag_context if rag_context else 'No content retrieved'}

Instructions:
- Provide genuine value in every message
- Ask discovery questions about their situation
- Reference DDP methods where natural (never salesy)
- Rate their engagement signal (0-1)
- Recommend next step clearly
- Keep messages conversational and authentic

Return JSON:
{{
    "message": "Your DM message",
    "engagement_score": 0.0-1.0,
    "qualified": true/false,
    "reasoning": "Why you qualify/disqualify",
    "next_step": "More engagement / Move to closing / Pause"
}}
"""
```

---

## Part 5: Closing Agent (src/agents/closing.py)

```python
"""
Closing Agent: sales conversations, objection handling, deal closure.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain.tools import BaseTool

from src.agents.base import BaseAgent
from src.state.schema import GraphState, Conversation, LeadStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClosingAgent(BaseAgent):
    """Sales Closing Agent (uses Opus model for complex reasoning)."""

    def __init__(self, llm: ChatAnthropic, tools: list[BaseTool]):
        super().__init__(name="closing", llm=llm, tools=tools, temperature=0.6)

    async def __call__(self, state: GraphState) -> dict[str, Any]:
        """
        Conduct sales conversation, handle objections, close deals.
        """
        lead = state.get_current_lead()

        # Create conversation
        conv_id = f"{lead.lead_id}_closing_{datetime.now().isoformat()}"
        conversation = Conversation(
            conversation_id=conv_id,
            lead_id=lead.lead_id,
            agent_name="closing"
        )

        # Prepare conversation history
        prev_convs = [
            c for c in state.conversations.values()
            if c.lead_id == lead.lead_id and c.agent_name != "closing"
        ]
        conv_summary = self._summarize_previous_convs(prev_convs)

        # System prompt
        system_prompt = self._get_system_prompt(lead, conv_summary)

        try:
            result = await self.execute_with_tools(
                input_text=f"Close {lead.username}. Run sales conversation, "
                          f"handle objections, guide to decision.",
                system_prompt=system_prompt,
                conversation=conversation
            )

            # Parse outcome
            parsed = self._parse_json_output(result.get("output", ""))

            # Update based on outcome
            outcome = parsed.get("status", "pending").lower()

            if outcome == "won":
                lead.status = LeadStatus.WON
                lead.notes += f"\n[{datetime.now().isoformat()}] DEAL CLOSED: "
                lead.notes += f"{parsed.get('deal_value', 'Unknown')} EUR"
                lead.conversion_probability = 1.0

            elif outcome == "lost":
                lead.status = LeadStatus.LOST
                lead.notes += f"\n[{datetime.now().isoformat()}] DEAL LOST"
                lead.next_follow_up = datetime.now() + timedelta(days=30)

            else:  # pending
                lead.status = LeadStatus.IN_CLOSING
                lead.next_follow_up = datetime.now() + timedelta(hours=24)

            # Record
            conversation.add_message(
                role="agent",
                content=result.get("output", ""),
                agent_name="closing",
                metadata={
                    "outcome": outcome,
                    "deal_value": parsed.get("deal_value"),
                    "objections_handled": parsed.get("objections_count", 0)
                }
            )

            state.update_current_lead(lead)
            state.add_conversation(conversation)

            return {
                "status": "success",
                "lead_id": lead.lead_id,
                "conversation_id": conv_id,
                "outcome": outcome,
                "deal_value": parsed.get("deal_value")
            }

        except Exception as e:
            logger.error(f"Closing agent error: {str(e)}", exc_info=True)
            state.error_count += 1
            return {
                "status": "error",
                "lead_id": lead.lead_id,
                "error": str(e)
            }

    def _summarize_previous_convs(self, convs: list[Conversation]) -> str:
        """Summarize previous conversations for context."""
        if not convs:
            return "No previous conversation history"

        summary = []
        for conv in convs:
            msg_count = len(conv.messages)
            summary.append(f"- {conv.agent_name}: {msg_count} messages")

        return "\n".join(summary)

    def _get_system_prompt(self, lead, conv_summary: str) -> str:
        """Generate system prompt for closing."""
        return f"""
You are the Closing Agent. Convert qualified leads into paying customers.

Your responsibilities:
1. Conduct consultative sales conversations
2. Uncover core pain points and desired outcomes
3. Handle objections with confidence and evidence
4. Present coaching offers clearly
5. Guide to contract/payment
6. Document deal status

Lead Profile:
- Username: {lead.username}
- Email: {lead.email or 'Not provided'}
- Phone: {lead.phone or 'Not provided'}
- Conversion Probability: {lead.conversion_probability:.2%}

Previous Engagement:
{conv_summary}

Offers to present:
1. 1:1 Coaching Package: €500-2000/month (12+ weeks)
2. Group Program: €199-499 (12-week cohort)
3. Training Course: €99-299 (self-paced)

Instructions:
- Listen 70%, talk 30%
- Be specific about outcomes
- Use social proof where relevant
- Create urgency (limited spots, price increase)
- Clear CTA: "Schedule call with program director"

Return JSON:
{{
    "status": "won" | "lost" | "pending",
    "deal_value": 500 (EUR, if won),
    "offer_presented": "1:1" | "Group" | "Course",
    "objections_count": 0,
    "next_step": "Payment processing" | "30-day recycle" | "Call tomorrow",
    "summary": "Deal summary or reason for loss"
}}
"""
```

---

## Part 6: Supervisor Node (src/agents/supervisor.py)

```python
"""
Supervisor: Central orchestration, routing, error handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain.tools import BaseTool, tool

from src.agents.base import BaseAgent
from src.state.schema import GraphState, LeadStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SupervisorAgent(BaseAgent):
    """Central Supervisor Agent."""

    def __init__(self, llm: ChatAnthropic):
        # Supervisor has special tools
        tools = [
            self._tool_get_lead_status,
            self._tool_next_action,
            self._tool_escalate
        ]
        super().__init__(name="supervisor", llm=llm, tools=tools, temperature=0.3)

    async def __call__(self, state: GraphState) -> dict[str, Any]:
        """
        Main routing logic: evaluate lead, decide next agent.
        """
        lead = state.get_current_lead()

        # Routing decision
        routing = await self._decide_routing(state, lead)

        state.routing_decision = routing

        return {
            "status": "success",
            "routing": routing,
            "next_agent": routing.get("next_agent")
        }

    async def _decide_routing(self, state: GraphState, lead) -> dict[str, Any]:
        """
        Determine which agent should process lead.
        """

        # Rule 1: Newly discovered
        if lead.status == LeadStatus.DISCOVERED:
            return {
                "next_agent": "acquisition",
                "reason": "New lead, needs discovery and scoring",
                "confidence": 1.0
            }

        # Rule 2: Contacted with engagement
        if (lead.status in [LeadStatus.CONTACTED, LeadStatus.ENGAGED]
            and lead.engagement_score > 0.4):
            return {
                "next_agent": "seduction",
                "reason": f"Engagement detected (score={lead.engagement_score:.2f})",
                "confidence": lead.engagement_score
            }

        # Rule 3: Qualified, ready for closing
        if (lead.status == LeadStatus.QUALIFIED
            and lead.conversion_probability > 0.6):
            return {
                "next_agent": "closing",
                "reason": f"Qualified lead (prob={lead.conversion_probability:.2f})",
                "confidence": lead.conversion_probability
            }

        # Rule 4: Re-engagement (3-14 days no contact)
        if lead.last_contacted:
            days_since = (datetime.now() - lead.last_contacted).days
            if (lead.status == LeadStatus.CONTACTED
                and 3 < days_since < 14):
                return {
                    "next_agent": "seduction",
                    "reason": f"Re-engagement ({days_since} days since contact)",
                    "confidence": 0.7
                }

        # Rule 5: Recycle lost leads (30+ days)
        if lead.status == LeadStatus.LOST:
            if lead.last_contacted:
                days_since = (datetime.now() - lead.last_contacted).days
                if days_since > 30:
                    return {
                        "next_agent": "acquisition",
                        "reason": f"Recycling lost lead ({days_since} days)",
                        "confidence": 0.5
                    }

        # Default: no action needed
        return {
            "next_agent": "supervisor",
            "reason": "No routing rule matched, check again later",
            "confidence": 0.1,
            "retry_after_seconds": 3600
        }

    # Tools accessible to supervisor

    @tool
    def _tool_get_lead_status(self, lead_id: str) -> str:
        """Get current lead status."""
        return f"Lead {lead_id} status retrieved"

    @tool
    def _tool_next_action(self, lead_id: str, action: str) -> str:
        """Queue next action for lead."""
        return f"Action {action} queued for lead {lead_id}"

    @tool
    def _tool_escalate(self, lead_id: str, reason: str) -> str:
        """Escalate lead to human operator."""
        logger.warning(
            f"Lead escalated",
            extra={"lead_id": lead_id, "reason": reason}
        )
        return f"Lead {lead_id} escalated: {reason}"
```

---

## Part 7: Graph Builder (src/graph/builder.py)

```python
"""
Build the LangGraph state machine.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langchain_anthropic import ChatAnthropic

from src.state.schema import GraphState
from src.agents.acquisition import AcquisitionAgent
from src.agents.seduction import SeductionAgent
from src.agents.closing import ClosingAgent
from src.agents.supervisor import SupervisorAgent
from src.utils.logging import get_logger

logger = get_logger(__name__)


def build_graph(
    checkpoint_saver=None,
    rag_retriever=None
):
    """
    Build the compiled LangGraph.
    """

    # Initialize LLM
    llm_haiku = ChatAnthropic(model="claude-3-5-haiku-20241022")
    llm_sonnet = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    llm_opus = ChatAnthropic(model="claude-3-5-opus-20241022")

    # Initialize agents
    acquisition = AcquisitionAgent(llm=llm_haiku, tools=[])
    seduction = SeductionAgent(llm=llm_sonnet, tools=[], rag_retriever=rag_retriever)
    closing = ClosingAgent(llm=llm_opus, tools=[])
    supervisor = SupervisorAgent(llm=llm_haiku)

    # Build graph
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("supervisor", supervisor)
    graph.add_node("acquisition", acquisition)
    graph.add_node("seduction", seduction)
    graph.add_node("closing", closing)

    # Edges
    graph.add_edge(START, "supervisor")

    # Supervisor routes
    graph.add_conditional_edges(
        "supervisor",
        _get_next_node,
        {
            "acquisition": "acquisition",
            "seduction": "seduction",
            "closing": "closing",
            "supervisor": "supervisor",
            "end": END
        }
    )

    # Agent feedback to supervisor (or end)
    graph.add_edge("acquisition", "supervisor")
    graph.add_edge("seduction", "supervisor")
    graph.add_edge("closing", "supervisor")

    # Compile with checkpointing
    compiled = graph.compile(
        checkpointer=checkpoint_saver,
        interrupt_before=["supervisor"]  # Inspect before routing
    )

    logger.info("LangGraph compiled successfully")
    return compiled


def _get_next_node(state: GraphState) -> str:
    """
    Routing function: determine next node based on supervisor decision.
    """
    routing = state.get("routing_decision")

    if routing:
        next_agent = routing.get("next_agent", "supervisor")

        # End processing if no more actions
        if next_agent == "supervisor" and routing.get("retry_after_seconds"):
            return "end"

        return next_agent

    return "supervisor"
```

---

## Part 8: Main Entry Point (src/main.py)

```python
"""
Main entry point: execute graph locally or in batch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import click
from sqlalchemy import create_engine

from src.graph.builder import build_graph
from src.state.schema import GraphState, Lead, LeadStatus, Source
from src.batch.processor import BatchProcessor
from src.batch.queue_manager import AgentQueueManager
from src.integrations.postgresql import init_db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """MEGA QUIXAI orchestration system."""
    pass


@cli.command()
@click.option("--lead-id", type=str, help="Lead UUID to process")
@click.option("--source", type=str, default="instagram", help="Lead source")
@click.option("--username", type=str, required=True, help="Lead username")
async def single(lead_id: str, source: str, username: str):
    """Process single lead."""

    logger.info(f"Processing single lead: {username}")

    # Create lead
    if not lead_id:
        lead_id = str(uuid.uuid4())

    lead = Lead(
        lead_id=lead_id,
        source=Source[source.upper()],
        profile_url=f"https://{source}.com/{username}",
        username=username,
        status=LeadStatus.DISCOVERED
    )

    # Initialize state
    state: GraphState = {
        "lead_id": lead_id,
        "leads": {lead_id: lead},
        "conversations": {},
        "current_agent": "supervisor",
        "message": "Single lead processing",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": None,
        "thread_id": str(uuid.uuid4()),
        "timestamp": datetime.now(),
        "metadata": {}
    }

    # Build and execute graph
    graph = build_graph()

    try:
        final_state = await graph.ainvoke(state)

        # Print results
        final_lead = final_state["leads"][lead_id]
        print(f"\n{'='*60}")
        print(f"Lead: {final_lead.username}")
        print(f"Status: {final_lead.status.value}")
        print(f"ICP Score: {final_lead.icp_score:.2%}")
        print(f"Engagement: {final_lead.engagement_score:.2%}")
        print(f"Conversion Prob: {final_lead.conversion_probability:.2%}")
        print(f"{'='*60}")

    except Exception as e:
        logger.error(f"Error processing lead: {str(e)}", exc_info=True)
        click.echo(f"Error: {str(e)}", err=True)


@cli.command()
@click.option("--batch-file", type=str, required=True, help="JSON file with leads")
@click.option("--workers", type=int, default=5, help="Parallel workers")
async def batch(batch_file: str, workers: int):
    """Process batch of leads."""

    logger.info(f"Processing batch from {batch_file}")

    # Load leads from JSON
    batch_path = Path(batch_file)
    if not batch_path.exists():
        click.echo(f"File not found: {batch_file}", err=True)
        return

    with open(batch_path) as f:
        leads_data = json.load(f)

    # Create leads
    leads = {}
    for data in leads_data:
        lead = Lead(**data)
        leads[lead.lead_id] = lead

    # Initialize batch state
    batch_id = str(uuid.uuid4())
    state: GraphState = {
        "lead_id": "",
        "leads": leads,
        "conversations": {},
        "current_agent": "supervisor",
        "message": f"Batch processing {len(leads)} leads",
        "next_agent": None,
        "routing_decision": None,
        "iteration_count": 0,
        "error_count": 0,
        "batch_id": batch_id,
        "thread_id": batch_id,
        "timestamp": datetime.now(),
        "metadata": {"lead_count": len(leads)}
    }

    # Build graph
    graph = build_graph()

    # Process batch
    processor = BatchProcessor(graph, max_workers=workers)

    async def on_complete(lead_id: str, status: str, result: dict):
        print(f"Completed {lead_id}: {status}")

    results = await processor.process_batch(
        lead_ids=list(leads.keys()),
        initial_state=state,
        callback=on_complete
    )

    # Summary
    successful = sum(1 for r in results.values() if r.get("status") == "success")
    print(f"\nBatch complete: {successful}/{len(leads)} successful")


@cli.command()
def init():
    """Initialize database schema."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")


if __name__ == "__main__":
    # For async support
    cli()
```

---

## Part 9: Batch Processing (src/batch/processor.py)

```python
"""
Batch processing: handle multiple leads in parallel.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from src.state.schema import GraphState
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BatchProcessor:
    """Process multiple leads concurrently."""

    def __init__(self, graph, max_workers: int = 5):
        self.graph = graph
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def process_batch(
        self,
        lead_ids: list[str],
        initial_state: GraphState,
        callback: Optional[Callable] = None
    ) -> dict[str, dict]:
        """
        Process multiple leads in parallel.
        """

        tasks = [
            self._process_single_lead(lead_id, initial_state, callback)
            for lead_id in lead_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect
        output = {}
        for lead_id, result in zip(lead_ids, results):
            if isinstance(result, Exception):
                output[lead_id] = {
                    "status": "error",
                    "error": str(result)
                }
            else:
                output[lead_id] = result

        return output

    async def _process_single_lead(
        self,
        lead_id: str,
        state: GraphState,
        callback: Optional[Callable]
    ) -> dict:
        """Process single lead with semaphore limit."""

        async with self.semaphore:
            try:
                # Set current lead
                state["lead_id"] = lead_id

                # Execute graph
                result = await self.graph.ainvoke(state)

                if callback:
                    await callback(lead_id, "success", result)

                return {
                    "status": "success",
                    "lead_id": lead_id,
                    "result": result
                }

            except Exception as e:
                logger.error(
                    f"Error processing lead {lead_id}: {str(e)}",
                    exc_info=True
                )

                if callback:
                    await callback(lead_id, "error", str(e))

                return {
                    "status": "error",
                    "lead_id": lead_id,
                    "error": str(e)
                }
```

---

## Part 10: Utilities & Helpers

### src/utils/logging.py

```python
"""
Structured logging setup.
"""

import logging
import sys
from typing import Optional


def get_logger(name: str) -> logging.Logger:
    """Get or create logger with structured format."""

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
```

### src/utils/error_handling.py

```python
"""
Custom exceptions and error classification.
"""


class AgentError(Exception):
    """Base agent error."""
    pass


class APIError(AgentError):
    """External API error."""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded."""
    pass


class RoutingError(AgentError):
    """Routing decision error."""
    pass


class BudgetExceededError(AgentError):
    """Monthly budget exceeded."""
    pass


def is_transient_error(error: Exception) -> bool:
    """Classify error as transient (retry-able)."""
    transient = (
        ConnectionError,
        TimeoutError,
        IOError,
        RateLimitError
    )
    return isinstance(error, transient)
```

### src/utils/parsing.py

```python
"""
Parse agent outputs into structured data.
"""

import json
from typing import Any, Optional


def safe_json_parse(text: str) -> Optional[dict]:
    """Safely extract JSON from agent output."""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try markdown code blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end].strip())
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return json.loads(text[start:end].strip())

    return None
```

---

## Part 11: PostgreSQL Integration (src/integrations/postgresql.py)

```python
"""
PostgreSQL operations: leads, conversations, logs.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.state.schema import Lead, Conversation
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LeadRepository:
    """Persist leads to PostgreSQL."""

    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)

    async def save_lead(self, lead: Lead) -> None:
        """Save or update lead."""

        session = self.Session()
        try:
            # Insert or update
            query = text("""
                INSERT INTO leads
                (lead_id, source, profile_url, username, email, phone,
                 icp_score, engagement_score, conversion_probability,
                 status, created_at, last_contacted, tags, notes)
                VALUES
                (:lead_id, :source, :profile_url, :username, :email, :phone,
                 :icp_score, :engagement_score, :conversion_probability,
                 :status, :created_at, :last_contacted, :tags, :notes)
                ON CONFLICT (lead_id) DO UPDATE SET
                    icp_score = EXCLUDED.icp_score,
                    engagement_score = EXCLUDED.engagement_score,
                    conversion_probability = EXCLUDED.conversion_probability,
                    status = EXCLUDED.status,
                    last_contacted = EXCLUDED.last_contacted,
                    tags = EXCLUDED.tags,
                    notes = EXCLUDED.notes
            """)

            session.execute(query, {
                "lead_id": lead.lead_id,
                "source": lead.source.value,
                "profile_url": lead.profile_url,
                "username": lead.username,
                "email": lead.email,
                "phone": lead.phone,
                "icp_score": lead.icp_score,
                "engagement_score": lead.engagement_score,
                "conversion_probability": lead.conversion_probability,
                "status": lead.status.value,
                "created_at": lead.created_at,
                "last_contacted": lead.last_contacted,
                "tags": lead.tags,
                "notes": lead.notes
            })

            session.commit()
            logger.info(f"Lead {lead.lead_id} saved")

        except Exception as e:
            session.rollback()
            logger.error(f"Error saving lead: {str(e)}", exc_info=True)
            raise

        finally:
            session.close()

    async def get_lead(self, lead_id: str) -> Optional[Lead]:
        """Retrieve lead by ID."""

        session = self.Session()
        try:
            query = text("SELECT * FROM leads WHERE lead_id = :lead_id")
            result = session.execute(query, {"lead_id": lead_id}).fetchone()

            if result:
                return Lead(**dict(result._mapping))

        except Exception as e:
            logger.error(f"Error fetching lead: {str(e)}", exc_info=True)

        finally:
            session.close()

        return None


def init_db() -> None:
    """Initialize database schema."""

    import os
    from sqlalchemy import create_engine

    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/langgraph")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Create tables
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS leads (
                lead_id UUID PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                profile_url TEXT NOT NULL,
                username VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                phone VARCHAR(20),
                icp_score DECIMAL(3,2),
                engagement_score DECIMAL(3,2),
                conversion_probability DECIMAL(3,2),
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE,
                last_contacted TIMESTAMP WITH TIME ZONE,
                next_follow_up TIMESTAMP WITH TIME ZONE,
                tags TEXT[],
                notes TEXT,
                created_by_agent VARCHAR(50),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        conn.commit()
        logger.info("Database schema initialized")
```

---

## Summary: File Structure

```
mega-quixai/src/
├── __init__.py
├── main.py                    # CLI entry point
├── state/
│   ├── __init__.py
│   ├── schema.py             # GraphState, Lead, Conversation
│   └── persistence.py        # Checkpoint management
├── graph/
│   ├── __init__.py
│   ├── builder.py            # Build LangGraph
│   └── router.py             # Routing logic
├── agents/
│   ├── __init__.py
│   ├── base.py               # BaseAgent class
│   ├── acquisition.py        # Lead Acquisition
│   ├── seduction.py          # Engagement & Qualification
│   ├── closing.py            # Sales Closing
│   └── supervisor.py         # Central Orchestrator
├── tools/
│   ├── __init__.py
│   ├── instagram.py
│   ├── youtube.py
│   └── rag_retriever.py
├── integrations/
│   ├── __init__.py
│   ├── postgresql.py
│   ├── langfuse_client.py
│   └── cache.py
├── batch/
│   ├── __init__.py
│   ├── processor.py          # Batch execution
│   └── queue_manager.py      # Queue management
└── utils/
    ├── __init__.py
    ├── logging.py
    ├── error_handling.py
    ├── parsing.py
    └── metrics.py
```

This skeleton provides the foundation for MEGA QUIXAI's orchestration system. Each module is designed to be:
- **Type-safe** (full Pydantic + type hints)
- **Async-ready** (asyncio patterns throughout)
- **Observable** (structured logging, LangFuse hooks)
- **Testable** (clear interfaces, dependency injection)
- **Scalable** (batch processing, parallel execution)

---

**Next Implementation Steps**:
1. Install dependencies: `pip install -e .`
2. Initialize PostgreSQL: `python scripts/init_db.py`
3. Implement agent tools (Instagram API, YouTube scraper, RAG)
4. Load DDP Garçonnière content to pgvector
5. Test single lead flow
6. Scale to batch processing
7. Monitor with LangFuse dashboarding

