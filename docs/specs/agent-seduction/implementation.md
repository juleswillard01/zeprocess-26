# Seduction Agent: Implementation Guide (Step-by-Step)

**Document**: 04-seduction-agent-implementation-guide.md
**Date**: 14 mars 2026
**Audience**: Development team
**Est. Time to Implement**: 40-60 hours

---

## Quick Start (30 mins)

### Your First Run: Hello Agent

```bash
# 1. Clone & setup
cd /home/jules/Documents/3-git/zeprocess/main
source .venv/bin/activate

# 2. Ensure PostgreSQL is running
psql -h localhost -U zeprocess -d zeprocess -c "SELECT 1"

# 3. Create agent module
mkdir -p agents/{nodes,tools,prompts,config}
touch agents/__init__.py agents/seduction_agent.py

# 4. Run test
python agents/seduction_agent.py --test --input "C'est quoi la meilleure ouverture?"
```

---

## Phase 1: Core Infrastructure (Days 1-2)

### 1.1 Set Up Python Module Structure

**File**: `agents/config/__init__.py`
```python
# Configuration module
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / ".logs"

# Create if needed
LOGS_DIR.mkdir(exist_ok=True)
```

**File**: `agents/config/constants.py`
```python
from datetime import timedelta
from typing import Literal

# Quality thresholds
QUALITY_THRESHOLDS = {
    "rag_confidence_min": 0.5,
    "tone_confidence_min": 0.7,
    "quality_checks_pass_threshold": 4,  # out of 5
    "max_regenerations": 2,
}

# Latency targets (seconds)
LATENCY_TARGETS = {
    "intake": 0.5,
    "contextualize": 2.0,
    "route": 0.2,
    "execute": 5.0,
    "quality_gate": 2.0,
    "total": 10.0,
}

# Content constraints
CONTENT_LIMITS = {
    "dm_max_words": 50,
    "post_max_words": 300,
    "story_script_max_words": 100,
    "reel_script_max_words": 150,
}

# RAG parameters
RAG_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.6,
    "embedding_model": "all-MiniLM-L6-v2",
}

# API limits
API_DAILY_BUDGET_USD = 100.0  # Dollar cap per day
API_REQUEST_TIMEOUT_SEC = 15
```

**File**: `agents/config/models.py`
```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RagChunk(BaseModel):
    chunk_id: str
    content: str
    similarity: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any]  # video_title, timestamp, playlist, etc


class ToolCall(BaseModel):
    name: str
    input: dict[str, Any]
    output: Any
    latency_ms: int
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: Optional[float] = None


class QualityCheck(BaseModel):
    name: str
    passed: bool
    reason: str
    score: Optional[float] = None


class AgentState(BaseModel):
    # Identifiers
    message_id: str
    sender_id: str
    run_id: str

    # Input
    message_text: str
    timestamp: datetime

    # Context
    sender_history: list[dict] = Field(default_factory=list)
    rag_chunks: list[RagChunk] = Field(default_factory=list)
    rag_sources: list[str] = Field(default_factory=list)

    # Routing
    role: Literal["RESPONDER", "CREATOR", "QUALIFIER", "IDLE"] = "IDLE"
    trigger_type: Literal["DM", "SCHEDULED", "EXTERNAL"] = "DM"

    # Execution
    tool_calls: list[ToolCall] = Field(default_factory=list)
    output_text: str = ""
    output_type: Literal["dm", "post", "story", "reel", "none"] = "none"

    # Quality
    rag_confidence: float = 0.0
    tone_confidence: float = 0.0
    quality_checks: list[QualityCheck] = Field(default_factory=list)
    quality_passed: bool = False
    regenerate_count: int = 0

    # Errors
    error: Optional[str] = None
    fallback_triggered: bool = False

    # Metadata
    memory_id: Optional[str] = None
    langfuse_trace_id: Optional[str] = None


class ProspectClassification(BaseModel):
    user_id: str
    is_qualified: bool
    confidence: float
    reason: str
    signals: dict[str, Any]
    next_action: Literal["follow_up", "send_offer", "nurture", "wait"]
    classified_at: datetime
```

### 1.2 Implement Base Logger

**File**: `agents/config/logging.py`
```python
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from agents.config import LOGS_DIR


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Setup JSON logging for production use."""

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # JSON formatter
    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "extra": {
                    k: v
                    for k, v in record.__dict__.items()
                    if k not in [
                        "name",
                        "msg",
                        "args",
                        "created",
                        "filename",
                        "funcName",
                        "levelname",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "message",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                    ]
                },
            }

            if record.exc_info:
                data["exception"] = self.formatException(record.exc_info)

            return json.dumps(data, ensure_ascii=False, default=str)

    # File handler
    log_file = LOGS_DIR / f"{name}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Console handler (non-JSON for dev)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(console_handler)

    return logger
```

---

## Phase 2: Database Layer (Days 2-3)

### 2.1 Database Schema

**File**: `database/schema.sql`
```sql
-- Main tables for Agent SEDUCTION

-- 1. Instagram DM storage
CREATE TABLE IF NOT EXISTS instagram_dms (
    id BIGSERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    sender_id VARCHAR(255) NOT NULL,
    sender_name VARCHAR(255),
    message_text TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_processed BOOLEAN DEFAULT FALSE,

    INDEX idx_sender_id (sender_id),
    INDEX idx_received_at (received_at)
);

-- 2. Agent run history
CREATE TABLE IF NOT EXISTS agent_conversations (
    id BIGSERIAL PRIMARY KEY,
    sender_id VARCHAR(255) NOT NULL,
    run_id VARCHAR(255) UNIQUE NOT NULL,

    -- State snapshot
    state_json JSONB,

    -- Metadata
    role VARCHAR(50),
    trigger_type VARCHAR(50),

    -- Quality metrics
    rag_confidence FLOAT,
    tone_confidence FLOAT,
    quality_passed BOOLEAN,
    regenerate_count INT,

    -- Timestamps
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_ms INT,

    INDEX idx_sender_id (sender_id),
    INDEX idx_run_id (run_id),
    INDEX idx_ended_at (ended_at)
);

-- 3. Agent outputs
CREATE TABLE IF NOT EXISTS agent_outputs (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,

    output_type VARCHAR(50),
    output_text TEXT,

    -- Traceability
    rag_chunks_used JSONB,
    tools_called JSONB,

    -- Posting
    posted_at TIMESTAMP,
    instagram_post_id VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id) REFERENCES agent_conversations(run_id)
);

-- 4. Prospect classifications (CRM)
CREATE TABLE IF NOT EXISTS prospect_classifications (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,

    is_qualified BOOLEAN,
    confidence FLOAT,
    reason TEXT,
    signals JSONB,
    next_action VARCHAR(50),

    classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    INDEX idx_is_qualified (is_qualified)
);

-- 5. User conversation memory
CREATE TABLE IF NOT EXISTS user_memory (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,

    -- Last N conversations
    recent_topics JSONB,  -- [{topic, timestamp, confidence}]
    pain_points JSONB,    -- [{pain_point, frequency}]
    interests JSONB,      -- [{interest, frequency}]

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id)
);
```

**File**: `agents/db.py`
```python
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

import psycopg
from psycopg import sql
from psycopg.pool import AsyncConnectionPool

from agents.config.logging import setup_logging
from agents.config.models import AgentState, ProspectClassification, RagChunk

logger = setup_logging(__name__)


class Database:
    """Async PostgreSQL wrapper with connection pooling."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "zeprocess",
        user: str = "zeprocess",
        password: str = "",
        min_size: int = 5,
        max_size: int = 20,
    ):
        self.pool = AsyncConnectionPool(
            conninfo=f"postgresql://{user}:{password}@{host}:{port}/{database}",
            min_size=min_size,
            max_size=max_size,
        )

    async def init(self):
        """Initialize connection pool."""
        await self.pool.open()
        logger.info("Database pool initialized", extra={"pool_size": self.pool._cur_size})

    async def close(self):
        """Close connection pool."""
        await self.pool.close()

    @asynccontextmanager
    async def _get_connection(self):
        """Get connection from pool."""
        async with self.pool.connection() as conn:
            yield conn

    async def store_conversation(
        self, state: AgentState, duration_ms: int
    ) -> str:
        """Store agent run to database."""

        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO agent_conversations
                (sender_id, run_id, state_json, role, trigger_type,
                 rag_confidence, tone_confidence, quality_passed,
                 regenerate_count, started_at, ended_at, duration_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    state.sender_id,
                    state.run_id,
                    json.dumps(state.model_dump(), default=str),
                    state.role,
                    state.trigger_type,
                    state.rag_confidence,
                    state.tone_confidence,
                    state.quality_passed,
                    state.regenerate_count,
                    state.timestamp,
                    datetime.now(),
                    duration_ms,
                ),
            )

        logger.info("Conversation stored", extra={"run_id": state.run_id})
        return state.run_id

    async def store_output(
        self,
        run_id: str,
        output_type: str,
        output_text: str,
        rag_chunks: list[RagChunk],
        tools_called: list[str],
    ) -> None:
        """Store agent output."""

        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO agent_outputs
                (run_id, output_type, output_text, rag_chunks_used, tools_called)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    output_type,
                    output_text,
                    json.dumps(
                        [c.model_dump() for c in rag_chunks], default=str
                    ),
                    json.dumps(tools_called),
                ),
            )

    async def get_user_history(
        self, user_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch recent DMs from user."""

        async with self._get_connection() as conn:
            rows = await conn.execute(
                """
                SELECT run_id, timestamp, output_text
                FROM agent_conversations
                WHERE sender_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )

        return [
            {"run_id": r[0], "timestamp": r[1], "text": r[2]}
            for r in await rows.fetchall()
        ]

    async def search_vectors(
        self,
        embedding: list[float],
        top_k: int = 5,
        similarity_threshold: float = 0.6,
    ) -> list[RagChunk]:
        """Search RAG chunks in pgvector."""

        async with self._get_connection() as conn:
            rows = await conn.execute(
                """
                SELECT id, content, similarity, metadata
                FROM rag_chunks
                WHERE 1 - (embedding <=> %s::vector) > %s
                ORDER BY 1 - (embedding <=> %s::vector) DESC
                LIMIT %s
                """,
                (embedding, similarity_threshold, embedding, top_k),
            )

        chunks = []
        for r in await rows.fetchall():
            metadata = json.loads(r[3])
            chunks.append(
                RagChunk(
                    chunk_id=r[0],
                    content=r[1],
                    similarity=float(r[2]),
                    metadata=metadata,
                )
            )

        return chunks

    async def store_prospect(
        self, classification: ProspectClassification
    ) -> None:
        """Store prospect classification."""

        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO prospect_classifications
                (user_id, is_qualified, confidence, reason, signals, next_action)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    is_qualified = EXCLUDED.is_qualified,
                    confidence = EXCLUDED.confidence,
                    reason = EXCLUDED.reason,
                    signals = EXCLUDED.signals,
                    next_action = EXCLUDED.next_action
                """,
                (
                    classification.user_id,
                    classification.is_qualified,
                    classification.confidence,
                    classification.reason,
                    json.dumps(classification.signals),
                    classification.next_action,
                ),
            )

        logger.info(
            "Prospect classified",
            extra={
                "user_id": classification.user_id,
                "is_qualified": classification.is_qualified,
            },
        )
```

---

## Phase 3: Nodes Implementation (Days 4-5)

### 3.1 Intake Node

**File**: `agents/nodes/intake.py`
```python
from __future__ import annotations

import uuid
from datetime import datetime

from agents.config.logging import setup_logging
from agents.config.models import AgentState
from agents.db import Database

logger = setup_logging(__name__)


async def intake_node(state: AgentState, db: Database) -> AgentState:
    """Parse input, load history, initialize state."""

    # Validate input
    if not state.message_text or len(state.message_text) > 2000:
        state.error = "Invalid message: empty or too long"
        state.fallback_triggered = True
        logger.warning(
            "INTAKE_VALIDATION_FAILED",
            extra={"message_id": state.message_id, "error": state.error},
        )
        return state

    # Generate run_id
    state.run_id = str(uuid.uuid4())

    # Load user conversation history
    try:
        history = await db.get_user_history(state.sender_id, limit=10)
        state.sender_history = history
    except Exception as e:
        logger.warning(
            "Failed to load user history",
            extra={"sender_id": state.sender_id, "error": str(e)},
        )
        state.sender_history = []

    logger.info(
        "INTAKE",
        extra={
            "run_id": state.run_id,
            "sender_id": state.sender_id,
            "message_length": len(state.message_text),
            "history_size": len(state.sender_history),
        },
    )

    return state
```

### 3.2 Contextualize Node

**File**: `agents/nodes/contextualize.py`
```python
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from agents.config.logging import setup_logging
from agents.config.models import AgentState
from agents.db import Database

logger = setup_logging(__name__)

# Load embedding model once (cache)
embedding_model = None


async def get_embedding_model():
    """Lazy load embedding model."""
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embedding_model


async def contextualize_node(state: AgentState, db: Database) -> AgentState:
    """RAG search, augment context."""

    if state.error:
        # Skip if intake failed
        return state

    try:
        # Embed query
        model = await get_embedding_model()
        embedding = model.encode(state.message_text, convert_to_numpy=False)

        # Vector search
        chunks = await db.search_vectors(
            embedding=embedding.tolist(),
            top_k=5,
            similarity_threshold=0.6,
        )

        state.rag_chunks = chunks
        state.rag_sources = [
            f"{c.metadata.get('video_title', 'Unknown')} @ {c.metadata.get('timestamp', '?')}"
            for c in chunks
        ]

        if chunks:
            state.rag_confidence = sum(c.similarity for c in chunks) / len(chunks)
        else:
            state.rag_confidence = 0.0
            logger.warning(
                "RAG_NO_MATCH",
                extra={"run_id": state.run_id, "query": state.message_text},
            )

    except Exception as e:
        logger.error(
            "CONTEXTUALIZE_ERROR",
            exc_info=True,
            extra={"run_id": state.run_id, "error": str(e)},
        )
        state.rag_confidence = 0.0
        state.rag_chunks = []

    logger.info(
        "CONTEXTUALIZE",
        extra={
            "run_id": state.run_id,
            "rag_chunks": len(state.rag_chunks),
            "rag_confidence": state.rag_confidence,
        },
    )

    return state
```

### 3.3 Route Node

**File**: `agents/nodes/route.py`
```python
from __future__ import annotations

from agents.config.logging import setup_logging
from agents.config.models import AgentState

logger = setup_logging(__name__)


async def route_node(state: AgentState) -> AgentState:
    """Route to appropriate role."""

    if state.error:
        state.role = "IDLE"
        return state

    if state.trigger_type == "SCHEDULED":
        state.role = "CREATOR"
    elif state.trigger_type == "EXTERNAL":
        state.role = "QUALIFIER"
    else:  # DM
        # Keyword-based routing
        qualifier_keywords = ["coaching", "formation", "conseil", "prix", "coût"]
        responder_keywords = ["technique", "comment", "pourquoi", "c'est quoi"]

        msg_lower = state.message_text.lower()

        if any(kw in msg_lower for kw in qualifier_keywords):
            state.role = "QUALIFIER"
        else:
            state.role = "RESPONDER"

    logger.info(
        "ROUTE",
        extra={"run_id": state.run_id, "role": state.role},
    )

    return state
```

(Continue avec execute et quality_gate nodes...)

---

## Phase 4: Tools Implementation (Days 6-7)

### 4.1 RAG Search Tool

**File**: `agents/tools/rag_search.py`
```python
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from agents.config.logging import setup_logging
from agents.config.models import RagChunk
from agents.db import Database

logger = setup_logging(__name__)


async def rag_search(
    db: Database,
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.6,
) -> list[RagChunk]:
    """
    Search training content in pgvector.

    Args:
        db: Database instance
        query: Search query
        top_k: Number of results
        similarity_threshold: Min similarity

    Returns:
        List of RAG chunks with metadata
    """

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding = model.encode(query, convert_to_numpy=False)

    chunks = await db.search_vectors(
        embedding=embedding.tolist(),
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )

    logger.info(
        "RAG_SEARCH",
        extra={
            "query": query,
            "chunks_found": len(chunks),
            "avg_similarity": sum(c.similarity for c in chunks) / len(chunks)
            if chunks
            else 0,
        },
    )

    return chunks
```

### 4.2 Response Generation Tool

**File**: `agents/tools/generate_response.py`
```python
from __future__ import annotations

import os

import anthropic

from agents.config.constants import CONTENT_LIMITS
from agents.config.logging import setup_logging
from agents.config.models import RagChunk

logger = setup_logging(__name__)


async def generate_dm_response(
    message: str,
    rag_chunks: list[RagChunk],
    role: str,
) -> str:
    """Generate a DM response using Claude."""

    # Build RAG context
    rag_context = "\n".join(
        [
            f"- {chunk.metadata.get('video_title')}: {chunk.content[:200]}"
            for chunk in rag_chunks[:3]
        ]
    )

    if role == "RESPONDER":
        system_prompt = f"""Tu es un expert en game/séduction qui répond aux questions.

Contexte d'entraînement:
{rag_context}

Règles:
- Réponse MAX {CONTENT_LIMITS['dm_max_words']} mots
- Ton: confiant, direct
- Cite sources si pertinent
- Français naturel
"""

    elif role == "QUALIFIER":
        system_prompt = f"""Tu qualifies les prospects pour coaching.

Contexte:
{rag_context}

Règles:
- Réponds à leur question (30-40 mots)
- Ajoute signal de qualification subtil
- Pas de hard-sell
"""

    else:
        system_prompt = "Tu es un assistant utile."

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=150,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Message: {message}"}
        ],
        temperature=0.7,
    )

    text = response.content[0].text

    # Enforce word limit
    words = text.split()
    if len(words) > CONTENT_LIMITS["dm_max_words"]:
        text = " ".join(words[: CONTENT_LIMITS["dm_max_words"]]) + "..."

    logger.info(
        "RESPONSE_GENERATED",
        extra={
            "role": role,
            "word_count": len(text.split()),
            "usage_tokens": response.usage.output_tokens,
        },
    )

    return text
```

---

## Phase 5: Testing & Validation (Days 8-9)

### 5.1 Unit Test Example

**File**: `tests/test_intake_node.py`
```python
import pytest
from datetime import datetime

from agents.config.models import AgentState
from agents.nodes.intake import intake_node
from agents.db import Database


@pytest.mark.asyncio
async def test_intake_valid_message():
    """Test intake with valid message."""

    db = Database()
    await db.init()

    state = AgentState(
        message_id="msg_123",
        sender_id="user_456",
        message_text="C'est quoi la meilleure ouverture?",
        timestamp=datetime.now(),
    )

    result = await intake_node(state, db)

    assert result.run_id is not None
    assert result.error is None
    assert not result.fallback_triggered

    await db.close()


@pytest.mark.asyncio
async def test_intake_empty_message():
    """Test intake with empty message."""

    db = Database()
    await db.init()

    state = AgentState(
        message_id="msg_123",
        sender_id="user_456",
        message_text="",
        timestamp=datetime.now(),
    )

    result = await intake_node(state, db)

    assert result.error is not None
    assert result.fallback_triggered

    await db.close()
```

### 5.2 Integration Test

**File**: `tests/test_full_flow.py`
```python
import pytest
from datetime import datetime

from agents.config.models import AgentState
from agents.seduction_agent import SeductionAgent


@pytest.mark.asyncio
async def test_full_dm_flow():
    """Test complete DM handling flow."""

    agent = SeductionAgent()
    await agent.init()

    state = AgentState(
        message_id="test_msg_001",
        sender_id="test_user_001",
        message_text="Comment débuter en séduction?",
        timestamp=datetime.now(),
        trigger_type="DM",
    )

    result = await agent.run(state)

    assert result.role in ["RESPONDER", "QUALIFIER"]
    assert result.output_text != ""
    assert len(result.output_text.split()) <= 60  # DM limit

    await agent.close()
```

---

## Phase 6: Deployment & Monitoring (Days 10+)

### 6.1 Docker Setup

**File**: `Dockerfile`
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Install Python deps
RUN pip install -e .

# Run agent
CMD ["python", "-m", "agents.seduction_agent", "--mode", "server", "--port", "8000"]
```

### 6.2 Prometheus Metrics

**File**: `agents/metrics.py`
```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
runs_total = Counter(
    "agent_seduction_runs_total",
    "Total runs",
    ["role", "trigger_type"],
)

quality_gate_pass = Counter(
    "agent_seduction_quality_gate_pass",
    "Quality gate passes",
    ["role"],
)

# Histograms
latency = Histogram(
    "agent_seduction_latency_ms",
    "Latency by node",
    ["node"],
    buckets=[100, 500, 1000, 2000, 5000, 10000],
)

# Gauges
rag_confidence = Gauge(
    "agent_seduction_rag_confidence",
    "Average RAG confidence",
    ["role"],
)
```

---

## Quick Reference: File Checklist

```
[x] agents/config/
    [x] __init__.py
    [x] constants.py
    [x] models.py
    [x] logging.py

[x] agents/nodes/
    [ ] __init__.py
    [ ] intake.py
    [ ] contextualize.py
    [ ] route.py
    [ ] execute.py
    [ ] quality_gate.py

[x] agents/tools/
    [ ] __init__.py
    [ ] rag_search.py
    [ ] generate_response.py
    [ ] generate_instagram.py
    [ ] classify_prospect.py
    [ ] instagram_api.py

[ ] agents/prompts/
    [ ] system.md
    [ ] responder.md
    [ ] creator.md
    [ ] qualifier.md

[ ] agents/seduction_agent.py  (Main graph)
[ ] agents/db.py

[ ] database/schema.sql
[ ] database/migrations/

[ ] tests/
    [ ] test_intake_node.py
    [ ] test_contextualize_node.py
    [ ] test_route_node.py
    [ ] test_execute_node.py
    [ ] test_quality_gate_node.py
    [ ] test_full_flow.py

[ ] Dockerfile
[ ] docker-compose.yml
[ ] .env.example
```

---

## Estimated Timeline

- **Days 1-2**: Core infrastructure (config, logging, models)
- **Days 2-3**: Database setup + migrations
- **Days 4-5**: Nodes implementation (5 nodes)
- **Days 6-7**: Tools + Claude SDK integration
- **Days 8-9**: Testing + bug fixes
- **Days 10+**: Deploy, monitoring, iteration

**Total**: 2 weeks (40-60 hours)

---

**Next Step**: Start with Phase 1 setup. Report back when infrastructure is ready.
