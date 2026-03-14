"""LLM interface for Claude API integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class LLMInterface:
    """Claude API wrapper with token tracking and cost estimation."""

    # Claude Opus 4.1 pricing (as of Mar 2026)
    PRICING = {
        "input": 0.003,  # $3 per 1M input tokens
        "output": 0.015,  # $15 per 1M output tokens
    }

    def __init__(self, model: str = "claude-opus-4-1") -> None:
        """Initialize LLM interface."""
        self.client = AsyncAnthropic()
        self.model = model
        self.total_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> tuple[str, int, float]:
        """
        Generate text using Claude.

        Returns: (text, tokens_used, cost_usd)
        """
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens

        cost = self._calculate_cost(input_tokens, output_tokens)

        self.total_tokens += total_tokens
        self.total_cost += cost
        self.call_count += 1

        logger.info(
            "LLM call completed",
            extra={
                "model": self.model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
            },
        )

        return text, total_tokens, cost

    async def classify(
        self,
        text: str,
        categories: list[str],
        max_tokens: int = 20,
    ) -> str:
        """Classify text into one of provided categories."""
        prompt = f"""Classify this text into ONE of: {', '.join(categories)}.

Text: "{text}"

Return ONLY the category name (single word):"""

        text_result, _, _ = await self.generate(prompt, max_tokens=max_tokens)
        return text_result.strip().lower()

    async def extract_objection(self, text: str) -> dict[str, Any]:
        """Extract objection details from prospect message."""
        prompt = f"""Extract objection details from this prospect message.

Message: "{text}"

Return ONLY valid JSON (no markdown, no extra text):
{{
    "type": "price|timing|trust|urgency|other",
    "severity": 0.0-1.0,
    "key_phrase": "quoted phrase from message"
}}"""

        response_text, _, _ = await self.generate(prompt, max_tokens=100)

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse objection JSON: {response_text}")
            return {
                "type": "other",
                "severity": 0.5,
                "key_phrase": text[:50],
            }

    async def generate_counter_argument(
        self,
        objection: str,
        segment: str,
        rag_context: list[str],
    ) -> str:
        """Generate counter-argument for objection using RAG context."""
        context_str = "\n".join(rag_context) if rag_context else "No context available"

        prompt = f"""You are a sales expert handling objections.

Prospect segment: {segment}
Objection: {objection}

Relevant training content:
{context_str}

Generate a BRIEF (2-3 sentences) counter-argument that:
1. Acknowledges the concern
2. Uses the training content to address it
3. Moves conversation toward closing

Counter-argument:"""

        response_text, _, _ = await self.generate(prompt, max_tokens=150)
        return response_text.strip()

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost."""
        input_cost = (input_tokens / 1_000_000) * self.PRICING["input"]
        output_cost = (output_tokens / 1_000_000) * self.PRICING["output"]
        return input_cost + output_cost

    def get_metrics(self) -> dict[str, Any]:
        """Get LLM usage metrics."""
        return {
            "total_calls": self.call_count,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "avg_cost_per_call": (
                round(self.total_cost / self.call_count, 4) if self.call_count > 0 else 0
            ),
        }
