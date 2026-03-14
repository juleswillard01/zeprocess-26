"""Base class for autonomous LangGraph agents."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class AgentState:
    """Base state for all agents."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.iteration = 0
        self.last_error: str | None = None


class AutonomousAgent(ABC):
    """Base class for autonomous LangGraph agents running 24/7."""
    
    def __init__(self, name: str, redis_client: Redis, loop_interval: int = 60):
        self.name = name
        self.redis = redis_client
        self.loop_interval = loop_interval
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._stop_event = asyncio.Event()
    
    @abstractmethod
    async def execute_iteration(self, state: Any) -> Any:
        """Execute one iteration of the agent."""
        pass
    
    async def run_forever(self) -> None:
        """Main loop: run agent continuously until stop signal."""
        self.logger.info(f"Starting autonomous agent: {self.name}")
        state = AgentState(self.name)
        
        while not self._stop_event.is_set():
            try:
                state.iteration += 1
                state = await self.execute_iteration(state)
                state.last_error = None
                
                await self.redis.set(
                    f"agent:{self.name}:health",
                    f"ok:iter={state.iteration}",
                    ex=300,
                )
                
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.loop_interval,
                    )
                except asyncio.TimeoutError:
                    pass
                
            except Exception as e:
                state.last_error = str(e)
                self.logger.error(f"Iteration {state.iteration} failed: {e}", exc_info=True)
                await self.redis.set(f"agent:{self.name}:health", f"error:{e}", ex=60)
                backoff = min(2 ** (state.iteration % 10), 300)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
    
    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self.logger.info(f"Stopping agent: {self.name}")
        self._stop_event.set()
