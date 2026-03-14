"""Lead Acquisition Agent implementation."""

from __future__ import annotations

import logging
from typing import Any

from src.state.schema import GraphState, LeadStatus

from .base import BaseAgent

logger = logging.getLogger(__name__)


class LeadAcquisitionAgent(BaseAgent):
    """Agent responsible for sourcing and qualifying leads."""

    def __init__(self) -> None:
        super().__init__("acquisition")

    async def execute(self, state: GraphState) -> GraphState:
        """Execute lead acquisition workflow.

        Steps:
        1. Score ICP match (Haiku)
        2. Detect spam/low-quality leads
        3. Generate first contact message (Sonnet)
        4. Prepare handoff to seduction agent
        """
        lead = state.lead

        # Step 1: Score ICP match
        icp_score = await self._score_icp(lead.metadata)
        lead.icp_score = icp_score

        # Step 2: Detect spam
        is_spam = await self._check_spam(lead)
        if is_spam:
            lead.status = LeadStatus.LOST
            state = await self._update_state(state, {"spam_detected": True})
            await self._log_execution(lead.lead_id, "spam_detected")
            return state

        # Step 3: Generate first contact message
        first_message = await self._generate_first_contact(lead)
        state.messages.append(
            {
                "role": "agent",
                "content": first_message,
                "agent_name": "acquisition",
            }
        )

        # Step 4: Update lead status and prepare handoff
        lead.status = LeadStatus.CONTACTED
        state = await self._update_state(
            state,
            {
                "icp_score": icp_score,
                "first_message": first_message,
                "ready_for_seduction": icp_score >= 0.5,
            },
        )

        await self._log_execution(lead.lead_id, "success")
        return state

    async def _score_icp(self, profile_data: dict[str, Any]) -> float:
        """Score lead against Ideal Customer Profile (ICP).

        Returns a score between 0 and 1 indicating fit.
        Uses Haiku model for cost efficiency (0.1-0.3 complexity).
        """
        # TODO: Integrate with Claude API (Haiku)
        # For now, return a mock score based on profile data
        age = profile_data.get("age", 0)
        interest_keywords = profile_data.get("interests", [])

        # Simple heuristic scoring
        score = 0.0

        # Age scoring (18-45 is ideal)
        if 18 <= age <= 45:
            score += 0.3
        elif 16 <= age <= 50:
            score += 0.15

        # Interest keyword scoring
        target_interests = {
            "dating",
            "self-improvement",
            "confidence",
            "personal-development",
        }
        matching_interests = set(interest_keywords) & target_interests
        score += min(0.5, len(matching_interests) * 0.15)

        return min(1.0, score)

    async def _check_spam(self, lead: Any) -> bool:
        """Detect spam or low-quality leads.

        Uses Haiku for classification (0.1-0.3 complexity).
        """
        # TODO: Integrate with Claude API (Haiku)
        # For now, simple heuristics
        username = lead.username.lower()

        # Spam patterns (only obvious spam indicators)
        spam_patterns = ["bot", "spam", "fake", "xxx", "porn"]
        if any(pattern in username for pattern in spam_patterns):
            return True

        # Minimum username length
        if len(username) < 2:
            return True

        return False

    async def _generate_first_contact(self, lead: Any) -> str:
        """Generate personalized first contact message.

        Uses Sonnet for message generation (0.4-0.6 complexity).
        """
        # TODO: Integrate with Claude API (Sonnet)
        # For now, return template message
        return (
            f"Hi {lead.username}!\n\n"
            "I noticed your interest in personal development. "
            "I've been working with guys just like you who want to level up. "
            "Worth a quick chat?\n\n"
            "Best,\nCoach"
        )
