"""Pytest fixtures and configuration."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.closing.state_machine import ClosingState, Message, ProspectProfile


@pytest.fixture
def mock_prospect() -> ProspectProfile:
    """Create mock prospect for testing."""
    return ProspectProfile(
        id="prospect_123",
        name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        whatsapp_id="1234567890",
        segment="high_value",
        pain_points=["scaling", "customer retention"],
        budget_range="$50k-100k",
        qualification_score=0.85,
        created_at=datetime.now(),
        notes="Test prospect",
    )


@pytest.fixture
def mock_closing_state(mock_prospect: ProspectProfile) -> ClosingState:
    """Create mock closing state for testing."""
    return ClosingState(
        prospect=mock_prospect,
        messages=[
            Message(
                role="assistant",
                content="Hi John, interested in learning more?",
                timestamp=datetime.now(),
            )
        ],
        conversation_turns=1,
        stage="opening_sent",
    )


@pytest.fixture
async def mock_llm_interface() -> AsyncMock:
    """Create mock LLM interface."""
    mock = AsyncMock()
    mock.generate.return_value = ("Generated response", 100, 0.0003)
    mock.classify.return_value = "price"
    mock.extract_objection.return_value = {
        "type": "price",
        "severity": 0.8,
        "key_phrase": "Too expensive",
    }
    mock.generate_counter_argument.return_value = "Here's why this investment is worth it..."
    return mock


@pytest.fixture
async def mock_rag_interface() -> AsyncMock:
    """Create mock RAG interface."""
    mock = AsyncMock()
    mock.search.return_value = [
        {
            "id": "1",
            "source": "training_video_1",
            "content": "Pricing strategy for high-value customers",
            "similarity": 0.92,
            "metadata": {"segment": "high_value"},
        }
    ]
    return mock


@pytest.fixture
async def mock_payment_manager() -> AsyncMock:
    """Create mock payment manager."""
    mock = AsyncMock()
    mock.create_checkout_session.return_value = (
        "session_123",
        "https://checkout.stripe.com/pay/session_123",
    )
    mock.verify_payment.return_value = {
        "status": "paid",
        "session_id": "session_123",
        "amount_usd": 50.0,
        "payment_id": "pi_123",
    }
    return mock
