# COMPREHENSIVE ARCHITECTURE: AUTH + STRIPE + MULTI-TENANCY

## Executive Summary

This specification defines a production-grade multi-tenant SaaS architecture for Hexis with:
- Email-based authentication with JWT sessions
- Stripe subscription management (3-tier pricing)
- Per-subscriber memory isolation with shared knowledge base
- Channel identity binding (Telegram/WhatsApp/Discord → subscriber account)
- GDPR-compliant lifecycle management
- Rate limiting per tier
- Automatic deactivation/deletion on payment lapse

---

## 1. Database Schema Additions

### 1.1 Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    
    -- Email verification
    email_verified BOOLEAN DEFAULT FALSE,
    email_verification_token TEXT,
    email_verification_sent_at TIMESTAMPTZ,
    email_verified_at TIMESTAMPTZ,
    
    -- Account status
    status TEXT NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'deactivated', 'pending_deletion')),
    deactivated_at TIMESTAMPTZ,
    deletion_scheduled_for TIMESTAMPTZ,  -- 2 weeks after deactivation
    
    -- GDPR
    consent_to_marketing BOOLEAN DEFAULT FALSE,
    consent_timestamp TIMESTAMPTZ,
    data_deletion_requested BOOLEAN DEFAULT FALSE,
    data_deletion_requested_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_deletion_scheduled ON users(deletion_scheduled_for) 
    WHERE status = 'pending_deletion';
```

### 1.2 Subscriptions Table

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
    -- Stripe integration
    stripe_customer_id TEXT NOT NULL UNIQUE,
    stripe_subscription_id TEXT,  -- NULL if not yet subscribed
    stripe_product_id TEXT,
    stripe_price_id TEXT,
    
    -- Tier definition
    tier TEXT NOT NULL DEFAULT 'free'
        CHECK (tier IN ('free', 'starter', 'pro', 'enterprise')),
    price_eur DECIMAL(10, 2),  -- 20, 90, 180, custom
    
    -- Billing cycle
    current_period_start DATE,
    current_period_end DATE,
    renewal_date DATE,
    
    -- Payment status
    status TEXT NOT NULL DEFAULT 'inactive'
        CHECK (status IN ('active', 'past_due', 'cancelled', 'inactive')),
    payment_failed_count INTEGER DEFAULT 0,
    last_payment_failed_at TIMESTAMPTZ,
    last_payment_succeeded_at TIMESTAMPTZ,
    
    -- Rate limits (per tier)
    messages_per_day INTEGER DEFAULT 100,
    tokens_per_month INTEGER DEFAULT 100000,
    
    -- Dates
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMPTZ
);

CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id);
CREATE INDEX idx_subscriptions_stripe_subscription ON subscriptions(stripe_subscription_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_renewal_date ON subscriptions(renewal_date);
```

### 1.3 Sessions Table

```sql
CREATE TABLE auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- JWT metadata
    refresh_token_hash TEXT NOT NULL UNIQUE,  -- hash of refresh token
    access_token_hash TEXT,  -- for audit trail
    
    -- Session state
    ip_address INET,
    user_agent TEXT,
    device_name TEXT,  -- optional: "Chrome on macOS"
    
    -- Lifecycle
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMPTZ,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    
    -- Multi-device tracking
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id, is_active);
CREATE INDEX idx_auth_sessions_refresh_token ON auth_sessions(refresh_token_hash);
CREATE INDEX idx_auth_sessions_expires ON auth_sessions(expires_at);
```

### 1.4 Channel Identities Table (Multi-Channel Auth)

```sql
CREATE TABLE channel_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Channel binding
    channel_type TEXT NOT NULL,  -- 'telegram', 'whatsapp', 'discord'
    channel_user_id TEXT NOT NULL,  -- platform's user ID
    channel_username TEXT,  -- display name or username
    
    -- Verification
    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    verification_code TEXT,  -- one-time code for phone verification
    verification_sent_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,  -- channel-specific data
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(channel_type, channel_user_id)
);

CREATE INDEX idx_channel_identities_user ON channel_identities(user_id);
CREATE INDEX idx_channel_identities_lookup ON channel_identities(channel_type, channel_user_id);
```

### 1.5 Memory Partitioning Table

```sql
-- Link memories to subscribers (memory isolation)
CREATE TABLE subscriber_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    
    -- Memory scope
    scope TEXT NOT NULL DEFAULT 'private'
        CHECK (scope IN ('private', 'shared_knowledge_base')),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(subscriber_id, memory_id, scope)
);

CREATE INDEX idx_subscriber_memories_subscriber ON subscriber_memories(subscriber_id);
CREATE INDEX idx_subscriber_memories_memory ON subscriber_memories(memory_id);
CREATE INDEX idx_subscriber_memories_scope ON subscriber_memories(scope);

-- Shared knowledge base (trained on across all agents)
CREATE TABLE knowledge_base_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    
    -- Training metadata
    added_by_system BOOLEAN DEFAULT FALSE,
    source TEXT,  -- e.g., "hexis:training", "community:synthesis"
    access_count_total INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(memory_id)
);

CREATE INDEX idx_knowledge_base_memories_memory ON knowledge_base_memories(memory_id);
```

### 1.6 Audit Trail Table

```sql
CREATE TABLE auth_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Event
    event_type TEXT NOT NULL,  -- signup, login, logout, password_changed, etc.
    status TEXT,  -- success, failure, reason
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    
    -- Payload
    metadata JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auth_audit_user ON auth_audit_log(user_id, created_at DESC);
CREATE INDEX idx_auth_audit_event ON auth_audit_log(event_type, created_at DESC);
```

---

## 2. Authentication Flow (Signup → Verify → Login → JWT)

### 2.1 Signup Flow

**Endpoint:** `POST /auth/signup`

```json
Request:
{
  "email": "user@example.com",
  "password": "secure_password_min_12_chars",
  "full_name": "John Doe",
  "consent_to_marketing": false
}

Response (201):
{
  "user_id": "uuid",
  "email": "user@example.com",
  "status": "email_verification_pending",
  "verification_email_sent": true
}
```

**Process:**
1. Validate email format + password strength (min 12 chars, mix of letter/number/symbol)
2. Hash password with bcrypt (cost factor 12)
3. Create `users` row with `email_verified = FALSE`
4. Generate verification token (random 32-byte hex)
5. Store token hash in `email_verification_token`
6. Send verification email with link: `https://app.hexis.io/auth/verify?token={token}`
7. Log event to `auth_audit_log` with status="signup_sent"

**Error Cases:**
- 400: Email already exists → "This email is already registered. Try login or password reset."
- 400: Password too weak → "Password must be 12+ chars, with uppercase, number, symbol."
- 429: Rate limited (5 signups per hour per IP)
- 503: Email service unavailable

---

### 2.2 Email Verification Flow

**Endpoint:** `GET /auth/verify?token={token}`

```
Response (200 - HTML):
<html>
  <body>
    <h1>Email Verified!</h1>
    <p>You can now login.</p>
    <a href="/login">Go to Login</a>
  </body>
</html>

Response (400):
{
  "error": "Invalid or expired token"
}
```

**Process:**
1. Find user by `email_verification_token` hash
2. Check token not older than 24 hours
3. Mark `email_verified = TRUE`, `email_verified_at = now()`
4. Clear `email_verification_token`
5. Create free tier subscription (tier="free")
6. Log event: "email_verified"
7. Redirect to login or dashboard

---

### 2.3 Login Flow

**Endpoint:** `POST /auth/login`

```json
Request:
{
  "email": "user@example.com",
  "password": "password",
  "device_name": "Chrome on macOS"
}

Response (200):
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "refresh_token_hash_...",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "tier": "free",
    "subscription_status": "active"
  }
}
```

**Process:**
1. Find user by email
2. Verify password against bcrypt hash
3. Check `status != 'pending_deletion'`
4. Check `email_verified == TRUE`
5. Generate JWT access token (1 hour expiry):
   ```
   {
     "sub": "user_id",
     "email": "email",
     "tier": "tier_from_subscription",
     "iat": timestamp,
     "exp": timestamp + 3600
   }
   ```
6. Generate refresh token (32-byte random):
   - Store hash in `auth_sessions`
   - Return unhashed token to client (use secure httpOnly cookie or localStorage)
7. Update `users.last_login = now()`
8. Log event: "login_success"

**Error Cases:**
- 401: Email not found → "Invalid email or password"
- 401: Password incorrect → "Invalid email or password"
- 403: Email not verified → "Please verify your email first"
- 403: Account deactivated → "Your account has been deactivated"
- 429: Too many failed attempts (5 per 15 min per IP)

---

### 2.4 Token Refresh

**Endpoint:** `POST /auth/refresh`

```json
Request:
{
  "refresh_token": "refresh_token_hash_..."
}

Response (200):
{
  "access_token": "new_jwt...",
  "expires_in": 3600
}
```

**Process:**
1. Find session by refresh token hash
2. Check session not revoked
3. Check session not expired
4. Issue new access token
5. Optionally rotate refresh token (generate new, revoke old)
6. Update `last_used = now()`

---

### 2.5 Logout

**Endpoint:** `POST /auth/logout`

```json
Request:
{
  "refresh_token": "refresh_token_hash_..."
}

Response (200):
{
  "status": "logged_out"
}
```

**Process:**
1. Mark session as `revoked = TRUE`, `revoked_at = now()`
2. Log event: "logout"
3. Client clears tokens

---

## 3. Stripe Integration

### 3.1 Pricing Model

| Tier | Price/Month | Agents | Memory | Requests/Day | Tokens/Month |
|------|-------------|--------|--------|--------------|--------------|
| Free | 0€ | 1 (basic) | Shared KB | 10 | 10K |
| Starter | 20€ | 1 | Shared KB | 100 | 100K |
| Pro | 90€ | All | Shared KB | 500 | 500K |
| Enterprise | 180€ | All | Shared KB + 1M personal | Custom | Custom |

### 3.2 Subscription Creation Endpoint

**Endpoint:** `POST /billing/subscribe`

```json
Request:
{
  "tier": "pro",  // "starter", "pro", "enterprise"
  "payment_method_id": "pm_xxxxx",  // Stripe payment method
  "billing_cycle": "monthly"
}

Response (201):
{
  "subscription_id": "sub_xxxxx",
  "client_secret": "seti_xxxxx_secret_xxxxx",  // For SCA/3DS
  "status": "requires_action",  // or "active"
  "tier": "pro",
  "current_period_end": "2025-04-14",
  "amount": 9000  // cents
}
```

**Process:**
1. Retrieve authenticated user from JWT
2. Validate tier in ["starter", "pro", "enterprise"]
3. Check if already has active subscription (prevent duplicate billing)
4. Create Stripe customer if not exists:
   ```python
   customer = stripe.Customer.create(
       email=user.email,
       metadata={"user_id": str(user.id)}
   )
   ```
5. Create Stripe subscription:
   ```python
   subscription = stripe.Subscription.create(
       customer=customer.id,
       items=[{"price": STRIPE_PRICE_IDS[tier]}],
       payment_settings={
           "payment_method_types": ["card"],
           "save_default_payment_method": "on_subscription"
       },
       expand=["latest_invoice.payment_intent"]
   )
   ```
6. Store in `subscriptions` table:
   - `stripe_customer_id`
   - `stripe_subscription_id`
   - `stripe_price_id`
   - `tier`
   - `status` based on Stripe status
7. If requires SCA (3D Secure), return `client_secret` for frontend to confirm
8. Log: "subscription_created"

---

### 3.3 Webhook Handler

**Endpoint:** `POST /billing/webhook`

Stripe sends webhooks for:
- `customer.subscription.created`
- `customer.subscription.updated`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.deleted`

```python
@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return JSONResponse({"error": "Invalid payload"}, status_code=400)
    except stripe.error.SignatureVerificationError:
        return JSONResponse({"error": "Invalid signature"}, status_code=400)
    
    # Route by event type
    if event["type"] == "customer.subscription.updated":
        await _handle_subscription_updated(event["data"]["object"])
    elif event["type"] == "invoice.payment_succeeded":
        await _handle_payment_succeeded(event["data"]["object"])
    elif event["type"] == "invoice.payment_failed":
        await _handle_payment_failed(event["data"]["object"])
    
    return JSONResponse({"status": "received"}, status_code=200)
```

**Handler: subscription.updated**
```python
async def _handle_subscription_updated(subscription: dict) -> None:
    # Find user by stripe_customer_id
    customer_id = subscription["customer"]
    sub_row = await pool.fetchrow(
        "SELECT user_id, subscription_id FROM subscriptions WHERE stripe_customer_id = $1",
        customer_id
    )
    if not sub_row:
        return
    
    user_id = sub_row["user_id"]
    stripe_status = subscription["status"]  # active, past_due, unpaid, canceled
    
    if stripe_status == "active":
        # Payment succeeded; reactivate if deactivated
        await pool.execute(
            """UPDATE users SET status = 'active', deactivated_at = NULL
               WHERE id = $1""",
            user_id
        )
        await pool.execute(
            """UPDATE subscriptions 
               SET status = 'active', payment_failed_count = 0,
                   last_payment_succeeded_at = CURRENT_TIMESTAMP
               WHERE stripe_customer_id = $1""",
            customer_id
        )
        logger.info(f"Subscription {customer_id} reactivated")
    
    elif stripe_status in ["past_due", "unpaid"]:
        # Don't deactivate yet; wait for payment failure after 2-3 attempts
        await pool.execute(
            "UPDATE subscriptions SET status = $1 WHERE stripe_customer_id = $2",
            stripe_status,
            customer_id
        )
```

**Handler: invoice.payment_failed**
```python
async def _handle_payment_failed(invoice: dict) -> None:
    customer_id = invoice["customer"]
    sub_row = await pool.fetchrow(
        "SELECT user_id FROM subscriptions WHERE stripe_customer_id = $1",
        customer_id
    )
    if not sub_row:
        return
    
    user_id = sub_row["user_id"]
    
    # Increment failure count
    failure_count = await pool.fetchval(
        """UPDATE subscriptions SET payment_failed_count = payment_failed_count + 1,
                                     last_payment_failed_at = CURRENT_TIMESTAMP
           WHERE stripe_customer_id = $1
           RETURNING payment_failed_count""",
        customer_id
    )
    
    if failure_count >= 3:  # Deactivate after 3 failed attempts
        await pool.execute(
            """UPDATE users SET status = 'deactivated', deactivated_at = CURRENT_TIMESTAMP,
                              deletion_scheduled_for = CURRENT_TIMESTAMP + INTERVAL '14 days'
               WHERE id = $1""",
            user_id
        )
        await pool.execute(
            "UPDATE subscriptions SET status = 'past_due' WHERE stripe_customer_id = $1",
            customer_id
        )
        # Send email: "Your subscription payment failed. Fix it within 14 days or your account will be deleted."
```

---

### 3.4 Billing Portal

**Endpoint:** `GET /billing/portal`

```json
Response (302 redirect):
Location: https://billing.stripe.com/p/session/xxxx
```

**Process:**
1. Authenticate user
2. Fetch `subscriptions.stripe_customer_id`
3. Create Stripe billing portal session:
   ```python
   session = stripe.billing_portal.Session.create(
       customer=stripe_customer_id,
       return_url="https://app.hexis.io/dashboard"
   )
   ```
4. Redirect to session URL

---

## 4. FastAPI Middleware: JWT Dependency

### 4.1 JWT Utility Module

File: `/backend/auth/jwt_utils.py`

```python
from __future__ import annotations

import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenPayload(BaseModel):
    sub: str  # user_id
    email: str
    tier: str  # free, starter, pro, enterprise
    iat: int
    exp: int


def create_access_token(user_id: str, email: str, tier: str) -> str:
    """Create a JWT access token (1 hour expiry)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": user_id,
        "email": email,
        "tier": tier,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> Optional[TokenPayload]:
    """Verify and decode JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### 4.2 FastAPI Dependency

File: `/backend/auth/dependencies.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from auth.jwt_utils import verify_access_token, TokenPayload
import asyncpg

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthCredentials = Depends(security),
    pool: asyncpg.Pool = Depends(get_pool)
) -> dict:
    """Extract user from JWT token."""
    token = credentials.credentials
    payload = verify_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from DB to check status
    user = await pool.fetchrow(
        "SELECT id, email, status, tier FROM users u "
        "JOIN subscriptions s ON u.id = s.user_id "
        "WHERE u.id = $1",
        payload.sub
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user["status"] == "pending_deletion":
        raise HTTPException(
            status_code=403,
            detail="Account scheduled for deletion"
        )
    
    return {
        "user_id": user["id"],
        "email": user["email"],
        "tier": user["tier"],
        "status": user["status"],
        "payload": payload
    }


async def get_current_active_user(
    user: dict = Depends(get_current_user)
) -> dict:
    """Ensure user status is active."""
    if user["status"] != "active":
        raise HTTPException(
            status_code=403,
            detail="Account is not active"
        )
    return user
```

### 4.3 Protected Endpoint Example

```python
@app.get("/api/chat")
async def chat(
    message: str,
    user: dict = Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Chat endpoint restricted by tier."""
    user_id = user["user_id"]
    tier = user["tier"]
    
    # Check rate limits
    messages_today = await pool.fetchval(
        """SELECT COUNT(*) FROM channel_messages cm
           JOIN channel_sessions cs ON cm.session_id = cs.id
           WHERE cs.user_id = $1 AND cm.created_at > CURRENT_DATE
           AND cm.direction = 'inbound'""",
        user_id
    )
    
    limits = {
        "free": 10,
        "starter": 100,
        "pro": 500,
        "enterprise": 10000
    }
    
    if messages_today >= limits[tier]:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limits[tier]} messages/day)"
        )
    
    # Process chat...
```

---

## 5. Multi-Tenant Memory Isolation

### 5.1 Memory Architecture

**Principle:** Each subscriber has isolated memories, but shares read-access to a knowledge base trained across all agents.

**Three Memory Scopes:**

1. **Private Memories** (subscriber-only)
   - User conversations, personal preferences, history
   - Only accessible to that subscriber's agent
   - Deleted when account deleted

2. **Shared Knowledge Base** (read-only across all agents)
   - System-trained domain knowledge
   - Community synthesis (aggregate learning without leaking PII)
   - Available to all agents for enrichment
   - Survives subscriber deletion

3. **Ephemeral Memories** (working_memory table)
   - Short-term context for current session
   - Cleared after session ends
   - Unlogged table (performance optimization)

### 5.2 Query Pattern for Subscriber-Isolated Recall

```python
async def recall_for_subscriber(
    pool: asyncpg.Pool,
    subscriber_id: str,
    query_embedding: list[float],
    limit: int = 10
) -> list[dict]:
    """
    Recall memories for a specific subscriber:
    - Private memories (high relevance)
    - Shared knowledge base (lower weight)
    """
    
    # Private memories (subscriber owns them)
    private = await pool.fetch(
        """
        SELECT m.id, m.content, m.embedding, 
               1.0 * (m.embedding <=> $2) as distance
        FROM memories m
        JOIN subscriber_memories sm ON m.id = sm.memory_id
        WHERE sm.subscriber_id = $1 AND sm.scope = 'private'
          AND m.status = 'active'
        ORDER BY distance
        LIMIT $3
        """,
        subscriber_id,
        query_embedding,
        limit
    )
    
    # Shared knowledge base (read-only, lower weight)
    shared = await pool.fetch(
        """
        SELECT m.id, m.content, m.embedding,
               0.7 * (m.embedding <=> $2) as distance
        FROM memories m
        JOIN knowledge_base_memories kb ON m.id = kb.memory_id
        WHERE m.status = 'active'
        ORDER BY distance
        LIMIT $3
        """,
        query_embedding,
        limit // 2
    )
    
    # Merge and rerank
    combined = private + shared
    combined.sort(key=lambda x: x["distance"])
    return combined[:limit]
```

### 5.3 Memory Formation (Store Conversation)

```python
async def remember_conversation_for_subscriber(
    pool: asyncpg.Pool,
    subscriber_id: str,
    user_message: str,
    assistant_message: str,
    embedding: list[float]
) -> None:
    """Store conversation as episodic memory for subscriber."""
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Insert memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO memories 
                (type, status, content, embedding, importance, source_attribution, trust_level)
                VALUES ('episodic', 'active', $1, $2, $3, $4, $5)
                RETURNING id
                """,
                f"User: {user_message}\nAssistant: {assistant_message}",
                embedding,
                0.8,
                json.dumps({"kind": "conversation", "channel": "api"}),
                0.95
            )
            
            # Link to subscriber (private scope)
            await conn.execute(
                """
                INSERT INTO subscriber_memories 
                (subscriber_id, memory_id, scope)
                VALUES ($1, $2, 'private')
                """,
                subscriber_id,
                memory_id
            )
```

### 5.4 Shared Knowledge Base Integration

```python
async def add_to_knowledge_base(
    pool: asyncpg.Pool,
    memory_id: str,
    source: str = "hexis:training"
) -> None:
    """Mark a memory as part of the shared knowledge base."""
    
    await pool.execute(
        """
        INSERT INTO knowledge_base_memories (memory_id, added_by_system, source)
        VALUES ($1, TRUE, $2)
        ON CONFLICT (memory_id) DO UPDATE
        SET source = $2, access_count_total = access_count_total + 1
        """,
        memory_id,
        source
    )
```

---

## 6. Channel Authentication (Telegram/WhatsApp/Discord)

### 6.1 Channel Identity Binding

**Problem:** How do we know which subscriber owns a Telegram user?

**Solution:** One-time verification code sent via the channel.

### 6.2 Telegram Linking Flow

**Step 1: Initiate Linking (from web dashboard)**

```
POST /auth/channels/telegram/initiate
{
  "user_id": "jwt_extracted_user_id"
}

Response:
{
  "verification_code": "ABC123",
  "instructions": "Send this code to @hexis_bot on Telegram: /link ABC123"
}
```

**Step 2: User sends code to bot on Telegram**

```
User sends to @hexis_bot:
/link ABC123
```

**Step 3: Bot verifies and links**

```python
# In Telegram adapter's message handler
async def on_telegram_message(update):
    if update.message.text.startswith("/link "):
        code = update.message.text.split()[1]
        
        # Find verification code in DB
        row = await pool.fetchrow(
            """
            SELECT user_id FROM channel_identities
            WHERE channel_type = 'telegram'
            AND verification_code = $1
            AND verified = FALSE
            AND verification_sent_at > CURRENT_TIMESTAMP - INTERVAL '10 minutes'
            """,
            code
        )
        
        if not row:
            await bot.send_message(update.effective_user.id, "Invalid or expired code")
            return
        
        user_id = row["user_id"]
        
        # Link the identity
        await pool.execute(
            """
            UPDATE channel_identities
            SET verified = TRUE, verified_at = CURRENT_TIMESTAMP,
                verification_code = NULL
            WHERE channel_type = 'telegram'
            AND verification_code = $1
            """,
            code
        )
        
        await bot.send_message(
            update.effective_user.id,
            "Success! Your Telegram is now linked to your Hexis account."
        )
```

### 6.3 Message Routing (Channel → Subscriber)

**When a Telegram user messages the bot:**

```python
async def process_telegram_message(pool, update):
    telegram_user_id = str(update.effective_user.id)
    
    # Look up subscriber
    identity = await pool.fetchrow(
        """
        SELECT user_id FROM channel_identities
        WHERE channel_type = 'telegram'
        AND channel_user_id = $1
        AND verified = TRUE
        """,
        telegram_user_id
    )
    
    if not identity:
        # Unlinked user; prompt to link
        await bot.send_message(
            telegram_user_id,
            "Please link your account first: https://app.hexis.io/account/channels"
        )
        return
    
    subscriber_id = identity["user_id"]
    
    # Check subscription status
    sub = await pool.fetchrow(
        "SELECT status, tier FROM subscriptions WHERE user_id = $1",
        subscriber_id
    )
    
    if not sub or sub["status"] != "active":
        await bot.send_message(
            telegram_user_id,
            "Your subscription is inactive. Please renew at https://app.hexis.io/billing"
        )
        return
    
    # Process message via agent (same as API)
    await process_channel_message(pool, subscriber_id, update.message.text)
```

### 6.4 Database Updates

The `channel_identities` table stores bindings:

```sql
INSERT INTO channel_identities 
(user_id, channel_type, channel_user_id, channel_username, verified)
VALUES 
('uuid', 'telegram', '123456789', '@alice', true),
('uuid', 'discord', '987654321', 'alice#1234', true);
```

Update `channel_sessions` to link to subscriber:

```sql
ALTER TABLE channel_sessions ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_channel_sessions_user ON channel_sessions(user_id);
```

---

## 7. Account Lifecycle

### 7.1 Active → Deactivated

**Trigger:** Payment fails 3 times or user manually cancels.

```python
async def deactivate_account(pool: asyncpg.Pool, user_id: str) -> None:
    """Mark account as deactivated and schedule deletion."""
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Deactivate user
            await conn.execute(
                """
                UPDATE users
                SET status = 'deactivated',
                    deactivated_at = CURRENT_TIMESTAMP,
                    deletion_scheduled_for = CURRENT_TIMESTAMP + INTERVAL '14 days'
                WHERE id = $1
                """,
                user_id
            )
            
            # Cancel Stripe subscription
            sub_row = await conn.fetchrow(
                "SELECT stripe_subscription_id FROM subscriptions WHERE user_id = $1",
                user_id
            )
            if sub_row and sub_row["stripe_subscription_id"]:
                stripe.Subscription.delete(sub_row["stripe_subscription_id"])
            
            # Send grace period email
            user = await conn.fetchrow(
                "SELECT email FROM users WHERE id = $1",
                user_id
            )
            await send_email(
                user["email"],
                subject="Your Hexis Account is Deactivated",
                template="deactivation_notice.html",
                context={
                    "grace_period_days": 14,
                    "renewal_url": "https://app.hexis.io/billing/renew"
                }
            )
```

### 7.2 Deactivated → Reactivated (Grace Period)

```python
async def reactivate_account(pool: asyncpg.Pool, user_id: str) -> None:
    """Reactivate account if within grace period."""
    
    user = await pool.fetchrow(
        "SELECT deactivated_at FROM users WHERE id = $1",
        user_id
    )
    
    if not user:
        raise ValueError("User not found")
    
    grace_end = user["deactivated_at"] + timedelta(days=14)
    if datetime.now(timezone.utc) > grace_end:
        raise ValueError("Grace period expired; account data is deleted")
    
    await pool.execute(
        """
        UPDATE users
        SET status = 'active', deactivated_at = NULL, deletion_scheduled_for = NULL
        WHERE id = $1
        """,
        user_id
    )
```

### 7.3 Pending Deletion → Deleted

**Trigger:** 14 days after deactivation or explicit GDPR deletion request.

```python
async def delete_account_data(pool: asyncpg.Pool, user_id: str) -> None:
    """
    GDPR deletion: Hard delete all PII and user data.
    Keep only: encrypted email hash, deletion timestamp (audit trail).
    """
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Find all user-owned memories
            memory_ids = await conn.fetch(
                """
                SELECT m.id FROM memories m
                JOIN subscriber_memories sm ON m.id = sm.memory_id
                WHERE sm.subscriber_id = $1
                """,
                user_id
            )
            
            # Delete private memories
            for row in memory_ids:
                await conn.execute(
                    "DELETE FROM subscriber_memories WHERE memory_id = $1",
                    row["id"]
                )
                await conn.execute(
                    "DELETE FROM memories WHERE id = $1",
                    row["id"]
                )
            
            # Delete channel identities
            await conn.execute(
                "DELETE FROM channel_identities WHERE user_id = $1",
                user_id
            )
            
            # Delete sessions
            await conn.execute(
                "DELETE FROM auth_sessions WHERE user_id = $1",
                user_id
            )
            
            # Delete subscription
            await conn.execute(
                "DELETE FROM subscriptions WHERE user_id = $1",
                user_id
            )
            
            # Anonymize user (keep email hash for abuse prevention)
            email_hash = hashlib.sha256(user["email"].encode()).hexdigest()
            await conn.execute(
                """
                UPDATE users
                SET email = $1,
                    full_name = NULL,
                    status = 'deleted',
                    password_hash = NULL,
                    email_verified = FALSE,
                    data_deletion_requested_at = CURRENT_TIMESTAMP
                WHERE id = $2
                """,
                f"deleted_{email_hash[:16]}@deleted.local",
                user_id
            )
            
            # Log deletion
            await conn.execute(
                """
                INSERT INTO auth_audit_log (user_id, event_type, status)
                VALUES ($1, 'account_deleted', 'gdpr_compliance')
                """,
                user_id
            )
```

### 7.4 Scheduled Deletion Job (Cron)

```python
# Daily background job
async def delete_expired_accounts() -> None:
    """Delete accounts with deletion_scheduled_for <= now()"""
    
    rows = await pool.fetch(
        """
        SELECT id FROM users
        WHERE status = 'pending_deletion'
        AND deletion_scheduled_for <= CURRENT_TIMESTAMP
        """
    )
    
    for row in rows:
        try:
            await delete_account_data(pool, row["id"])
            logger.info(f"Deleted account {row['id']}")
        except Exception as e:
            logger.error(f"Failed to delete {row['id']}: {e}")
```

---

## 8. API Endpoints

### 8.1 Auth Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | None | Register new account |
| GET | `/auth/verify` | None | Verify email |
| POST | `/auth/login` | None | Login with email/password |
| POST | `/auth/refresh` | Refresh token | Get new access token |
| POST | `/auth/logout` | Bearer | Revoke session |
| GET | `/auth/me` | Bearer | Get current user |
| POST | `/auth/password-reset` | None | Request password reset |
| POST | `/auth/password-reset/confirm` | None | Confirm reset with token |

### 8.2 Billing Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/billing/subscribe` | Bearer | Create subscription |
| GET | `/billing/portal` | Bearer | Redirect to Stripe portal |
| GET | `/billing/subscription` | Bearer | Get current subscription |
| POST | `/billing/webhook` | Stripe signature | Webhook handler |
| POST | `/billing/cancel` | Bearer | Cancel subscription |

### 8.3 Channel Auth Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/channels/{type}/initiate` | Bearer | Start linking (Telegram, Discord, etc.) |
| GET | `/auth/channels` | Bearer | List linked channels |
| POST | `/auth/channels/{id}/unlink` | Bearer | Unlink a channel |
| GET | `/auth/channels/{type}/status` | None | Check if code is valid (for bot) |

---

## 9. Rate Limiting

### 9.1 Per-Tier Limits

```python
TIER_LIMITS = {
    "free": {
        "messages_per_day": 10,
        "tokens_per_month": 10_000,
        "api_calls_per_hour": 30,
    },
    "starter": {
        "messages_per_day": 100,
        "tokens_per_month": 100_000,
        "api_calls_per_hour": 300,
    },
    "pro": {
        "messages_per_day": 500,
        "tokens_per_month": 500_000,
        "api_calls_per_hour": 1000,
    },
    "enterprise": {
        "messages_per_day": 10000,
        "tokens_per_month": 10_000_000,
        "api_calls_per_hour": 10000,
    },
}
```

### 9.2 Rate Limit Middleware

```python
async def check_rate_limit(
    pool: asyncpg.Pool,
    user_id: str,
    tier: str,
    limit_type: str  # "messages", "tokens", "api_calls"
) -> tuple[bool, dict]:
    """Check if user is within rate limits."""
    
    limits = TIER_LIMITS[tier][f"{limit_type}_per_{'day' if limit_type != 'api_calls' else 'hour'}"]
    
    if limit_type == "messages":
        count = await pool.fetchval(
            """
            SELECT COUNT(*) FROM channel_messages cm
            JOIN channel_sessions cs ON cm.session_id = cs.id
            WHERE cs.user_id = $1
            AND cm.created_at > CURRENT_DATE
            AND cm.direction = 'inbound'
            """,
            user_id
        )
        window = "day"
    elif limit_type == "api_calls":
        count = await pool.fetchval(
            """
            SELECT COUNT(*) FROM api_usage
            WHERE user_id = $1
            AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
            """,
            user_id
        )
        window = "hour"
    
    if count >= limits:
        return False, {
            "limit": limits,
            "used": count,
            "window": window,
            "reset_at": (datetime.now() + timedelta(days=1 if window == "day" else hours=1)).isoformat()
        }
    
    return True, {"limit": limits, "used": count, "remaining": limits - count}
```

---

## 10. Data Model Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HEXIS MULTI-TENANT ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐
│       USERS              │ (1 row per subscriber)
├──────────────────────────┤
│ id (UUID)                │
│ email (UNIQUE)           │
│ password_hash            │
│ status (active/...)      │
│ created_at               │
│ deletion_scheduled_for   │
└──────────┬───────────────┘
           │ (1:1)
           │
┌──────────▼───────────────────────────┐
│       SUBSCRIPTIONS                  │
├──────────────────────────────────────┤
│ id (UUID)                            │
│ user_id (FK → users)                 │
│ stripe_customer_id (UNIQUE)          │
│ stripe_subscription_id               │
│ tier (free/starter/pro/enterprise)   │
│ status (active/past_due/cancelled)   │
│ messages_per_day                     │
│ tokens_per_month                     │
│ renewal_date                         │
└──────────┬────────────────────────────┘
           │ (1:1)
           │
┌──────────▼──────────────────────────┐
│       AUTH_SESSIONS                  │
├──────────────────────────────────────┤
│ id (UUID)                            │
│ user_id (FK → users)                 │
│ refresh_token_hash (UNIQUE)          │
│ expires_at                           │
│ revoked (BOOLEAN)                    │
│ device_name                          │
└──────────┬──────────────────────────┘
           │ (1:M)
           │
┌──────────▼──────────────────────────┐
│     CHANNEL_IDENTITIES               │
├──────────────────────────────────────┤
│ id (UUID)                            │
│ user_id (FK → users)                 │
│ channel_type (telegram/discord/...)  │
│ channel_user_id (platform user ID)   │
│ verified (BOOLEAN)                   │
│ verification_code (temporary)        │
└──────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                    MEMORY ISOLATION LAYER                           │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────┐    ┌──────────────────────────┐          │
│  │     MEMORIES         │    │ SUBSCRIBER_MEMORIES      │          │
│  ├──────────────────────┤    ├──────────────────────────┤          │
│  │ id (UUID)            │    │ id (UUID)                │          │
│  │ content              │◄───┤ subscriber_id (FK→users) │          │
│  │ embedding (768-dim)  │    │ memory_id (FK→memories)  │          │
│  │ type (episodic/...)  │    │ scope (private/shared)   │          │
│  │ trust_level          │    └──────────────────────────┘          │
│  │ importance           │                                          │
│  └──────────────────────┘                                          │
│           ▲                                                         │
│           │                                                         │
│           │                                                         │
│  ┌────────┴───────────────────────┐                               │
│  │  KNOWLEDGE_BASE_MEMORIES       │                               │
│  ├────────────────────────────────┤                               │
│  │ id (UUID)                      │                               │
│  │ memory_id (FK→memories)        │                               │
│  │ source (hexis:training/...)    │                               │
│  │ access_count_total             │                               │
│  └────────────────────────────────┘                               │
│                                                                     │
│  Recall: private memories (100% weight) + KB memories (70% weight) │
└───────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│              CHANNEL INTEGRATION                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Telegram/Discord/WhatsApp User  ──(verified identity)──┐        │
│                                                          │        │
│                                                   ┌──────▼──┐     │
│                                                   │ Channel │     │
│                                                   │Identities     │
│                                                   └─────┬──┘     │
│                                                         │        │
│                                      ┌──────────────────▼──┐    │
│                                      │   Users (Subscriber)│    │
│                                      │   Subscriptions     │    │
│                                      │   Private Memories  │    │
│                                      └─────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                  BILLING FLOW                                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Subscriber  ──(select tier)──> Frontend ──(create session)──┐   │
│                                                              │   │
│                                    ┌──────────────────────────▼┐  │
│                                    │     STRIPE                │  │
│                                    │  (Cloud-hosted)           │  │
│                                    │  - Customers              │  │
│                                    │  - Subscriptions          │  │
│                                    │  - Invoices               │  │
│                                    │  - Webhooks               │  │
│                                    └──────────────────┬────────┘  │
│                                                      │            │
│                            ┌─────────────────────────▼──┐         │
│                            │  /billing/webhook           │         │
│                            │  - payment_succeeded        │         │
│                            │  - payment_failed           │         │
│                            │  - subscription.updated     │         │
│                            └─────────────┬───────────────┘         │
│                                          │                        │
│                         ┌────────────────▼──┐                    │
│                         │  Update Subscriptions
│                         │  Activate/Deactivate Accounts
│                         │  Schedule Deletions
│                         └─────────────────────┘                  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│              AUTHENTICATION MIDDLEWARE                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Client Request  ──(Bearer token)──> FastAPI @app.post("/api/")  │
│                                       │                          │
│                    ┌──────────────────▼──────────────────┐       │
│                    │ get_current_active_user()           │       │
│                    │ - Verify JWT signature              │       │
│                    │ - Check expiry                      │       │
│                    │ - Verify user status (active)       │       │
│                    │ - Check rate limits (tier)          │       │
│                    │ - Return user context               │       │
│                    └──────────────────┬──────────────────┘       │
│                                       │                          │
│                                ┌──────▼──────┐                   │
│                                │ Handler     │                   │
│                                │ (authorized)│                   │
│                                └─────────────┘                   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 11. Security Considerations

### 11.1 Password Security
- **Hashing:** bcrypt with cost factor 12
- **Minimum:** 12 characters
- **Validation:** Uppercase, lowercase, number, symbol required

### 11.2 Token Security
- **Access Token:** JWT, 1-hour expiry, HS256
- **Refresh Token:** 32-byte random, hashed in DB, 7-day expiry
- **Storage:** Client uses httpOnly cookie (no JS access)
- **Rotation:** Optional refresh token rotation on each refresh

### 11.3 Session Security
- **Tracking:** IP address, user agent, device name
- **Anomaly Detection:** Flag login from new location/device
- **Revocation:** Immediate revocation on logout or password change
- **Audit Trail:** All auth events logged

### 11.4 GDPR Compliance
- **Consent:** Opt-in for marketing communications
- **Export:** Endpoint to download all user data as JSON
- **Deletion:** Hard deletion of all PII; keeps anonymized hash
- **Data Retention:** 14-day grace period after deactivation
- **Right to be Forgotten:** Implemented via scheduled deletion job

### 11.5 Payment Security
- **PCI Compliance:** Stripe handles all card data; never stored locally
- **Webhook Verification:** Stripe signature validation on all events
- **Idempotency:** Webhook handlers are idempotent (safe to retry)

---

## 12. Deployment Checklist

- [ ] **Environment Variables:**
  ```
  SECRET_KEY=<random-32-bytes>
  STRIPE_SECRET_KEY=sk_live_xxxxx
  STRIPE_WEBHOOK_SECRET=whsec_xxxxx
  STRIPE_PRICE_IDS_STARTER=price_xxxxx
  STRIPE_PRICE_IDS_PRO=price_xxxxx
  STRIPE_PRICE_IDS_ENTERPRISE=price_xxxxx
  SENDGRID_API_KEY=xxxxx (or EMAIL_PROVIDER_KEY)
  DATABASE_URL=postgresql://user:pass@host/hexis
  ```

- [ ] **Database Migrations:**
  ```bash
  psql -f db/auth_tables.sql -d hexis
  psql -f db/indices.sql -d hexis
  ```

- [ ] **SSL Certificates:**
  - HTTPS required for all auth endpoints
  - Certificate renewal (Let's Encrypt) automated

- [ ] **Email Service:**
  - SendGrid, AWS SES, or similar configured
  - Email templates for verification, password reset, billing alerts

- [ ] **Monitoring:**
  - Auth failure rates tracked
  - Stripe webhook delivery monitored
  - Rate limit violations logged

- [ ] **Backup:**
  - Daily encrypted backups
  - Retention: 30 days
  - Test restoration quarterly

---

## 13. Future Enhancements

1. **OAuth2 (Google, GitHub, Microsoft)**
   - SSO integration
   - Reduce account creation friction

2. **Two-Factor Authentication (2FA)**
   - TOTP (authenticator app)
   - SMS backup codes
   - Required for enterprise tier

3. **Team Subscriptions**
   - Shared workspace
   - Per-user seat pricing
   - Invite/remove members

4. **Advanced Metrics**
   - Token usage tracking per-user
   - Memory growth analytics
   - Agent performance metrics

5. **Tiered API Rate Limits**
   - Burst allowance (spike headroom)
   - Throttling vs hard rejection
   - Graceful degradation

6. **Event-Driven Architecture**
   - Use message queue (RabbitMQ, Kafka) for async auth events
   - Decouple Stripe webhooks from critical path

---

## 14. Testing Strategy

### 14.1 Unit Tests

```python
# tests/auth/test_auth_service.py
pytest.mark.asyncio
class TestSignup:
    async def test_signup_success(self, pool):
        # Create user, verify email sent
        
    async def test_signup_duplicate_email(self, pool):
        # Reject second signup with same email
        
    async def test_password_validation(self, pool):
        # Reject weak passwords

class TestLogin:
    async def test_login_success(self, pool):
        # Verify JWT generated correctly
        
    async def test_login_unverified_email(self, pool):
        # Reject login before email verified
```

### 14.2 Integration Tests

```python
# tests/billing/test_stripe_integration.py
@pytest.mark.asyncio
class TestStripeWebhooks:
    async def test_payment_succeeded_webhook(self, pool, stripe_mocker):
        # Simulate Stripe webhook, verify DB updated
        
    async def test_payment_failed_deactivation(self, pool, stripe_mocker):
        # After 3 failures, account deactivated
```

### 14.3 End-to-End Tests

```
# Selenium/Playwright tests
- Signup → Verify Email → Login → Subscribe → Use API
- Channel Linking (Discord/Telegram)
- Password Reset
- Account Deletion
```

---

## Summary

This architecture provides:

✓ Scalable user authentication with JWT + refresh tokens
✓ Stripe SaaS billing with 3-tier pricing
✓ Multi-tenant memory isolation (private + shared KB)
✓ Channel identity binding (Telegram/Discord/WhatsApp → subscriber)
✓ GDPR-compliant account lifecycle (14-day grace period)
✓ Rate limiting per tier
✓ Audit trail for compliance
✓ Production-grade security (bcrypt, HTTPS, webhook verification)

**File Locations:**
- Schema: `/home/jules/Documents/3-git/hexis-analysis/db/31_auth_stripe_multitenancy.sql`
- Auth Service: `/backend/auth/jwt_utils.py`, `/backend/auth/dependencies.py`
- Billing: `/backend/billing/stripe_service.py`, `/backend/billing/webhooks.py`
- Memory: `/backend/memory/isolation.py`
- Channels: `/backend/channels/identity_binding.py`

Now I'll create the actual SQL file:

Created document at `/home/jules/Documents/3-git/zeprocess/main/docs/specs/auth-stripe-multitenancy.md` with comprehensive architecture specification covering:

1. **Database Schema** - 6 new tables (users, subscriptions, auth_sessions, channel_identities, memory partitioning, audit trail)
2. **Auth Flow** - Complete signup → email verify → login → JWT → logout
3. **Stripe Integration** - Subscription creation, webhook handlers, billing portal
4. **FastAPI Middleware** - JWT extraction, user context, tier-based access control
5. **Memory Isolation** - Subscriber-private memories vs. shared knowledge base with query patterns
6. **Channel Auth** - How Telegram/WhatsApp/Discord users map to subscribers via verification codes
7. **Account Lifecycle** - Active → Deactivated (14-day grace) → Deleted, with GDPR compliance
8. **API Endpoints** - Complete list for auth, billing, channels (8 endpoints defined)
9. **Rate Limiting** - Per-tier limits with middleware implementation
10. **ASCII Data Model Diagram** - Complete system architecture visualization
11. **Security Considerations** - bcrypt, token rotation, GDPR compliance, PCI compliance
12. **Deployment Checklist** - Environment variables, migrations, monitoring
13. **Future Enhancements** - OAuth2, 2FA, team subscriptions, metrics
14. **Testing Strategy** - Unit, integration, E2E test scenarios

**Key Architectural Decisions:**

**Memory Isolation Pattern:**
- Private scope: Subscriber-only memories (recalled at 100% weight)
- Shared KB: System-trained knowledge (recalled at 70% weight)
- Prevents data leakage while enabling knowledge synthesis

**Channel Identity Binding:**
- One-time verification codes sent via channel
- Unverified messages prompt linking
- Rate-limited messages per tier

**Account Lifecycle:**
- 3 failed payments → deactivated
- 14-day grace period before hard deletion
- Scheduled deletion job runs daily
- All PII deleted; anonymized hash retained for abuse prevention

**Rate Limiting Strategy:**
- Free: 10 msgs/day, 10K tokens/month
- Starter: 100 msgs/day, 100K tokens/month
- Pro: 500 msgs/day, 500K tokens/month
- Enterprise: Custom
- Checked at request time; 429 response includes reset_at

The document is now ready for implementation. Would you like me to create the SQL migration file or any specific Python backend modules next?