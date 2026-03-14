"""Unit tests for LLM interface."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from agents.closing.llm_interface import LLMInterface


@pytest.mark.unit
class TestLLMInterface:
    """Test suite for LLMInterface."""

    @pytest.fixture
    def llm(self) -> LLMInterface:
        """Create LLMInterface instance."""
        return LLMInterface(model="claude-opus-4-1")

    @pytest.mark.asyncio
    async def test_generate_text(self, llm: LLMInterface) -> None:
        """Test text generation."""
        with patch.object(llm.client.messages, "create") as mock_create:
            # Mock response
            mock_response = AsyncMock()
            mock_response.content = [AsyncMock(text="Generated response")]
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_create.return_value = mock_response

            text, tokens, cost = await llm.generate("Test prompt")

            assert text == "Generated response"
            assert tokens == 150
            assert cost > 0
            assert llm.total_tokens == 150
            assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_classify_text(self, llm: LLMInterface) -> None:
        """Test text classification."""
        with patch.object(llm.client.messages, "create") as mock_create:
            mock_response = AsyncMock()
            mock_response.content = [AsyncMock(text="price")]
            mock_response.usage.input_tokens = 50
            mock_response.usage.output_tokens = 10
            mock_create.return_value = mock_response

            result = await llm.classify("Too expensive", ["price", "timing", "trust"])

            assert result == "price"

    @pytest.mark.asyncio
    async def test_extract_objection_valid(self, llm: LLMInterface) -> None:
        """Test objection extraction with valid JSON."""
        with patch.object(llm.client.messages, "create") as mock_create:
            mock_response = AsyncMock()
            mock_response.content = [
                AsyncMock(text='{"type": "price", "severity": 0.8, "key_phrase": "Too expensive"}')
            ]
            mock_response.usage.input_tokens = 50
            mock_response.usage.output_tokens = 20
            mock_create.return_value = mock_response

            result = await llm.extract_objection("This is too expensive")

            assert result["type"] == "price"
            assert result["severity"] == 0.8
            assert result["key_phrase"] == "Too expensive"

    @pytest.mark.asyncio
    async def test_extract_objection_invalid_json(self, llm: LLMInterface) -> None:
        """Test objection extraction with invalid JSON."""
        with patch.object(llm.client.messages, "create") as mock_create:
            mock_response = AsyncMock()
            mock_response.content = [AsyncMock(text="Invalid JSON")]
            mock_response.usage.input_tokens = 50
            mock_response.usage.output_tokens = 10
            mock_create.return_value = mock_response

            result = await llm.extract_objection("This is too expensive")

            assert result["type"] == "other"
            assert result["severity"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_counter_argument(self, llm: LLMInterface) -> None:
        """Test counter-argument generation."""
        with patch.object(llm.client.messages, "create") as mock_create:
            mock_response = AsyncMock()
            mock_response.content = [AsyncMock(text="Here's why this is worth it...")]
            mock_response.usage.input_tokens = 200
            mock_response.usage.output_tokens = 40
            mock_create.return_value = mock_response

            result = await llm.generate_counter_argument(
                "Too expensive", "high_value", ["Content about pricing strategy"]
            )

            assert "worth it" in result.lower()
            assert llm.total_tokens == 240

    def test_calculate_cost(self, llm: LLMInterface) -> None:
        """Test cost calculation."""
        cost = llm._calculate_cost(input_tokens=1000, output_tokens=500)

        expected = (1000 / 1_000_000) * 0.003 + (500 / 1_000_000) * 0.015
        assert cost == pytest.approx(expected)

    def test_get_metrics(self, llm: LLMInterface) -> None:
        """Test metrics retrieval."""
        llm.total_tokens = 1000
        llm.total_cost = 0.05
        llm.call_count = 5

        metrics = llm.get_metrics()

        assert metrics["total_calls"] == 5
        assert metrics["total_tokens"] == 1000
        assert metrics["total_cost_usd"] == 0.05
        assert metrics["avg_cost_per_call"] == pytest.approx(0.01)
