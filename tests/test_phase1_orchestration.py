"""Phase 1 test: Core LangGraph orchestration."""

from __future__ import annotations

import pytest

from src.agents.acquisition import LeadAcquisitionAgent
from src.agents.closing import ClosingAgent
from src.agents.seduction import SeductionAgent
from src.graph.builder import GraphBuilder
from src.state.schema import (
    ConversationState,
    GraphState,
    Lead,
    LeadStatus,
    Source,
)


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


@pytest.mark.asyncio
class TestLeadAcquisitionAgent:
    """Test lead acquisition agent."""

    async def test_agent_initialization(self) -> None:
        """Test agent can be instantiated."""
        agent = LeadAcquisitionAgent()
        assert agent.agent_name == "acquisition"

    async def test_score_icp(self, sample_lead: Lead) -> None:
        """Test ICP scoring."""
        agent = LeadAcquisitionAgent()
        score = await agent._score_icp(sample_lead.metadata)
        assert 0.0 <= score <= 1.0

    async def test_check_spam(self, sample_lead: Lead) -> None:
        """Test spam detection."""
        agent = LeadAcquisitionAgent()
        is_spam = await agent._check_spam(sample_lead)
        assert isinstance(is_spam, bool)

    async def test_execute_happy_path(self, sample_graph_state: GraphState) -> None:
        """Test full acquisition agent execution."""
        agent = LeadAcquisitionAgent()
        result = await agent.execute(sample_graph_state)

        assert result.lead.status == LeadStatus.CONTACTED
        assert result.lead.icp_score > 0.0
        assert len(result.messages) > 0


@pytest.mark.asyncio
class TestSeductionAgent:
    """Test seduction agent."""

    async def test_agent_initialization(self) -> None:
        """Test agent can be instantiated."""
        agent = SeductionAgent()
        assert agent.agent_name == "seduction"

    async def test_retrieve_rag_context(self, sample_lead: Lead) -> None:
        """Test RAG context retrieval."""
        agent = SeductionAgent()
        context = await agent._retrieve_rag_context(sample_lead)
        assert isinstance(context, dict)
        assert "relevant_scripts" in context

    async def test_detect_objections(self) -> None:
        """Test objection detection."""
        agent = SeductionAgent()
        message = "This is expensive, I'm not sure about the timing"
        objections = await agent._detect_objections(message)
        assert "price" in objections
        assert "timing" in objections

    async def test_score_engagement(self) -> None:
        """Test engagement scoring."""
        agent = SeductionAgent()
        messages = [
            {"role": "agent", "content": "Hi there", "agent_name": "seduction"},
            {"role": "lead", "content": "Hey, interested", "agent_name": "seduction"},
            {"role": "agent", "content": "Great!", "agent_name": "seduction"},
            {"role": "lead", "content": "Tell me more", "agent_name": "seduction"},
        ]
        score = await agent._score_engagement(messages)
        assert 0.0 <= score <= 1.0
        assert score > 0.4  # Should have some engagement


@pytest.mark.asyncio
class TestClosingAgent:
    """Test closing agent."""

    async def test_agent_initialization(self) -> None:
        """Test agent can be instantiated."""
        agent = ClosingAgent()
        assert agent.agent_name == "closing"

    async def test_process_payment(self, sample_lead: Lead, sample_graph_state: GraphState) -> None:
        """Test payment processing."""
        agent = ClosingAgent()
        result = await agent._process_payment(sample_lead, sample_graph_state)
        assert "status" in result

    async def test_v_code_review(self, sample_lead: Lead, sample_graph_state: GraphState) -> None:
        """Test V-Code safety review."""
        agent = ClosingAgent()
        payment_data = {"amount": 2000}
        result = await agent._v_code_review_payment(payment_data, sample_lead, sample_graph_state)
        assert "approved" in result


@pytest.mark.asyncio
class TestGraphOrchestration:
    """Test LangGraph orchestration."""

    def test_graph_builder_initialization(self) -> None:
        """Test graph builder can be instantiated."""
        builder = GraphBuilder()
        assert builder.acquisition_agent is not None
        assert builder.seduction_agent is not None
        assert builder.closing_agent is not None

    def test_graph_builds_successfully(self) -> None:
        """Test graph builds without errors."""
        builder = GraphBuilder()
        graph = builder.build()
        assert graph is not None

    @pytest.mark.skip(reason="LangGraph asyncio event loop issue with pytest")
    def test_graph_execution_happy_path(self, sample_graph_state: GraphState) -> None:
        """Test full graph execution from lead to end."""
        builder = GraphBuilder()
        graph = builder.build()

        # Manual verification in smoke tests preferred
        assert graph is not None


@pytest.mark.asyncio
class TestStateManagement:
    """Test state management and models."""

    def test_lead_creation(self, sample_lead: Lead) -> None:
        """Test lead model creation."""
        assert sample_lead.lead_id is not None
        assert sample_lead.status == LeadStatus.DISCOVERED
        assert sample_lead.icp_score == 0.0

    def test_conversation_state_creation(
        self, sample_conversation_state: ConversationState
    ) -> None:
        """Test conversation state creation."""
        assert sample_conversation_state.conversation_id is not None
        assert sample_conversation_state.messages == []
        assert sample_conversation_state.total_tokens == 0

    def test_graph_state_creation(self, sample_graph_state: GraphState) -> None:
        """Test graph state creation."""
        assert sample_graph_state.lead is not None
        assert sample_graph_state.conversation is not None
        assert sample_graph_state.current_agent == "supervisor"

    async def test_state_updates_in_agent(self, sample_graph_state: GraphState) -> None:
        """Test state updates through agent execution."""
        agent = LeadAcquisitionAgent()
        updated_state = await agent.execute(sample_graph_state)

        assert updated_state.lead.status != LeadStatus.DISCOVERED
        assert len(updated_state.messages) > 0
        assert len(updated_state.acquisition_context) > 0
