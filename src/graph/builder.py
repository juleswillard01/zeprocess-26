"""LangGraph builder for multi-agent orchestration."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.acquisition import LeadAcquisitionAgent
from src.agents.closing import ClosingAgent
from src.agents.seduction import SeductionAgent
from src.state.schema import GraphState

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Build and compile the LangGraph orchestration graph."""

    def __init__(self) -> None:
        self.graph = StateGraph(GraphState)
        self.acquisition_agent = LeadAcquisitionAgent()
        self.seduction_agent = SeductionAgent()
        self.closing_agent = ClosingAgent()

    def build(self) -> Any:
        """Build the LangGraph with all nodes and edges.

        Returns:
            Compiled StateGraph ready for execution
        """
        # Add nodes for each agent
        self.graph.add_node("acquisition", self._acquisition_node)
        self.graph.add_node("seduction", self._seduction_node)
        self.graph.add_node("closing", self._closing_node)
        self.graph.add_node("supervisor", self._supervisor_node)

        # Set entry point
        self.graph.set_entry_point("supervisor")

        # Add edges (routing)
        self.graph.add_conditional_edges(
            "supervisor",
            self._route_after_supervisor,
            {
                "acquisition": "acquisition",
                "seduction": "seduction",
                "closing": "closing",
                "end": END,
            },
        )

        self.graph.add_conditional_edges(
            "acquisition",
            self._route_after_acquisition,
            {
                "seduction": "seduction",
                "end": END,
            },
        )

        self.graph.add_conditional_edges(
            "seduction",
            self._route_after_seduction,
            {
                "closing": "closing",
                "seduction": "seduction",  # Continue seduction
                "end": END,
            },
        )

        self.graph.add_edge("closing", END)

        # Compile
        return self.graph.compile()

    async def _acquisition_node(self, state: GraphState) -> dict[str, Any]:
        """Execute acquisition agent node."""
        logger.info(f"Executing acquisition node for lead {state.lead.lead_id}")
        state.current_agent = "acquisition"
        return (await self.acquisition_agent.execute(state)).model_dump()

    async def _seduction_node(self, state: GraphState) -> dict[str, Any]:
        """Execute seduction agent node."""
        logger.info(f"Executing seduction node for lead {state.lead.lead_id}")
        state.current_agent = "seduction"
        return (await self.seduction_agent.execute(state)).model_dump()

    async def _closing_node(self, state: GraphState) -> dict[str, Any]:
        """Execute closing agent node."""
        logger.info(f"Executing closing node for lead {state.lead.lead_id}")
        state.current_agent = "closing"
        return (await self.closing_agent.execute(state)).model_dump()

    async def _supervisor_node(self, state: GraphState) -> dict[str, Any]:
        """Route to first agent based on lead status."""
        # Start with acquisition
        return state.model_dump()

    def _route_after_supervisor(self, state: GraphState) -> str:
        """Route from supervisor to appropriate starting agent."""
        # Always start with acquisition
        return "acquisition"

    def _route_after_acquisition(self, state: GraphState) -> str:
        """Route after acquisition based on lead quality."""
        # If ICP score is high enough, go to seduction
        if state.acquisition_context.get("ready_for_seduction", False):
            return "seduction"
        return "end"

    def _route_after_seduction(self, state: GraphState) -> str:
        """Route after seduction based on engagement level."""
        routing = state.routing_decision

        if routing == "closing":
            return "closing"
        elif routing == "continue_seduction":
            return "seduction"

        return "end"
