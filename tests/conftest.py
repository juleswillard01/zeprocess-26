"""Pytest fixtures and configuration for Phase 1 orchestration."""

from __future__ import annotations

import pytest

from src.state.schema import ConversationState, GraphState, Lead, Source


@pytest.fixture
def sample_lead() -> Lead:
    """Create a sample lead for testing."""
    return Lead(
        lead_id="test-lead-001",
        source=Source.INSTAGRAM,
        profile_url="https://instagram.com/test_user",
        username="test_user",
        email="test@example.com",
        metadata={"age": 28, "interests": ["dating", "self-improvement"]},
    )


@pytest.fixture
def sample_conversation_state(sample_lead: Lead) -> ConversationState:
    """Create a sample conversation state."""
    return ConversationState(
        conversation_id="conv-001",
        lead_id=sample_lead.lead_id,
        messages=[],
    )


@pytest.fixture
def sample_graph_state(
    sample_lead: Lead, sample_conversation_state: ConversationState
) -> GraphState:
    """Create a sample graph state."""
    return GraphState(
        lead=sample_lead,
        conversation=sample_conversation_state,
        current_agent="supervisor",
        messages=[],
    )
