"""SQLAlchemy models for MEGA QUIXAI database."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

if TYPE_CHECKING:
    pass

Base = declarative_base()


class LeadModel(Base):
    """ORM model for leads."""

    __tablename__ = "leads"

    lead_id = Column(String(36), primary_key=True, index=True)
    source = Column(String(50), nullable=False)
    profile_url = Column(String(500), nullable=False)
    username = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True)
    # Scoring
    icp_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    conversion_probability = Column(Float, default=0.0)
    # Status tracking
    status = Column(String(50), default="discovered", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_contacted = Column(DateTime, nullable=True)
    next_follow_up = Column(DateTime, nullable=True)
    # Context
    tags = Column(JSON, default=[])
    notes = Column(Text, default="")
    conversation_history_id = Column(String(36), nullable=True)
    # Metadata
    metadata = Column(JSON, default={})

    conversations = relationship(
        "ConversationModel", back_populates="lead", cascade="all, delete-orphan"
    )
    interactions = relationship(
        "InteractionModel", back_populates="lead", cascade="all, delete-orphan"
    )


class ConversationModel(Base):
    """ORM model for conversations."""

    __tablename__ = "conversations"

    conversation_id = Column(String(36), primary_key=True, index=True)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    messages = Column(JSON, default=[])  # List of message dicts
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default={})

    lead = relationship("LeadModel", back_populates="conversations")


class InteractionModel(Base):
    """ORM model for interactions (events)."""

    __tablename__ = "interactions"

    interaction_id = Column(String(36), primary_key=True, index=True)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)
    interaction_type = Column(String(50), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    result = Column(String(50), nullable=False)  # success, failure, escalated
    metadata = Column(JSON, default={})

    lead = relationship("LeadModel", back_populates="interactions")


class MetricsModel(Base):
    """ORM model for time-series metrics."""

    __tablename__ = "metrics"

    metric_id = Column(String(36), primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    value = Column(Float, nullable=False)
    tags = Column(JSON, default={})  # For dimensional queries


class AuditLogModel(Base):
    """ORM model for immutable audit logs."""

    __tablename__ = "audit_logs"

    log_id = Column(String(36), primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    lead_id = Column(String(36), nullable=True, index=True)
    data = Column(JSON, nullable=False)
    result = Column(String(50), nullable=False)  # approved, rejected, escalated
