"""Agent CLOSING state machine and dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


@dataclass
class ProspectProfile:
    """Lead data from Agent SÉDUCTION."""

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
    """Single message in conversation."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    source: str = "manual"  # manual | node_init | node_objection_handling


@dataclass
class Objection:
    """Tracked objection."""

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
    """Pricing offer."""

    price: float
    description: str
    stripe_session_id: str
    stripe_url: str
    created_at: datetime
    expires_at: datetime


@dataclass
class ClosingState:
    """LangGraph state for Agent CLOSING."""

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
        "archived",
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
