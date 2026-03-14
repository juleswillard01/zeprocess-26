"""Payment manager for Stripe integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import stripe

logger = logging.getLogger(__name__)


class PaymentManager:
    """Stripe payment integration for checkout flows."""

    def __init__(self, stripe_api_key: str, api_domain: str):
        """Initialize payment manager."""
        stripe.api_key = stripe_api_key
        self.api_domain = api_domain

    async def create_checkout_session(
        self,
        prospect_id: str,
        prospect_email: str,
        amount_cents: int,
        description: str,
    ) -> tuple[str, str]:
        """
        Create Stripe checkout session.

        Returns: (session_id, checkout_url)
        """
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": description,
                                "metadata": {"prospect_id": prospect_id},
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                metadata={
                    "prospect_id": prospect_id,
                    "prospect_email": prospect_email,
                },
                success_url=f"{self.api_domain}/api/closing/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{self.api_domain}/api/closing/payment/cancel?session_id={{CHECKOUT_SESSION_ID}}",
            )

            logger.info(
                f"Checkout session created",
                extra={
                    "session_id": session.id,
                    "prospect_id": prospect_id,
                    "amount_usd": amount_cents / 100,
                },
            )

            return session.id, session.url

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise

    async def verify_payment(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Verify payment status from session."""
        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == "paid":
                payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)

                return {
                    "status": "paid",
                    "session_id": session_id,
                    "amount_usd": session.amount_total / 100,
                    "payment_id": payment_intent.id,
                    "customer_email": session.customer_email,
                    "metadata": session.metadata or {},
                }
            else:
                return {
                    "status": session.payment_status,
                    "session_id": session_id,
                }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe verification error: {str(e)}")
            raise

    async def refund_payment(
        self,
        payment_intent_id: str,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Refund a payment."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                reason=reason,
            )

            logger.info(
                f"Refund processed",
                extra={
                    "payment_intent_id": payment_intent_id,
                    "refund_id": refund.id,
                },
            )

            return {
                "status": refund.status,
                "refund_id": refund.id,
                "amount_usd": refund.amount / 100,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {str(e)}")
            raise

    def get_metrics(self) -> dict[str, Any]:
        """Get payment manager metrics."""
        return {
            "stripe_api_key_set": bool(stripe.api_key),
            "api_domain": self.api_domain,
        }
