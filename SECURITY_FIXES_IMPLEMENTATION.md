# Security Fixes - Implementation Guide

**Timeline**: 4-6 hours | **Team**: 1 engineer | **Difficulty**: Medium

This guide provides step-by-step instructions to implement all HIGH-severity security fixes from the security audit.

---

## Quick Start

```bash
# Start fresh branch
git checkout -b security/phase-0-hardening
git pull origin main

# Run audit to verify issues
pip-audit
mypy --strict src/ agents/

# Begin fixes (estimated 1-2 hours per fix)
```

---

## Fix 1: CORS Configuration (SEC-001)

**Status**: 🔴 HIGH | CVSS 6.5
**Time**: ~1 hour
**Difficulty**: Easy

### Step 1.1: Update settings

Edit `/config/settings.py`:

```python
"""Application settings and configuration."""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # ... existing fields (project, environment, debug) ...

    # NEW: Add allowed domains
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    @field_validator("allowed_origins")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> list[str]:
        """Parse comma-separated allowed origins."""
        return [origin.strip() for origin in v.split(",")]

    # ... rest of settings ...
```

### Step 1.2: Update API configuration

Edit `/src/api/main.py`:

```python
"""FastAPI application for MEGA QUIXAI."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    debug=settings.debug,
)

# CORS configuration - FIXED: Restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # ← Now uses configured list
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ... rest of app ...
```

### Step 1.3: Update `.env.example`

```bash
# API CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://yourdomain.com
```

### Step 1.4: Test

```bash
# CORS should be rejected from unapproved origin
curl -H "Origin: https://evil.com" \
     -H "Access-Control-Request-Method: POST" \
     -v http://localhost:8000/health

# Should see NO Access-Control-Allow-Origin header (rejection)

# CORS should work from approved origin
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -v http://localhost:8000/health

# Should see Access-Control-Allow-Origin header
```

**Verification Command**:
```bash
python -c "from config.settings import settings; print(settings.allowed_origins)"
```

---

## Fix 2: API Authentication (SEC-002)

**Status**: 🔴 HIGH | CVSS 7.3
**Time**: ~2-3 hours
**Difficulty**: Medium

### Step 2.1: Add API token to settings

Edit `/config/settings.py`, add field:

```python
class Settings(BaseSettings):
    """Application settings from environment variables."""

    # ... existing fields ...

    # NEW: API authentication
    api_token: str = ""  # Optional; if empty, auth is disabled (dev only)

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False

    def get_database_url(self) -> str:
        """Get database URL."""
        return self.database_url

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def require_api_token(self) -> bool:
        """Check if API token is required (production only)."""
        return self.environment == "production" and bool(self.api_token)
```

### Step 2.2: Create auth module

Create new file `/src/api/auth.py`:

```python
"""API authentication and authorization."""

from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Verify Bearer token using constant-time comparison.

    Args:
        credentials: Bearer token from request header

    Returns:
        Token string if valid

    Raises:
        HTTPException: 401 if token invalid or missing (when required)
    """
    # In development without token configured, skip auth
    if not settings.api_token:
        return "development"

    # Missing credentials
    if not credentials:
        logger.warning("Missing API token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use hmac.compare_digest for timing-attack resistance
    # This prevents attackers from guessing token by timing responses
    if not hmac.compare_digest(credentials.credentials, settings.api_token):
        logger.warning("Invalid API token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


async def optional_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Optional Bearer token verification.

    Used for endpoints that work with or without auth (e.g., health checks).

    Args:
        credentials: Bearer token from request header (optional)

    Returns:
        Token string if valid, None if missing or invalid
    """
    if not credentials:
        return None

    # If no token configured, allow public access
    if not settings.api_token:
        return "public"

    # Verify token
    if hmac.compare_digest(credentials.credentials, settings.api_token):
        return credentials.credentials

    # Invalid token; fail silently for optional auth
    logger.warning("Invalid API token on optional endpoint")
    return None
```

### Step 2.3: Update API endpoints

Edit `/src/api/main.py`:

```python
"""FastAPI application for MEGA QUIXAI."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import settings
from src.api.auth import optional_bearer_token, verify_bearer_token

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    debug=settings.debug,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Health check endpoint (public with optional auth)
@app.get("/health")
async def health_check(
    token: str = Depends(optional_bearer_token),
) -> dict[str, str]:
    """Health check endpoint.

    This endpoint is publicly accessible but optionally accepts
    Bearer token for authenticated monitoring.
    """
    return {
        "status": "ok",
        "service": "mega-quixai",
        "authenticated": bool(token),
    }


# Root endpoint (requires auth in production)
@app.get("/")
async def root(
    token: str = Depends(verify_bearer_token),
) -> dict[str, str]:
    """Root endpoint."""
    return {"message": f"Welcome to {settings.project_name}"}


# Error handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# Lifespan events
@app.on_event("startup")
async def startup_event() -> None:
    """Startup event."""
    logger.info(f"Starting {settings.project_name} (env: {settings.environment})")
    if settings.environment == "production" and not settings.api_token:
        logger.warning("API_TOKEN not set in production; all endpoints public!")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event."""
    logger.info(f"Shutting down {settings.project_name}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
    )
```

### Step 2.4: Update `.env.example`

```bash
# API Authentication
API_TOKEN=your_32_character_api_key_here_change_this
```

### Step 2.5: Test

```bash
# Generate a test token
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set token
export API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Start server
uvicorn src.api.main:app --reload

# Test without token (should fail if token set)
curl http://localhost:8000/

# Test with token (should work)
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/

# Test health (should work without token)
curl http://localhost:8000/health
```

---

## Fix 3: Database URL Validation (SEC-003)

**Status**: 🟡 MEDIUM | CVSS 5.9
**Time**: ~1 hour
**Difficulty**: Easy

### Step 3.1: Update settings validation

Edit `/config/settings.py`:

```python
"""Application settings and configuration."""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Project
    project_name: str = "MEGA QUIXAI"
    environment: str = "development"
    debug: bool = False

    # Database - MUST be provided in production
    database_url: str = ""

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str, info) -> str:
        """Ensure database URL is configured in production."""
        environment = info.data.get("environment", "development")

        if environment == "production" and not v:
            raise ValueError(
                "DATABASE_URL must be set in production. "
                "Example: postgresql://user:password@host:5432/dbname"
            )

        if environment == "development" and not v:
            # Default for development
            return "postgresql://quixai_user:quixai_password@localhost:5432/mega_quixai"

        return v

    # ... rest of settings ...
```

### Step 3.2: Update `.env.example`

```bash
# Database - REQUIRED in production
# Format: postgresql://username:password@hostname:port/database
DATABASE_URL=postgresql://quixai_user:password@localhost:5432/mega_quixai
```

### Step 3.3: Test

```bash
# Development (should work without DATABASE_URL)
unset DATABASE_URL
python -c "from config.settings import settings; print(settings.database_url)"

# Production (should fail without DATABASE_URL)
export ENVIRONMENT=production
unset DATABASE_URL
python -c "from config.settings import settings; print(settings.database_url)" 2>&1 | grep -i "must be set"

# Should see: "DATABASE_URL must be set in production"
```

---

## Fix 4: Secret Sanitization in Logs (SEC-004)

**Status**: 🟡 MEDIUM | CVSS 4.7
**Time**: ~1-2 hours
**Difficulty**: Medium

### Step 4.1: Create sanitization utility

Create `/src/utils/__init__.py`:

```python
"""Utility modules."""

from __future__ import annotations
```

Create `/src/utils/sanitizers.py`:

```python
"""Log sanitization utilities."""

from __future__ import annotations

import re
from typing import Any


# Patterns for sensitive data
SENSITIVE_PATTERNS = {
    "stripe_key": re.compile(r"(sk_live_|sk_test_)[a-zA-Z0-9_]+"),
    "anthropic_key": re.compile(r"sk-ant-[a-zA-Z0-9_]+"),
    "api_token": re.compile(r"^bearer\s+[a-zA-Z0-9]{32,}$", re.IGNORECASE),
    "password": re.compile(r"password['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_!@#$%^&*()+-]+['\"]?"),
    "token": re.compile(r"token['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{20,}['\"]?"),
}


def sanitize_value(value: str) -> str:
    """Sanitize a single string value.

    Replaces sensitive patterns with ***REDACTED***.
    """
    if not isinstance(value, str):
        return value

    for pattern in SENSITIVE_PATTERNS.values():
        if pattern.search(value):
            return "***REDACTED***"

    return value


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize sensitive values in dict.

    Args:
        data: Dictionary to sanitize

    Returns:
        Copy of dict with sensitive values redacted

    Example:
        >>> input_data = {"api_key": "sk_test_abc123", "name": "John"}
        >>> sanitize_dict(input_data)
        {"api_key": "***REDACTED***", "name": "John"}
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [
                sanitize_dict(item) if isinstance(item, dict) else sanitize_value(item)
                for item in value
            ]
        elif isinstance(value, str):
            # Check both key name and value
            if _looks_sensitive(key):
                result[key] = "***REDACTED***"
            else:
                result[key] = sanitize_value(value)
        else:
            result[key] = value

    return result


def _looks_sensitive(key: str) -> bool:
    """Check if a key name suggests sensitive data."""
    sensitive_keys = {
        "password",
        "secret",
        "token",
        "api_key",
        "api_token",
        "auth_token",
        "private_key",
        "access_token",
        "refresh_token",
        "stripe_key",
        "stripe_secret",
        "anthropic_key",
    }
    return key.lower() in sensitive_keys or any(
        sk in key.lower() for sk in sensitive_keys
    )
```

### Step 4.2: Update payment manager logging

Edit `/agents/closing/payment_manager.py`:

```python
"""Payment manager for Stripe integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import stripe

from src.utils.sanitizers import sanitize_dict

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
        """Create Stripe checkout session.

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

            # Log with sanitization (prevents API key leaks)
            logger.info(
                "Checkout session created",
                extra=sanitize_dict({
                    "session_id": session.id,
                    "prospect_id": prospect_id,
                    "prospect_email": prospect_email,
                    "amount_usd": amount_cents / 100,
                }),
            )

            return session.id, session.url

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise

    async def verify_payment(self, session_id: str) -> dict[str, Any]:
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
                "Refund processed",
                extra=sanitize_dict({
                    "payment_intent_id": payment_intent_id,
                    "refund_id": refund.id,
                    "amount_usd": refund.amount / 100,
                }),
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
```

### Step 4.3: Test sanitization

```bash
# Unit test
python -m pytest tests/unit/test_sanitizers.py -v

# Manual test
python -c "
from src.utils.sanitizers import sanitize_dict

data = {
    'api_key': 'sk_test_abc123',
    'user_name': 'john',
    'metadata': {
        'stripe_secret': 'secret_xyz'
    }
}

print(sanitize_dict(data))
# Should output:
# {'api_key': '***REDACTED***', 'user_name': 'john', 'metadata': {'stripe_secret': '***REDACTED***'}}
"
```

---

## Summary & Verification

### Checklist

- [ ] Fix 1: CORS configuration (1 hour)
- [ ] Fix 2: API authentication (2-3 hours)
- [ ] Fix 3: Database URL validation (1 hour)
- [ ] Fix 4: Secret sanitization (1-2 hours)
- [ ] Run all tests: `pytest tests/ -v`
- [ ] Type check: `mypy --strict src/ agents/`
- [ ] Dependency audit: `pip-audit`

### Total Time
**Estimated**: 4-6 hours for one engineer

### Deployment

```bash
# Test all fixes
pytest tests/ -v --cov=src --cov=agents --cov-fail-under=80
mypy --strict src/ agents/
ruff check src/ agents/

# Commit
git add -A
git commit -m "security: Phase 0 hardening - CORS, API auth, DB validation, secret sanitization"

# Push for code review
git push origin security/phase-0-hardening

# Create PR
gh pr create --title "Security: Phase 0 hardening" \
  --body "Implements all 4 HIGH/MEDIUM security fixes from audit"
```

### Testing in Staging

```bash
# Start server with API_TOKEN set
export API_TOKEN="test_token_12345678901234567890"
export DATABASE_URL="postgresql://user:password@localhost/testdb"
export ENVIRONMENT=production
export ALLOWED_ORIGINS="http://localhost:3000"

uvicorn src.api.main:app --reload

# Test endpoints
curl http://localhost:8000/health  # Public (optional auth)
curl http://localhost:8000/  # Requires auth

# With token
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/

# CORS test
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     http://localhost:8000/
```

---

## Next Steps

After Phase 0 hardening is complete:

1. **Code review** (1-2 hours)
2. **Staging deployment** (2 hours)
3. **Load testing** (4 hours)
4. **Production deployment** (2 hours)

**Total**: ~1-2 days from commit to production with proper testing.

---

**Created**: March 14, 2026
**Updated**: March 14, 2026
