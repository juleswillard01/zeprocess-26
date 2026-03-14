"""Seduction/Engagement Agent implementation (RAG-powered)."""

from __future__ import annotations

import logging
from typing import Any

from src.state.schema import GraphState, LeadStatus

from .base import BaseAgent

logger = logging.getLogger(__name__)


class SeductionAgent(BaseAgent):
    """Agent responsible for building rapport and qualifying leads through engagement."""

    def __init__(self) -> None:
        super().__init__("seduction")

    async def execute(self, state: GraphState) -> GraphState:
        """Execute seduction/engagement workflow.

        Steps:
        1. Retrieve RAG context from knowledge base
        2. Generate personalized response (Sonnet)
        3. Handle lead objections
        4. Qualify for closing (>0.7 score)
        5. Route to closing or recycle
        """
        lead = state.lead

        # Step 1: Retrieve RAG context
        rag_context = await self._retrieve_rag_context(lead)

        # Step 2: Generate personalized response
        response_message = await self._generate_response(lead, rag_context)
        state.messages.append(
            {
                "role": "agent",
                "content": response_message,
                "agent_name": "seduction",
            }
        )

        # Step 3: Handle objections (if present in conversation)
        if state.messages:
            last_lead_message = await self._get_last_lead_message(state.messages)
            if last_lead_message:
                objections = await self._detect_objections(last_lead_message)
                if objections:
                    objection_response = await self._handle_objections(objections, rag_context)
                    state.messages.append(
                        {
                            "role": "agent",
                            "content": objection_response,
                            "agent_name": "seduction",
                        }
                    )

        # Step 4: Score engagement and qualification
        engagement_score = await self._score_engagement(state.messages)
        lead.engagement_score = engagement_score

        # Step 5: Decide routing
        if engagement_score >= 0.7:
            lead.status = LeadStatus.QUALIFIED
            state.routing_decision = "closing"
        else:
            lead.status = LeadStatus.ENGAGED
            state.routing_decision = "continue_seduction"

        state = await self._update_state(
            state,
            {
                "engagement_score": engagement_score,
                "rag_context": rag_context,
                "routing_decision": state.routing_decision,
            },
        )

        await self._log_execution(lead.lead_id, state.routing_decision)
        return state

    async def _retrieve_rag_context(self, lead: Any) -> dict[str, Any]:
        """Retrieve relevant coaching content from RAG.

        Returns contextualized training material based on lead's interests.
        """
        # TODO: Integrate with pgvector RAG
        # For now, return mock context
        return {
            "relevant_scripts": [
                "Script about building confidence in dating",
                "Framework for handling common objections",
            ],
            "coaching_principles": [
                "Lead with value, not pressure",
                "Build genuine rapport first",
            ],
            "testimonials": [
                "Success story from similar client",
            ],
        }

    async def _generate_response(self, lead: Any, rag_context: dict[str, Any]) -> str:
        """Generate personalized response using RAG context.

        Uses Sonnet for response generation (0.4-0.6 complexity).
        """
        # TODO: Integrate with Claude API (Sonnet)
        # For now, return template based on RAG context
        return (
            f"Thanks for the interest, {lead.username}! "
            "A lot of guys I work with struggle with the same thing. "
            "The key is understanding the fundamentals. "
            "Have you worked on confidence-building before?"
        )

    async def _get_last_lead_message(self, messages: list[dict[str, Any]]) -> str:
        """Extract the last message from the lead."""
        for message in reversed(messages):
            if message.get("role") == "lead":
                return message.get("content", "")
        return ""

    async def _detect_objections(self, message: str) -> list[str]:
        """Detect common objections in lead's message.

        Uses Haiku for classification (0.1-0.3 complexity).
        """
        # TODO: Integrate with Claude API (Haiku)
        # Simple pattern matching for now
        objections = []

        objection_patterns = {
            "price": ["expensive", "cost", "price", "afford"],
            "timing": ["timing", "now", "busy", "later", "time", "week"],
            "doubt": ["sure", "not sure", "hesitant", "worried"],
            "competition": ["other", "competitor", "different", "similar"],
        }

        message_lower = message.lower()
        for objection_type, patterns in objection_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                objections.append(objection_type)

        return objections

    async def _handle_objections(self, objections: list[str], rag_context: dict[str, Any]) -> str:
        """Generate response handling specific objections.

        Uses Sonnet for reasoning (0.4-0.6 complexity).
        """
        # TODO: Integrate with Claude API (Sonnet)
        if "price" in objections:
            return "I get that. Most guys wonder about ROI. Let me be direct: this is an investment in yourself. What value would a confident dating life be worth?"
        elif "timing" in objections:
            return "Totally understand you're busy. Most successful guys are. That's why they start now - it saves time long-term."
        elif "doubt" in objections:
            return "That's healthy to be cautious. Let me ask: what would it take for you to feel confident about this step?"

        return "Great question. Tell me more about what's on your mind."

    async def _score_engagement(self, messages: list[dict[str, Any]]) -> float:
        """Score engagement level based on conversation.

        Higher score = better fit for closing agent.
        """
        # TODO: Use Claude API for sophisticated scoring
        # For now, simple heuristic
        lead_message_count = sum(1 for m in messages if m.get("role") == "lead")
        agent_message_count = sum(1 for m in messages if m.get("role") == "agent")

        # Score based on back-and-forth
        if lead_message_count == 0:
            return 0.2
        if agent_message_count == 0:
            return 0.3

        score = min(0.9, 0.3 + (lead_message_count * 0.15))
        return min(1.0, score)
