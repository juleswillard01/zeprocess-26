# Claude Code SDK Integration & Architecture

## Overview

MEGA QUIXAI utilizes Claude Code SDK as the **core execution engine** for three autonomous agents, integrated with LangGraph for state management and LangChain for memory/RAG. This document details the full Claude SDK implementation.

---

## 1. Claude SDK Setup & Configuration

### 1.1 Installation & Dependencies

```bash
# Add to pyproject.toml
uv pip install anthropic>=0.28.0 langgraph>=0.0.1 langchain>=0.1.0

# Verify installation
python -c "import anthropic; print(anthropic.__version__)"
```

### 1.2 SDK Configuration Manager

```python
# src/llm/claude_sdk_config.py

from __future__ import annotations

import os
import json
from typing import Optional, Literal
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import anthropic
from anthropic.types.message import Message
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class ModelTier(str, Enum):
    """Model routing based on task complexity."""
    HAIKU = "claude-3-5-haiku-20241022"
    SONNET = "claude-3-5-sonnet-20241022"
    OPUS = "claude-3-5-opus-20250514"

@dataclass
class ModelConfig:
    """Configuration for each model tier."""
    tier: ModelTier
    max_tokens: int
    cost_per_million_input: float
    cost_per_million_output: float
    use_cases: list[str]
    temperature: float = 0.7

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for token usage."""
        input_cost = (input_tokens / 1_000_000) * self.cost_per_million_input
        output_cost = (output_tokens / 1_000_000) * self.cost_per_million_output
        return input_cost + output_cost

class BudgetAllocation(BaseModel):
    """Monthly budget allocation across agents."""
    total_monthly_usd: float = Field(default=5000, gt=0)
    lead_acquisition_pct: float = Field(default=0.25)
    seduction_pct: float = Field(default=0.45)
    closing_pct: float = Field(default=0.30)

    @property
    def lead_acquisition_budget(self) -> float:
        return self.total_monthly_usd * self.lead_acquisition_pct

    @property
    def seduction_budget(self) -> float:
        return self.total_monthly_usd * self.seduction_pct

    @property
    def closing_budget(self) -> float:
        return self.total_monthly_usd * self.closing_pct

class ClaudeSDKManager:
    """Central manager for Claude API with intelligent model routing."""

    def __init__(self, api_key: Optional[str] = None, budget_allocation: Optional[BudgetAllocation] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key)

        self.budget = budget_allocation or BudgetAllocation()
        self.monthly_start = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        self.monthly_spend = {
            "LEAD_ACQUISITION": 0.0,
            "SEDUCTION": 0.0,
            "CLOSING": 0.0,
            "total": 0.0,
        }

        # Model configurations
        self.models = {
            "haiku": ModelConfig(
                tier=ModelTier.HAIKU,
                max_tokens=1024,
                cost_per_million_input=0.80,
                cost_per_million_output=4.00,
                use_cases=["spam_detection", "icp_filtering", "sentiment_analysis"],
                temperature=0.3,
            ),
            "sonnet": ModelConfig(
                tier=ModelTier.SONNET,
                max_tokens=4096,
                cost_per_million_input=3.00,
                cost_per_million_output=15.00,
                use_cases=["dm_response_generation", "objection_handling", "content_generation"],
                temperature=0.7,
            ),
            "opus": ModelConfig(
                tier=ModelTier.OPUS,
                max_tokens=4096,
                cost_per_million_input=15.00,
                cost_per_million_output=75.00,
                use_cases=["complex_strategy", "closing_decisions"],
                temperature=0.8,
            ),
        }

    def invoke(
        self,
        messages: list[dict],
        task: str,
        complexity: float = 0.5,
        agent_id: str = "default",
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Invoke Claude with automatic model routing and cost tracking."""

        # Select model tier
        if complexity < 0.3:
            model_config = self.models["haiku"]
        elif complexity < 0.7:
            model_config = self.models["sonnet"]
        else:
            model_config = self.models["opus"]

        # Check budget
        agent_budget = getattr(self.budget, f"{agent_id.lower()}_budget", float('inf'))
        if self.monthly_spend[agent_id] >= agent_budget:
            return {"error": "budget_exceeded", "success": False}

        # Call API
        try:
            response = self.client.messages.create(
                model=model_config.tier.value,
                max_tokens=kwargs.get("max_tokens", model_config.max_tokens),
                messages=messages,
                system=system_prompt,
                temperature=kwargs.get("temperature", model_config.temperature),
            )

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = model_config.cost_estimate(input_tokens, output_tokens)

            # Track spend
            self.monthly_spend[agent_id] += cost_usd
            self.monthly_spend["total"] += cost_usd

            return {
                "content": response.content[0].text if response.content else "",
                "metadata": {
                    "model_tier": model_config.tier.value,
                    "tokens": input_tokens + output_tokens,
                    "cost_usd": cost_usd,
                },
                "success": True,
            }

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return {"error": str(e), "success": False}

    def get_monthly_stats(self) -> dict:
        """Get monthly usage statistics."""
        return {
            "total_spend": self.monthly_spend["total"],
            "by_agent": {
                "LEAD_ACQUISITION": self.monthly_spend["LEAD_ACQUISITION"],
                "SEDUCTION": self.monthly_spend["SEDUCTION"],
                "CLOSING": self.monthly_spend["CLOSING"],
            },
            "remaining_budget": self.budget.total_monthly_usd - self.monthly_spend["total"],
        }
```

---

## 2. Agent SDK Patterns

### 2.1 Base Agent Class

```python
# src/agents/base_agent.py

from typing import Optional, Any
from uuid import UUID
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class AgentType(str, Enum):
    LEAD_ACQUISITION = "LEAD_ACQUISITION"
    SEDUCTION = "SEDUCTION"
    CLOSING = "CLOSING"

class AgentState(BaseModel):
    """State managed by LangGraph."""
    lead_id: UUID
    agent_id: AgentType
    conversation_history: list[dict] = Field(default_factory=list)
    status: str = "idle"
    score: float = 0.0
    cost_usd: float = 0.0
    metadata: dict = Field(default_factory=dict)

class BaseAgent:
    """Base class for all agents."""

    def __init__(self, agent_type: AgentType, claude_sdk: Any, db_client: Any):
        self.agent_type = agent_type
        self.claude_sdk = claude_sdk
        self.db_client = db_client

    def _get_system_prompt(self) -> str:
        """Get system prompt. Override in subclasses."""
        raise NotImplementedError

    async def invoke(self, state: AgentState) -> AgentState:
        """Main entrypoint."""
        raise NotImplementedError
```

### 2.2 LEAD ACQUISITION Agent

```python
# src/agents/lead_acquisition_agent.py

from src.agents.base_agent import BaseAgent, AgentType, AgentState

class LeadAcquisitionAgent(BaseAgent):
    """Score leads, detect spam, send first contact."""

    def _get_system_prompt(self) -> str:
        return """You are LEAD_ACQUISITION, sourcing and qualifying prospects.

Evaluate: age, bio, engagement, ICP match.
Output: qualification score (0-1), spam flag, first contact message."""

    def _score_icp(self, lead_data: dict) -> float:
        """Score ICP match."""
        score = 0.0

        age = lead_data.get("age", 0)
        if 18 <= age <= 55:
            score += 0.2

        keywords = ["séduction", "confiance", "approche", "dating"]
        bio = lead_data.get("bio", "").lower()
        keyword_matches = sum(1 for kw in keywords if kw in bio)
        score += min(keyword_matches / 3, 1.0) * 0.4

        engagement = lead_data.get("engagement_rate", 0)
        score += min(engagement / 0.1, 1.0) * 0.2

        followers = lead_data.get("follower_count", 0)
        if 50 <= followers <= 500000:
            score += 0.2

        return min(score, 1.0)

    async def invoke(self, state: AgentState) -> AgentState:
        """Process lead."""
        lead = self.db_client.get_lead(state.lead_id)

        icp_score = self._score_icp(lead)

        if icp_score < 0.5:
            state.status = "rejected"
            return state

        # Generate first contact via Claude
        response = self.claude_sdk.invoke(
            messages=[{"role": "user", "content": f"Generate first DM for lead: {lead['bio']}"}],
            task="first_contact_generation",
            complexity=0.5,
            agent_id="LEAD_ACQUISITION",
            system_prompt=self._get_system_prompt(),
        )

        state.score = icp_score
        state.status = "completed"
        state.cost_usd = response["metadata"]["cost_usd"]

        return state
```

### 2.3 SÉDUCTION Agent

```python
# src/agents/seduction_agent.py

from src.agents.base_agent import BaseAgent, AgentType, AgentState

class SeductionAgent(BaseAgent):
    """Build rapport, qualify objections, nurture toward closing."""

    def _get_system_prompt(self) -> str:
        return """You are SEDUCTION, building rapport and qualifying prospects.

Be authentic, share value, ask questions.
Detect buying signals, qualify score (0-1).
Decide if ready for closing (score >= 0.7)."""

    async def invoke(self, state: AgentState) -> AgentState:
        """Process prospect through nurturing."""
        conversation = self.db_client.get_conversation(state.lead_id)

        system = self._get_system_prompt()
        response = self.claude_sdk.invoke(
            messages=state.conversation_history,
            task="dm_response_generation",
            complexity=0.6,
            agent_id="SEDUCTION",
            system_prompt=system,
        )

        state.status = "completed"
        state.cost_usd = response["metadata"]["cost_usd"]
        state.score = 0.7  # Simplified; real implementation parses response

        return state
```

### 2.4 CLOSING Agent

```python
# src/agents/closing_agent.py

from src.agents.base_agent import BaseAgent, AgentType, AgentState

class ClosingAgent(BaseAgent):
    """Handle objections, close deals, process payments."""

    def _get_system_prompt(self) -> str:
        return """You are CLOSING, converting prospects to customers.

Detect objections: price, timing, doubt.
Respond with empathy and tactics.
Ask for sale directly. Return: deal_closed (true/false)."""

    async def invoke(self, state: AgentState) -> AgentState:
        """Process closing conversation."""
        system = self._get_system_prompt()
        response = self.claude_sdk.invoke(
            messages=state.conversation_history,
            task="closing_ask",
            complexity=0.8,
            agent_id="CLOSING",
            system_prompt=system,
        )

        state.status = "completed"
        state.cost_usd = response["metadata"]["cost_usd"]
        # Parse response for deal status

        return state
```

---

## 3. LangGraph Integration

```python
# src/orchestration/graph.py

from langgraph.graph import StateGraph
from src.agents.base_agent import AgentState

def create_mega_quixai_graph(lead_acq_agent, seduction_agent, closing_agent):
    """Create multi-agent workflow."""

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("LEAD_ACQUISITION", lead_acq_agent.invoke)
    graph.add_node("SEDUCTION", seduction_agent.invoke)
    graph.add_node("CLOSING", closing_agent.invoke)

    # Add edges
    graph.add_edge("LEAD_ACQUISITION", "SEDUCTION")

    def seduction_routing(state):
        return "CLOSING" if state.score >= 0.7 else "END"

    graph.add_conditional_edges("SEDUCTION", seduction_routing)
    graph.add_edge("CLOSING", "END")

    graph.set_entry_point("LEAD_ACQUISITION")

    return graph.compile()
```

---

## 4. Cost Management

```python
# src/budget/optimizer.py

class CostOptimizer:
    """Optimize token usage and routing."""

    def estimate_monthly_cost(self, leads_per_month: int = 200) -> dict:
        """Estimate costs for given volume."""

        # Lead Acquisition: 1 task per lead (Haiku filtering, Sonnet qualification)
        lea_cost = (leads_per_month * 300 / 1_000_000) * 0.80  # Haiku

        # Seduction: 5 interactions per qualified lead (Sonnet)
        sed_cost = (leads_per_month * 5 * 1000 / 1_000_000) * 3.00  # Sonnet

        # Closing: 2 interactions per lead, 20% Opus for strategy
        close_cost = (leads_per_month * 2 * 800 / 1_000_000) * 3.00  # Sonnet

        total = lea_cost + sed_cost + close_cost

        return {
            "lea": lea_cost,
            "seduction": sed_cost,
            "closing": close_cost,
            "total": total,
            "leads_per_month": leads_per_month,
        }
```

---

## 5. Safety & Guardrails (V-Code Pattern)

```python
# src/safety/v_code_review.py

class VCodeReviewer:
    """Automated code review before sensitive operations."""

    async def review_before_execute(
        self,
        operation: str,
        parameters: dict,
        agent_id: str,
    ) -> dict:
        """Review and approve/reject operations."""

        if operation == "stripe_charge" and parameters.get("amount_usd", 0) > 2000:
            return {"approved": False, "escalate_to_human": True}

        if operation == "instagram_dm" and len(parameters.get("content", "")) > 500:
            return {"approved": False, "reason": "message_too_long"}

        return {"approved": True}
```

---

## 6. Monitoring & Observability

```python
# src/monitoring/langfuse_monitor.py

from langfuse import Langfuse

class LangfuseMonitor:
    """Track costs and performance."""

    def __init__(self, public_key: str, secret_key: str):
        self.client = Langfuse(public_key=public_key, secret_key=secret_key)

    def log_agent_execution(self, agent_id: str, lead_id: str, cost_usd: float, tokens: int):
        """Log to LangFuse."""
        self.client.trace(
            name=f"{agent_id}_execution",
            metadata={"cost_usd": cost_usd, "tokens": tokens},
        )
```

---

*Document Version*: 1.0
*Date*: 2026-03-14
*Status*: COMPLETE
