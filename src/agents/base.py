"""Base agent class for MEGA QUIXAI."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.state.schema import GraphState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"{__name__}.{agent_name}")

    @abstractmethod
    async def execute(self, state: GraphState) -> GraphState:
        """Execute the agent's logic on the given state.

        Args:
            state: Current orchestration state

        Returns:
            Updated state after agent execution
        """
        pass

    async def _log_execution(
        self, lead_id: str, result: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Log agent execution for observability."""
        self.logger.info(
            f"Agent {self.agent_name} executed for lead {lead_id}",
            extra={
                "agent": self.agent_name,
                "lead_id": lead_id,
                "result": result,
                "metadata": metadata or {},
            },
        )

    async def _update_state(self, state: GraphState, updates: dict[str, Any]) -> GraphState:
        """Safely update state with agent-specific context.

        Args:
            state: Current state
            updates: Updates to apply

        Returns:
            Updated state
        """
        # Update agent-specific context
        if self.agent_name == "acquisition":
            state.acquisition_context.update(updates)
        elif self.agent_name == "seduction":
            state.seduction_context.update(updates)
        elif self.agent_name == "closing":
            state.closing_context.update(updates)

        return state
