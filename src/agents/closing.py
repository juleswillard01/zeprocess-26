"""Closing Agent implementation."""

from __future__ import annotations

import logging
from typing import Any

from src.state.schema import GraphState, LeadStatus

from .base import BaseAgent

logger = logging.getLogger(__name__)


class ClosingAgent(BaseAgent):
    """Agent responsible for closing deals and processing payments."""

    def __init__(self) -> None:
        super().__init__("closing")

    async def execute(self, state: GraphState) -> GraphState:
        """Execute closing workflow.

        Steps:
        1. Detect remaining objections
        2. Apply closing tactics (Sonnet/Opus)
        3. Create urgency
        4. Ask for the sale
        5. Process payment (Stripe)
        6. Track for upsells
        """
        lead = state.lead

        # Step 1: Detect objections
        final_objections = await self._detect_final_objections(state.messages)
        if final_objections:
            # Handle final objections
            objection_handler = await self._create_final_objection_response(final_objections, lead)
            state.messages.append(
                {
                    "role": "agent",
                    "content": objection_handler,
                    "agent_name": "closing",
                }
            )

        # Step 2-3: Create urgency and ask for sale
        sales_message = await self._ask_for_sale(lead)
        state.messages.append(
            {
                "role": "agent",
                "content": sales_message,
                "agent_name": "closing",
            }
        )

        # Step 4: Process payment (with V-Code verification)
        payment_result = await self._process_payment(lead, state)

        if payment_result["status"] == "approved":
            lead.status = LeadStatus.WON
            lead.conversion_probability = 1.0
            state = await self._update_state(
                state,
                {
                    "payment_processed": True,
                    "amount": payment_result["amount"],
                    "transaction_id": payment_result["transaction_id"],
                },
            )
        else:
            lead.status = LeadStatus.LOST
            state.should_escalate = True
            state.escalation_reason = f"Payment failed: {payment_result['error']}"

        await self._log_execution(lead.lead_id, lead.status.value)
        return state

    async def _detect_final_objections(self, messages: list[dict[str, Any]]) -> list[str]:
        """Detect final objections before payment.

        Uses Haiku for classification (0.1-0.3 complexity).
        """
        # TODO: Integrate with Claude API (Haiku)
        objections = []

        if not messages:
            return objections

        last_lead_message = ""
        for message in reversed(messages):
            if message.get("role") == "lead":
                last_lead_message = message.get("content", "")
                break

        message_lower = last_lead_message.lower()

        objection_patterns = {
            "payment_method": ["card", "payment", "crypto", "wire"],
            "guarantee": ["guarantee", "refund", "money-back"],
            "commitment": ["too much", "commitment", "change mind"],
        }

        for objection_type, patterns in objection_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                objections.append(objection_type)

        return objections

    async def _create_final_objection_response(self, objections: list[str], lead: Any) -> str:
        """Handle final objections with Opus-level reasoning.

        Uses Opus for complex strategy (0.7-1.0 complexity).
        """
        # TODO: Integrate with Claude API (Opus)
        if "guarantee" in objections:
            return "I stand behind my work. 30-day satisfaction guarantee. You're protected."
        elif "commitment" in objections:
            return "Look, I get it. This is real. But you've been thinking about this for how long already? The cost of waiting is higher."
        elif "payment_method" in objections:
            return (
                "We accept all major payment methods. Card, bank transfer, whatever works for you."
            )

        return "Great question. Let me address that directly."

    async def _ask_for_sale(self, lead: Any) -> str:
        """Direct ask for the sale.

        Uses Sonnet for persuasive copy (0.4-0.6 complexity).
        """
        # TODO: Integrate with Claude API (Sonnet)
        return (
            f"{lead.username}, here's where we are: "
            "you're ready, the timing is right, and I know I can help you. "
            "The question is: are you ready to take action? "
            "Let's start today. I'll process your payment and we'll get you started tomorrow."
        )

    async def _process_payment(self, lead: Any, state: GraphState) -> dict[str, Any]:
        """Process payment via Stripe (with V-Code safety review).

        Returns: {"status": "approved"|"rejected"|"escalated", ...}
        """
        # TODO: Integrate with V-Code safety layer and Stripe
        # For now, mock implementation
        payment_data = {
            "customer_email": lead.email,
            "amount": 2000,  # $2000 course price
            "currency": "usd",
            "description": f"Coaching package for {lead.username}",
        }

        # Step 1: V-Code review (safety layer)
        v_code_decision = await self._v_code_review_payment(payment_data, lead, state)

        if v_code_decision["approved"]:
            # Step 2: Process with Stripe
            stripe_result = await self._stripe_charge(payment_data, lead)
            return stripe_result
        else:
            return {
                "status": "rejected",
                "error": v_code_decision.get("reason", "Safety check failed"),
            }

    async def _v_code_review_payment(
        self, payment_data: dict[str, Any], lead: Any, state: GraphState
    ) -> dict[str, Any]:
        """V-Code automated review before payment (safety layer).

        Checks:
        1. Amount limits
        2. Customer consent
        3. Suspicious patterns
        4. High-amount Opus verification
        """
        # TODO: Integrate actual V-Code system
        amount = payment_data.get("amount", 0)

        # Rule 1: Check amount limit
        if amount > 5000:
            return {
                "approved": False,
                "reason": "Amount exceeds single transaction limit",
            }

        # Rule 2: Check conversion probability
        if lead.conversion_probability < 0.6:
            return {
                "approved": False,
                "reason": "Conversion probability below threshold",
            }

        # Rule 3: Check for engagement
        if state.messages and len(state.messages) >= 3:
            return {"approved": True}

        return {
            "approved": False,
            "reason": "Insufficient engagement history",
        }

    async def _stripe_charge(self, payment_data: dict[str, Any], lead: Any) -> dict[str, Any]:
        """Process payment with Stripe.

        TODO: Integrate actual Stripe SDK.
        """
        # Mock Stripe response
        return {
            "status": "approved",
            "amount": payment_data["amount"],
            "transaction_id": f"txn_{lead.lead_id[:8]}",
            "timestamp": "2024-03-14T12:00:00Z",
        }
