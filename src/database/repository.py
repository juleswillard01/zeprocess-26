"""Repository pattern for database access."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.state.schema import Lead, LeadStatus

from .models import ConversationModel, InteractionModel, LeadModel


class LeadRepository:
    """Repository for Lead operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, lead: Lead) -> LeadModel:
        """Create a new lead in the database."""
        db_lead = LeadModel(
            lead_id=lead.lead_id,
            source=lead.source.value,
            profile_url=lead.profile_url,
            username=lead.username,
            email=lead.email,
            phone=lead.phone,
            icp_score=lead.icp_score,
            engagement_score=lead.engagement_score,
            conversion_probability=lead.conversion_probability,
            status=lead.status.value,
            tags=lead.tags,
            notes=lead.notes,
            metadata=lead.metadata,
        )
        self.session.add(db_lead)
        await self.session.commit()
        await self.session.refresh(db_lead)
        return db_lead

    async def get_by_id(self, lead_id: str) -> LeadModel | None:
        """Retrieve a lead by ID."""
        result = await self.session.execute(select(LeadModel).where(LeadModel.lead_id == lead_id))
        return result.scalars().first()

    async def get_by_username(self, username: str) -> LeadModel | None:
        """Retrieve a lead by username."""
        result = await self.session.execute(select(LeadModel).where(LeadModel.username == username))
        return result.scalars().first()

    async def update(self, lead_id: str, updates: dict[str, Any]) -> LeadModel | None:
        """Update a lead."""
        db_lead = await self.get_by_id(lead_id)
        if not db_lead:
            return None

        for key, value in updates.items():
            if hasattr(db_lead, key):
                setattr(db_lead, key, value)

        await self.session.commit()
        await self.session.refresh(db_lead)
        return db_lead

    async def list_by_status(self, status: LeadStatus, limit: int = 100) -> list[LeadModel]:
        """List leads by status."""
        result = await self.session.execute(
            select(LeadModel).where(LeadModel.status == status.value).limit(limit)
        )
        return result.scalars().all()

    async def delete(self, lead_id: str) -> bool:
        """Delete a lead."""
        db_lead = await self.get_by_id(lead_id)
        if not db_lead:
            return False

        await self.session.delete(db_lead)
        await self.session.commit()
        return True


class ConversationRepository:
    """Repository for Conversation operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, conversation_id: str, lead_id: str, agent_name: str
    ) -> ConversationModel:
        """Create a new conversation."""
        db_conv = ConversationModel(
            conversation_id=conversation_id,
            lead_id=lead_id,
            agent_name=agent_name,
        )
        self.session.add(db_conv)
        await self.session.commit()
        await self.session.refresh(db_conv)
        return db_conv

    async def get_by_id(self, conversation_id: str) -> ConversationModel | None:
        """Retrieve a conversation by ID."""
        result = await self.session.execute(
            select(ConversationModel).where(ConversationModel.conversation_id == conversation_id)
        )
        return result.scalars().first()

    async def add_message(
        self, conversation_id: str, message: dict[str, Any]
    ) -> ConversationModel | None:
        """Add a message to a conversation."""
        db_conv = await self.get_by_id(conversation_id)
        if not db_conv:
            return None

        if db_conv.messages is None:
            db_conv.messages = []

        db_conv.messages.append(message)
        await self.session.commit()
        await self.session.refresh(db_conv)
        return db_conv

    async def update_token_count(
        self, conversation_id: str, token_count: int
    ) -> ConversationModel | None:
        """Update token count for a conversation."""
        db_conv = await self.get_by_id(conversation_id)
        if not db_conv:
            return None

        db_conv.total_tokens += token_count
        await self.session.commit()
        await self.session.refresh(db_conv)
        return db_conv


class InteractionRepository:
    """Repository for Interaction operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        interaction_id: str,
        lead_id: str,
        interaction_type: str,
        agent_name: str,
        result: str,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionModel:
        """Create a new interaction record."""
        db_interaction = InteractionModel(
            interaction_id=interaction_id,
            lead_id=lead_id,
            interaction_type=interaction_type,
            agent_name=agent_name,
            result=result,
            metadata=metadata or {},
        )
        self.session.add(db_interaction)
        await self.session.commit()
        await self.session.refresh(db_interaction)
        return db_interaction

    async def get_by_lead(self, lead_id: str, limit: int = 100) -> list[InteractionModel]:
        """Get all interactions for a lead."""
        result = await self.session.execute(
            select(InteractionModel).where(InteractionModel.lead_id == lead_id).limit(limit)
        )
        return result.scalars().all()
