"""
Global state definitions for LangGraph orchestration.

Defines all Pydantic models for leads, conversations, and the main orchestration state.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
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
    email: str | None = None
    phone: str | None = None
    # Scoring (0-1)
    icp_score: float = Field(ge=0, le=1, default=0.0)
    engagement_score: float = Field(ge=0, le=1, default=0.0)
    conversion_probability: float = Field(ge=0, le=1, default=0.0)
    # Status tracking
    status: LeadStatus = LeadStatus.DISCOVERED
    created_at: datetime = Field(default_factory=datetime.now)
    last_contacted: datetime | None = None
    next_follow_up: datetime | None = None
    # Context
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    conversation_history_id: str | None = None
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
                "tags": ["dating_anxiety", "self_improvement"],
            }
        }


class ConversationMessage(BaseModel):
    """Single message in a conversation."""

    role: Literal["agent", "lead", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_name: Literal["acquisition", "seduction", "closing"]
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0


class ConversationState(BaseModel):
    """Conversation history and context."""

    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str
    messages: list[ConversationMessage] = Field(default_factory=list)
    total_tokens: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphState(BaseModel):
    """Main orchestration state for the LangGraph."""

    lead: Lead
    conversation: ConversationState
    current_agent: Literal["acquisition", "seduction", "closing", "supervisor"]
    messages: list[dict[str, Any]] = Field(default_factory=list)
    # Agent-specific context
    acquisition_context: dict[str, Any] = Field(default_factory=dict)
    seduction_context: dict[str, Any] = Field(default_factory=dict)
    closing_context: dict[str, Any] = Field(default_factory=dict)
    # Routing decisions
    routing_decision: str | None = None
    should_escalate: bool = False
    escalation_reason: str | None = None
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
