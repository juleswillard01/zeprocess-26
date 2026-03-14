# Knowledge Base RAG Architecture - MEGA QUIXAI
**System Architecture Document for Agent-Optimized Retrieval**

---

## Executive Summary

Cette architecture déploie un RAG hyper-optimisé pour les 3 agents MEGA QUIXAI (Prospection, Qualification, Closing) opérant sur du contenu séduction/game. Le système réutilise le pipeline YouTube RAG existant et ajoute :

1. **Schema PostgreSQL avancé** : leads, conversations, knowledge graphs, feedback loops
2. **Chunking multi-stratégie** : par type de contenu (concept, tactique, objet) et par agent
3. **Embedding multilingue** : modèle 384-dim pour français/anglais + spécialisé séduction
4. **Hybrid search** : semantic + BM25 keyword + graph-based entity matching
5. **Knowledge graph** : relations entre concepts (approche → qualification → closing)
6. **Agent-specific retrieval** : chaque agent reçoit chunks optimisés pour sa phase
7. **Feedback loop** : amélioration continue basée sur succès/échecs de conversion
8. **MCP integration** : exposition du RAG via tools spécialisés par agent

**Coût opérationnel** : 0€/mois (self-hosted) ou €15/mois (Supabase managed)
**Latence retrieval** : <200ms p95 pour hybrid search + reranking
**Scalabilité** : up to 10M chunks (1-2 To de contenu)

---

## Part 1: PostgreSQL Schema Design

### 1.1 Core Tables

```sql
-- Extension pgvector et full-text search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fuzzy matching

-- Videos table (from existing pipeline)
CREATE TABLE videos (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(1000) NOT NULL,
    youtube_url TEXT,
    playlist_id VARCHAR(255),
    playlist_name VARCHAR(500),
    duration_seconds INT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(100),  -- "approche", "qualification", "closing", "mindset", "tools"
    language VARCHAR(10) DEFAULT 'fr',
    chunks_count INT DEFAULT 0,
    INDEX idx_category (category),
    INDEX idx_uploaded_at (uploaded_at)
);

-- Content chunks with metadata
CREATE TABLE video_chunks (
    id BIGSERIAL PRIMARY KEY,
    video_id VARCHAR(255) NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,

    -- Content
    text TEXT NOT NULL,
    start_time_seconds FLOAT NOT NULL,
    end_time_seconds FLOAT NOT NULL,
    duration FLOAT GENERATED ALWAYS AS (end_time_seconds - start_time_seconds) STORED,

    -- Chunking metadata
    chunk_type VARCHAR(50) NOT NULL,  -- "concept", "tactic", "example", "objection", "mindset"
    token_count INT,

    -- Full-text search support
    text_tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', text)) STORED,

    -- Semantic search support (unified embeddings)
    embedding vector(384),

    -- Quality metrics
    confidence FLOAT DEFAULT 1.0,  -- ASR confidence if available
    is_verified BOOLEAN DEFAULT FALSE,  -- manual verification

    UNIQUE(video_id, chunk_index),
    CONSTRAINT chunk_duration_positive CHECK (duration >= 0)
);

-- Embeddings index for fast similarity search
CREATE INDEX idx_video_chunks_embedding ON video_chunks USING ivfflat (
    embedding vector_cosine_ops
) WITH (lists = 100);

-- Full-text search index
CREATE INDEX idx_video_chunks_text_tsv ON video_chunks USING gin(text_tsv);

-- Trigram index for fuzzy matching
CREATE INDEX idx_video_chunks_text_trigm ON video_chunks USING gin(text gin_trgm_ops);

-- Leads table (CRM integration)
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Contact info
    name VARCHAR(500) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    source VARCHAR(100),  -- "instagram_dm", "email", "website", "referral"

    -- Qualification
    qualification_score INT DEFAULT 0,  -- 0-100
    qualification_status VARCHAR(50) DEFAULT 'new',  -- "new", "interested", "qualified", "unqualified", "closed"
    target_pain_points TEXT[],  -- ["confiance", "approche", "qualification"]

    -- Engagement
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_contacted_at TIMESTAMP,
    next_followup_at TIMESTAMP,
    conversion_stage VARCHAR(50),  -- "discovery", "consideration", "decision"

    -- Metadata
    metadata JSONB DEFAULT '{}',  -- custom fields per agent/campaign

    INDEX idx_qualification_status (qualification_status),
    INDEX idx_created_at (created_at),
    INDEX idx_next_followup_at (next_followup_at)
);

-- Conversations with leads
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,

    -- Agent who handled this
    agent_type VARCHAR(50) NOT NULL,  -- "prospection", "qualification", "closing"
    agent_id VARCHAR(255),  -- e.g., "grok_prospection", "claude_qualification"

    -- Message history
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Context (what the agent retrieved)
    context_chunks_used INT[],  -- IDs of chunks used in this conversation
    rag_queries_count INT DEFAULT 0,

    -- Outcome
    conversion_result VARCHAR(50),  -- "qualified", "unqualified", "pending", "error"
    conversion_reason TEXT,  -- why qualified/unqualified
    confidence_score FLOAT DEFAULT 0.0,  -- agent's confidence in decision

    -- Message content (stored as JSONB for flexibility)
    messages JSONB NOT NULL DEFAULT '[]',  -- [{role, content, timestamp, rag_context}]

    INDEX idx_lead_id (lead_id),
    INDEX idx_agent_type (agent_type),
    INDEX idx_created_at (created_at),
    INDEX idx_conversion_result (conversion_result)
);

-- RAG retrieval events (for feedback loop)
CREATE TABLE rag_events (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,

    -- Query & retrieval
    query VARCHAR(2000) NOT NULL,
    retrieved_chunk_ids INT[] NOT NULL,  -- which chunks were returned
    retrieval_method VARCHAR(50) NOT NULL,  -- "semantic", "keyword", "hybrid", "graph"
    retrieval_time_ms INT,

    -- Quality metrics
    query_embedding vector(384),
    top_match_score FLOAT,
    chunk_count INT,

    -- Outcome (was this retrieval helpful?)
    was_useful BOOLEAN,  -- user feedback if available
    lead_conversion BOOLEAN,  -- did this ultimately lead to conversion?

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_conversation_id (conversation_id),
    INDEX idx_lead_conversion (lead_conversion),
    INDEX idx_created_at (created_at)
);
```

### 1.2 Knowledge Graph Tables

```sql
-- Concepts (nodes in knowledge graph)
CREATE TABLE concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(500) NOT NULL UNIQUE,

    -- Classification
    domain VARCHAR(100) NOT NULL,  -- "approche", "qualification", "closing", "mindset"
    parent_id UUID REFERENCES concepts(id),

    -- Description
    description TEXT,
    definition TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_domain (domain),
    INDEX idx_parent_id (parent_id)
);

-- Relations between concepts (directed edges)
CREATE TABLE concept_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    target_concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,

    -- Relation type
    relation_type VARCHAR(100) NOT NULL,  -- "prerequisite", "example_of", "causes", "opposes", "refines"
    strength FLOAT DEFAULT 1.0,  -- 0-1, importance of relation

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source_concept_id, target_concept_id, relation_type),
    INDEX idx_source (source_concept_id),
    INDEX idx_target (target_concept_id)
);

-- Mapping between chunks and concepts (chunk → concept)
CREATE TABLE chunk_concepts (
    id BIGSERIAL PRIMARY KEY,
    chunk_id BIGINT NOT NULL REFERENCES video_chunks(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,

    -- Strength of association
    relevance_score FLOAT DEFAULT 1.0,  -- 0-1
    is_primary BOOLEAN DEFAULT FALSE,  -- is this the main concept?

    UNIQUE(chunk_id, concept_id),
    INDEX idx_chunk_id (chunk_id),
    INDEX idx_concept_id (concept_id)
);

-- Entities extracted from chunks (e.g., "objection: price")
CREATE TABLE entities (
    id BIGSERIAL PRIMARY KEY,
    chunk_id BIGINT NOT NULL REFERENCES video_chunks(id) ON DELETE CASCADE,

    entity_type VARCHAR(50) NOT NULL,  -- "objection", "technique", "phrase", "mindset_shift"
    entity_text VARCHAR(1000) NOT NULL,

    -- Positions in text
    start_pos INT,
    end_pos INT,

    -- Metadata
    confidence FLOAT DEFAULT 1.0,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_chunk_id (chunk_id),
    INDEX idx_entity_type (entity_type)
);
```

### 1.3 Agent-Specific Views

```sql
-- Prospection agent: chunks optimized for initial outreach
CREATE VIEW prospection_chunks AS
SELECT
    vc.id,
    vc.video_id,
    vc.text,
    vc.start_time_seconds,
    vc.chunk_type,
    vc.embedding,
    v.title,
    v.youtube_url,
    CASE
        WHEN vc.chunk_type IN ('mindset', 'approach_intro') THEN 1.3
        WHEN vc.chunk_type = 'example' THEN 1.0
        WHEN vc.chunk_type = 'objection' THEN 0.6
        ELSE 1.0
    END AS relevance_boost
FROM video_chunks vc
JOIN videos v ON vc.video_id = v.id
WHERE v.category IN ('approche', 'mindset');

-- Qualification agent: chunks for deeper discovery
CREATE VIEW qualification_chunks AS
SELECT
    vc.id,
    vc.video_id,
    vc.text,
    vc.start_time_seconds,
    vc.chunk_type,
    vc.embedding,
    v.title,
    v.youtube_url,
    CASE
        WHEN vc.chunk_type IN ('objection', 'qualifier') THEN 1.4
        WHEN vc.chunk_type = 'tactic' THEN 1.2
        WHEN vc.chunk_type = 'mindset' THEN 0.9
        ELSE 1.0
    END AS relevance_boost
FROM video_chunks vc
JOIN videos v ON vc.video_id = v.id
WHERE v.category IN ('qualification', 'objection_handling');

-- Closing agent: chunks for conversion
CREATE VIEW closing_chunks AS
SELECT
    vc.id,
    vc.video_id,
    vc.text,
    vc.start_time_seconds,
    vc.chunk_type,
    vc.embedding,
    v.title,
    v.youtube_url,
    CASE
        WHEN vc.chunk_type IN ('closing_technique', 'urgency', 'commitment') THEN 1.5
        WHEN vc.chunk_type = 'objection' THEN 1.2
        WHEN vc.chunk_type = 'example' THEN 1.0
        ELSE 0.8
    END AS relevance_boost
FROM video_chunks vc
JOIN videos v ON vc.video_id = v.id
WHERE v.category IN ('closing', 'urgency', 'commitment');
```

### 1.4 Feedback Loop View

```sql
-- Track which chunks lead to conversions
CREATE VIEW chunk_conversion_stats AS
SELECT
    vc.id as chunk_id,
    vc.video_id,
    COUNT(DISTINCT re.conversation_id) as retrieval_count,
    COUNT(DISTINCT CASE WHEN re.lead_conversion THEN re.conversation_id END) as conversions,
    ROUND(
        COUNT(DISTINCT CASE WHEN re.lead_conversion THEN re.conversation_id END)::FLOAT /
        NULLIF(COUNT(DISTINCT re.conversation_id), 0) * 100,
        2
    ) as conversion_rate,
    AVG(CASE WHEN re.was_useful THEN 1 ELSE 0 END) * 100 as usefulness_pct
FROM video_chunks vc
LEFT JOIN rag_events re ON re.retrieved_chunk_ids @> ARRAY[vc.id]
WHERE re.created_at > CURRENT_DATE - INTERVAL '90 days'
GROUP BY vc.id, vc.video_id
ORDER BY conversion_rate DESC NULLS LAST;
```

---

## Part 2: Chunking Strategy

### 2.1 Multi-Level Chunking Approach

Le chunking n'est **pas** juste "par 60 secondes". C'est stratégié :

```python
# chunking_strategy.py

from enum import Enum
from dataclasses import dataclass
from typing import Literal

class ChunkType(str, Enum):
    """Chunk classification based on content."""
    # Mindset & philosophy
    MINDSET = "mindset"
    PSYCHOLOGY = "psychology"

    # Techniques & tactics
    TACTIC = "tactic"
    TECHNIQUE = "technique"
    APPROACH_INTRO = "approach_intro"

    # Practical examples
    EXAMPLE = "example"
    ROLEPLAY = "roleplay"
    CASE_STUDY = "case_study"

    # Objection handling
    OBJECTION = "objection"
    OBJECTION_ANSWER = "objection_answer"

    # Conversion
    CLOSING_TECHNIQUE = "closing_technique"
    URGENCY = "urgency"
    COMMITMENT = "commitment"

    # Meta
    INTRO = "intro"
    CONCLUSION = "conclusion"
    TRANSITION = "transition"

@dataclass
class Chunk:
    """Structured chunk with rich metadata."""
    text: str
    start_time: float  # seconds
    end_time: float
    chunk_type: ChunkType
    confidence: float = 1.0  # ASR confidence
    concepts: list[str] = None  # ["approche", "qualification", ...]
    entities: dict = None  # {"objection": ["price"], "technique": ["DCP"]}
    token_count: int = None

class ContentChunker:
    """Multi-strategy chunking optimized for RAG quality."""

    def __init__(self):
        # Strategy 1: Time-based chunking (60-120 sec baseline)
        # Strategy 2: Semantic segmentation (detect content changes)
        # Strategy 3: Entity-based (group by concept/objection)
        self.time_chunk_seconds = 90
        self.min_chunk_seconds = 30
        self.max_chunk_seconds = 180
        self.overlap_seconds = 10

    def chunk_srt(
        self,
        srt_content: str,
        video_duration: float,
        strategy: Literal["time", "semantic", "hybrid"] = "hybrid"
    ) -> list[Chunk]:
        """
        Chunk SRT with multi-strategy approach.

        Strategy comparison:

        | Strategy | Pros | Cons |
        |----------|------|------|
        | time | Fast, deterministic | Breaks concepts mid-stream |
        | semantic | Respects content boundaries | Slow, requires LLM |
        | hybrid | Good balance + concept-aware | Moderate complexity |
        """

        if strategy == "time":
            return self._chunk_by_time(srt_content)
        elif strategy == "semantic":
            return self._chunk_by_semantic_change(srt_content)
        else:  # hybrid
            return self._chunk_hybrid(srt_content)

    def _chunk_by_time(self, srt_content: str) -> list[Chunk]:
        """Simple time-based chunking with overlap."""
        # Parse SRT
        import srt
        subs = list(srt.parse(srt_content))

        chunks = []
        i = 0
        while i < len(subs):
            chunk_start = subs[i].start.total_seconds()
            current_texts = []
            chunk_end = chunk_start

            # Accumulate subtitles until time threshold
            while i < len(subs):
                sub = subs[i]
                current_end = sub.end.total_seconds()

                if current_end - chunk_start >= self.time_chunk_seconds:
                    break

                current_texts.append(sub.content.replace("\n", " ").strip())
                chunk_end = current_end
                i += 1

            if current_texts:
                text = " ".join(current_texts)
                chunks.append(Chunk(
                    text=text,
                    start_time=chunk_start,
                    end_time=chunk_end,
                    chunk_type=self._classify_chunk(text),
                    token_count=len(text.split())
                ))

        return chunks

    def _chunk_by_semantic_change(self, srt_content: str) -> list[Chunk]:
        """Detect semantic boundaries using keyword patterns."""
        import srt

        # Keywords that signal new sections
        section_markers = {
            "approche": ["approche", "technique", "aller à l'abord", "démarrer"],
            "objection": ["objection", "excuse", "problème", "pourquoi"],
            "closing": ["fermeture", "commit", "décision", "oui"],
        }

        subs = list(srt.parse(srt_content))
        chunks = []
        current_chunk = []
        chunk_start = None
        current_section = None

        for sub in subs:
            text = sub.content.lower()

            # Detect section change
            new_section = None
            for section, keywords in section_markers.items():
                if any(kw in text for kw in keywords):
                    new_section = section
                    break

            # Flush chunk if section changed
            if new_section and new_section != current_section and current_chunk:
                chunks.append(self._create_chunk(current_chunk, chunk_start))
                current_chunk = []
                chunk_start = None
                current_section = new_section

            # Add subtitle to current chunk
            if chunk_start is None:
                chunk_start = sub.start.total_seconds()
            current_chunk.append(sub.content.replace("\n", " ").strip())

        # Flush remaining
        if current_chunk:
            chunks.append(self._create_chunk(current_chunk, chunk_start))

        return chunks

    def _chunk_hybrid(self, srt_content: str) -> list[Chunk]:
        """
        Combine time-based + semantic detection.

        Process:
        1. Time-based initial split (90 sec)
        2. If chunk contains semantic boundary, split there
        3. Classify each chunk
        4. Apply overlap for context
        """
        chunks = self._chunk_by_time(srt_content)

        # Post-process: if a chunk is too large and contains markers, split
        refined_chunks = []
        for chunk in chunks:
            if chunk.end_time - chunk.start_time > self.max_chunk_seconds:
                # Try to split at semantic boundary
                sub_chunks = self._split_large_chunk(chunk)
                refined_chunks.extend(sub_chunks)
            else:
                refined_chunks.append(chunk)

        return refined_chunks

    def _classify_chunk(self, text: str) -> ChunkType:
        """Classify chunk type based on content patterns."""
        text_lower = text.lower()

        # Keywords → type mapping
        patterns = {
            ChunkType.MINDSET: ["croire", "confiance", "mentalité", "psychologie"],
            ChunkType.OBJECTION: ["objection", "excuse", "problème", "pourquoi", "comment"],
            ChunkType.TACTIC: ["technique", "stratégie", "tactique", "faire", "dire"],
            ChunkType.EXAMPLE: ["par exemple", "exemple", "cas", "imaginons"],
            ChunkType.CLOSING_TECHNIQUE: ["fermeture", "commit", "décision", "oui"],
        }

        # Score each pattern
        best_match = ChunkType.EXAMPLE
        best_score = 0

        for chunk_type, keywords in patterns.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_match = chunk_type

        return best_match

    def _create_chunk(self, texts: list[str], start_time: float) -> Chunk:
        """Helper to create Chunk object."""
        # Implementation details
        pass
```

### 2.2 Chunk Quality Optimization

```python
class ChunkQualityOptimizer:
    """Ensure chunks are RAG-optimal."""

    @staticmethod
    def validate_chunk(chunk: Chunk) -> bool:
        """Check if chunk meets quality criteria."""
        # Criteria
        min_tokens = 20
        max_tokens = 300
        min_duration = 15  # seconds

        token_count = len(chunk.text.split())
        duration = chunk.end_time - chunk.start_time

        return (
            min_tokens <= token_count <= max_tokens and
            duration >= min_duration and
            chunk.confidence > 0.8  # ASR confidence
        )

    @staticmethod
    def deduplicate_chunks(chunks: list[Chunk]) -> list[Chunk]:
        """Remove near-duplicate chunks."""
        # Use embedding similarity to detect duplicates
        # Keep highest-quality (ASR confidence) version
        pass

    @staticmethod
    def balance_chunk_types(chunks: list[Chunk]) -> list[Chunk]:
        """Rebalance chunk types for diversity."""
        # Ensure we don't have 90% examples and 10% mindset
        # Redistribute timing to capture balanced content
        pass
```

---

## Part 3: Embedding Model Selection

### 3.1 Model Choice Justification

**Sélection : Sentence-Transformers `multilingual-e5-large`**

```python
# Why this model:

MODEL_CONFIG = {
    "name": "intfloat/multilingual-e5-large",
    "dimensions": 1024,
    "languages": ["french", "english"],
    "strengths": [
        "Excellent French support (trained on multilingual data)",
        "Strong semantic understanding for domain-specific terms",
        "Compatible with existing e5-small deployment (can fine-tune)",
        "Public weights, reproducible",
    ],
    "weaknesses": [
        "Larger (560MB), slower inference than MiniLM",
        "Requires more VRAM for batch embedding",
    ],
    "cost_analysis": {
        "one_shot_embedding_1m_chunks": "€50-100 (GPU rental) OR free (self-hosted)",
        "monthly_inference": "negligible (local inference)",
    }
}

# Alternative: if cost/speed critical, use smaller model:
# - intfloat/multilingual-e5-small (384 dim, 10x faster)
# - all-MiniLM-L6-v2 (384 dim, very fast, good French)

# We choose multilingual-e5-large because:
# 1. Seduction/game content is nuanced - need strong semantic understanding
# 2. May include English content (techniques, psychology) - need multilingual
# 3. One-shot cost is negligible vs ongoing value
# 4. Inference is local, not metered
```

### 3.2 Embedding Pipeline

```python
from __future__ import annotations

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Literal
import logging

logger = logging.getLogger(__name__)

class EmbeddingPipeline:
    """Production embedding service for chunks."""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        device: str = "cuda",  # or "cpu"
        batch_size: int = 32,
        normalize: bool = True,
    ):
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        self.normalize = normalize
        self.dimensions = self.model.get_sentence_embedding_dimension()
        logger.info(f"Loaded {model_name}, dims={self.dimensions}")

    def embed_chunks(
        self,
        chunks: list[Chunk],
        with_instructions: bool = False,
    ) -> list[np.ndarray]:
        """
        Embed chunks efficiently.

        Args:
            chunks: List of Chunk objects with .text
            with_instructions: If True, prepend "Represent this text: "
                              (e5 specific, improves performance)

        Returns:
            List of embeddings (normalized or not)
        """
        texts = [c.text for c in chunks]

        if with_instructions:
            texts = [f"Represent this text for retrieval: {t}" for t in texts]

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
        )

        return embeddings

    def embed_query(
        self,
        query: str,
        with_instructions: bool = True,
    ) -> np.ndarray:
        """
        Embed a single query.

        For e5 models, queries should be prefixed with "Represent this
        question for retrieving supporting documents: " for best results.
        """
        if with_instructions:
            query = f"Represent this question for retrieving supporting documents: {query}"

        embedding = self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
        )

        return embedding

    def batch_embed_chunks_from_db(
        self,
        db_conn,
        limit: int = 100000,
        offset: int = 0,
    ) -> int:
        """
        Batch embed chunks from database and update pgvector column.

        Returns:
            Number of chunks embedded
        """
        with db_conn.cursor() as cur:
            # Fetch chunks without embeddings
            cur.execute(
                "SELECT id, text FROM video_chunks WHERE embedding IS NULL "
                f"ORDER BY id LIMIT {limit} OFFSET {offset}"
            )
            rows = cur.fetchall()

        if not rows:
            logger.info("No chunks to embed.")
            return 0

        chunk_ids, texts = zip(*rows)
        logger.info(f"Embedding {len(texts)} chunks...")

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
        )

        # Update database
        with db_conn.cursor() as cur:
            for chunk_id, emb in zip(chunk_ids, embeddings):
                emb_str = f"[{','.join(str(float(x)) for x in emb)}]"
                cur.execute(
                    "UPDATE video_chunks SET embedding = %s::vector WHERE id = %s",
                    (emb_str, chunk_id),
                )

        db_conn.commit()
        logger.info(f"Updated {len(embeddings)} embeddings in DB")
        return len(embeddings)
```

---

## Part 4: Retrieval Pipeline

### 4.1 Hybrid Search Architecture

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import psycopg
import numpy as np
from typing import Literal

@dataclass
class RetrievalResult:
    """Single result from hybrid search."""
    chunk_id: int
    video_id: str
    video_title: str
    youtube_url: str
    text: str
    start_time: float
    end_time: float
    timestamp_str: str  # "14:23"

    # Scores
    semantic_score: float  # 0-1, similarity
    keyword_score: float   # 0-1, BM25-like
    final_score: float     # weighted combination
    retrieval_method: str  # "semantic", "keyword", "hybrid", "graph"

class RetrievalMethod(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    GRAPH = "graph"

class HybridSearchEngine:
    """Production retrieval with 4 search methods."""

    def __init__(
        self,
        db_url: str,
        embedding_model,
        agent_type: Literal["prospection", "qualification", "closing"] = "prospection",
    ):
        self.db_url = db_url
        self.embedding_model = embedding_model
        self.agent_type = agent_type

        # Weights for hybrid score (tuned per agent)
        self.weights = self._get_agent_weights()

    def _get_agent_weights(self) -> dict:
        """Agent-specific weight configuration."""
        weights = {
            "prospection": {
                "semantic": 0.50,
                "keyword": 0.25,
                "graph": 0.25,
            },
            "qualification": {
                "semantic": 0.40,
                "keyword": 0.30,
                "graph": 0.30,
            },
            "closing": {
                "semantic": 0.45,
                "keyword": 0.35,
                "graph": 0.20,
            },
        }
        return weights.get(self.agent_type, weights["prospection"])

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        method: RetrievalMethod = RetrievalMethod.HYBRID,
        threshold: float = 0.3,
    ) -> list[RetrievalResult]:
        """
        Retrieve most relevant chunks for query.

        Args:
            query: Natural language search query
            top_k: Number of results to return
            method: Which retrieval method(s) to use
            threshold: Minimum score to return

        Returns:
            Ranked list of RetrievalResult objects
        """
        if method == RetrievalMethod.SEMANTIC:
            return self._search_semantic(query, top_k, threshold)
        elif method == RetrievalMethod.KEYWORD:
            return self._search_keyword(query, top_k, threshold)
        elif method == RetrievalMethod.GRAPH:
            return self._search_graph(query, top_k, threshold)
        else:  # HYBRID
            return self._search_hybrid(query, top_k, threshold)

    def _search_semantic(
        self,
        query: str,
        top_k: int,
        threshold: float,
    ) -> list[RetrievalResult]:
        """Semantic similarity search via embedding."""
        # Embed query
        query_embedding = self.embedding_model.embed_query(query)
        emb_str = f"[{','.join(str(float(x)) for x in query_embedding)}]"

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # Use pgvector distance operator
                cur.execute(
                    f"""
                    SELECT
                        vc.id,
                        vc.video_id,
                        vc.text,
                        vc.start_time_seconds,
                        vc.end_time_seconds,
                        v.title,
                        v.youtube_url,
                        1 - (vc.embedding <=> %s::vector) as similarity
                    FROM video_chunks vc
                    JOIN videos v ON vc.video_id = v.id
                    WHERE vc.embedding IS NOT NULL
                    ORDER BY vc.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (emb_str, emb_str, top_k * 2),  # over-fetch for filtering
                )
                rows = cur.fetchall()

        results = []
        for row in rows:
            chunk_id, vid, text, start, end, title, url, score = row
            if score >= threshold:
                results.append(RetrievalResult(
                    chunk_id=chunk_id,
                    video_id=vid,
                    video_title=title,
                    youtube_url=url,
                    text=text,
                    start_time=start,
                    end_time=end,
                    timestamp_str=self._format_timestamp(start),
                    semantic_score=score,
                    keyword_score=0.0,
                    final_score=score,
                    retrieval_method="semantic",
                ))

        return results[:top_k]

    def _search_keyword(
        self,
        query: str,
        top_k: int,
        threshold: float,
    ) -> list[RetrievalResult]:
        """Full-text search via PostgreSQL tsvector."""
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # PostgreSQL full-text search
                cur.execute(
                    """
                    SELECT
                        vc.id,
                        vc.video_id,
                        vc.text,
                        vc.start_time_seconds,
                        vc.end_time_seconds,
                        v.title,
                        v.youtube_url,
                        ts_rank(vc.text_tsv, query) as bm25_score
                    FROM video_chunks vc
                    JOIN videos v ON vc.video_id = v.id,
                    plainto_tsquery('french', %s) query
                    WHERE vc.text_tsv @@ query
                    ORDER BY ts_rank(vc.text_tsv, query) DESC
                    LIMIT %s
                    """,
                    (query, top_k * 2),
                )
                rows = cur.fetchall()

        results = []
        for row in rows:
            chunk_id, vid, text, start, end, title, url, score = row
            if score >= threshold:
                results.append(RetrievalResult(
                    chunk_id=chunk_id,
                    video_id=vid,
                    video_title=title,
                    youtube_url=url,
                    text=text,
                    start_time=start,
                    end_time=end,
                    timestamp_str=self._format_timestamp(start),
                    semantic_score=0.0,
                    keyword_score=score,
                    final_score=score,
                    retrieval_method="keyword",
                ))

        return results[:top_k]

    def _search_hybrid(
        self,
        query: str,
        top_k: int,
        threshold: float,
    ) -> list[RetrievalResult]:
        """Combine semantic + keyword search."""
        # Run both in parallel
        semantic_results = self._search_semantic(query, top_k * 2, threshold * 0.8)
        keyword_results = self._search_keyword(query, top_k * 2, threshold * 0.8)

        # Merge and score
        results_by_id = {}

        for r in semantic_results:
            results_by_id[r.chunk_id] = {
                **r.__dict__,
                "semantic_score": r.semantic_score,
                "keyword_score": 0.0,
            }

        for r in keyword_results:
            if r.chunk_id in results_by_id:
                results_by_id[r.chunk_id]["keyword_score"] = r.keyword_score
            else:
                results_by_id[r.chunk_id] = {
                    **r.__dict__,
                    "semantic_score": 0.0,
                    "keyword_score": r.keyword_score,
                }

        # Calculate weighted final score
        weights = self.weights
        final_results = []

        for chunk_id, data in results_by_id.items():
            final_score = (
                data["semantic_score"] * weights["semantic"] +
                data["keyword_score"] * weights["keyword"]
            )

            if final_score >= threshold:
                result = RetrievalResult(
                    chunk_id=data["chunk_id"],
                    video_id=data["video_id"],
                    video_title=data["video_title"],
                    youtube_url=data["youtube_url"],
                    text=data["text"],
                    start_time=data["start_time"],
                    end_time=data["end_time"],
                    timestamp_str=data["timestamp_str"],
                    semantic_score=data["semantic_score"],
                    keyword_score=data["keyword_score"],
                    final_score=final_score,
                    retrieval_method="hybrid",
                )
                final_results.append(result)

        # Sort by final score
        final_results.sort(key=lambda x: x.final_score, reverse=True)
        return final_results[:top_k]

    def _search_graph(
        self,
        query: str,
        top_k: int,
        threshold: float,
    ) -> list[RetrievalResult]:
        """
        Graph-based search: find chunks related to concepts in query.

        Algorithm:
        1. Extract entities from query (NER)
        2. Map to concepts in knowledge graph
        3. Find chunks associated with those concepts
        4. Rank by concept relevance
        """
        # Extract entities from query
        entities = self._extract_entities(query)

        if not entities:
            # Fall back to semantic if no entities found
            return self._search_semantic(query, top_k, threshold)

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # Find concepts matching entities
                placeholders = ",".join(["%s"] * len(entities))
                cur.execute(
                    f"""
                    SELECT DISTINCT
                        vc.id,
                        vc.video_id,
                        vc.text,
                        vc.start_time_seconds,
                        vc.end_time_seconds,
                        v.title,
                        v.youtube_url,
                        cc.relevance_score
                    FROM concepts c
                    JOIN chunk_concepts cc ON c.id = cc.concept_id
                    JOIN video_chunks vc ON cc.chunk_id = vc.id
                    JOIN videos v ON vc.video_id = v.id
                    WHERE c.name = ANY(ARRAY[{placeholders}])
                    ORDER BY cc.relevance_score DESC
                    LIMIT %s
                    """,
                    (*entities, top_k * 2),
                )
                rows = cur.fetchall()

        results = []
        for row in rows:
            chunk_id, vid, text, start, end, title, url, relevance = row
            if relevance >= threshold:
                results.append(RetrievalResult(
                    chunk_id=chunk_id,
                    video_id=vid,
                    video_title=title,
                    youtube_url=url,
                    text=text,
                    start_time=start,
                    end_time=end,
                    timestamp_str=self._format_timestamp(start),
                    semantic_score=0.0,
                    keyword_score=relevance,
                    final_score=relevance,
                    retrieval_method="graph",
                ))

        return results[:top_k]

    def _extract_entities(self, text: str) -> list[str]:
        """Extract concept entities from text."""
        # Simple keyword matching - could use spaCy NER for better results
        concept_keywords = {
            "approche": ["approche", "abordage", "initial", "premier contact"],
            "qualification": ["qualification", "découverte", "problème", "situation"],
            "objection": ["objection", "excuse", "résistance", "pourquoi"],
            "closing": ["fermeture", "commitment", "décision", "accord"],
        }

        found = []
        text_lower = text.lower()

        for concept, keywords in concept_keywords.items():
            if any(kw in text_lower for kw in keywords):
                found.append(concept)

        return found

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert seconds to MM:SS format."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
```

### 4.2 Reranking (Optional but Recommended)

```python
# Optional: use a reranker to improve result quality
# Useful when you have 100s of candidates and need top-5

from sentence_transformers import CrossEncoder

class RerankerService:
    """Post-process retrieval results with cross-encoder reranking."""

    def __init__(self, model_name: str = "cross-encoder/qnli-distilroberta-base"):
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Rerank results by cross-encoder score."""
        if len(results) <= top_k:
            return results

        # Score pairs (query, document)
        pairs = [[query, r.text] for r in results]
        scores = self.model.predict(pairs)

        # Sort and return top-k
        ranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
        return [r for r, _ in ranked[:top_k]]
```

---

## Part 5: Knowledge Graph Design

### 5.1 Concept Hierarchy

```
SEDUCTION/GAME Domain
├── MINDSET (psychological foundations)
│   ├── Confiance en soi
│   ├── Lâcher prise
│   ├── Authenticité
│   └── Amour propre
├── APPROCHE (first interaction)
│   ├── Indirect approach
│   ├── Direct approach
│   ├── Group dynamics
│   └── Opening lines
├── QUALIFICATION (understanding her)
│   ├── Values discovery
│   ├── Pain points identification
│   ├── Interest qualification
│   └── Logistics qualification
├── OBJECTION HANDLING
│   ├── "I have a boyfriend"
│   ├── "I'm not interested"
│   ├── "You're too old/young"
│   └── Technical objections
└── CLOSING (conversion)
    ├── Number close
    ├── Date close
    ├── Kiss close
    └── Commitment techniques
```

### 5.2 Populating the Graph

```python
class KnowledgeGraphBuilder:
    """Populate concept hierarchy and chunk → concept mappings."""

    def __init__(self, db_conn):
        self.conn = db_conn

    def seed_concepts(self):
        """Insert base concept hierarchy."""
        concepts = {
            "mindset": {
                "Confiance en soi": "Foundation of all interactions",
                "Lâcher prise": "Not outcome-dependent",
                "Authenticité": "Being genuine in interaction",
            },
            "approche": {
                "Approach direct": "Direct opening",
                "Approach indirect": "Indirect openers",
                "Gestion de groupe": "Friend group dynamics",
            },
            "qualification": {
                "Découverte des valeurs": "Understanding what she values",
                "Identification des problèmes": "Finding pain points",
                "Qualification logistique": "Feasibility check",
            },
            "objection_handling": {
                "Boyfriend objection": "Response to 'I have a bf'",
                "Not interested": "General disinterest",
                "Age objection": "Too old/young responses",
            },
            "closing": {
                "Number close": "Getting contact info",
                "Date close": "Arranging to meet",
                "Kiss close": "Physical escalation",
            },
        }

        with self.conn.cursor() as cur:
            for domain, concepts_dict in concepts.items():
                for name, description in concepts_dict.items():
                    cur.execute(
                        """
                        INSERT INTO concepts (name, domain, description)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (name) DO NOTHING
                        """,
                        (name, domain, description),
                    )

        self.conn.commit()

    def link_chunks_to_concepts(self):
        """Automatically map chunks to concepts based on semantic similarity."""
        # For each chunk, find closest concepts
        # Use embedding similarity to match
        pass

    def extract_and_link_objections(self):
        """
        Extract "objection: X" patterns from chunks and create entities.

        This creates a searchable index of all objections covered.
        """
        with self.conn.cursor() as cur:
            # Find chunks containing objection patterns
            cur.execute(
                """
                SELECT id, text FROM video_chunks
                WHERE chunk_type = 'objection' OR chunk_type = 'objection_answer'
                """
            )
            rows = cur.fetchall()

        for chunk_id, text in rows:
            # Extract objections like "Si elle dit 'j'ai un mec'"
            import re
            pattern = r"[Ss]i (?:elle|il) (?:dit|te dit)[:\s]+['\"]([^'\"]+)['\"]"
            matches = re.findall(pattern, text)

            for objection_text in matches:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO entities (chunk_id, entity_type, entity_text)
                        VALUES (%s, %s, %s)
                        """,
                        (chunk_id, "objection", objection_text),
                    )

        self.conn.commit()
```

---

## Part 6: Agent-Specific Retrieval

### 6.1 Agent Configuration

```python
from enum import Enum
from dataclasses import dataclass

class AgentType(str, Enum):
    PROSPECTION = "prospection"
    QUALIFICATION = "qualification"
    CLOSING = "closing"

@dataclass
class AgentRetrievalConfig:
    """Per-agent retrieval tuning."""
    agent_type: AgentType

    # Search parameters
    top_k: int  # how many chunks to retrieve
    retrieval_method: RetrievalMethod  # semantic/keyword/hybrid/graph
    threshold: float  # minimum score

    # Re-weighting by chunk type
    chunk_type_weights: dict[str, float]

    # Re-weighting by video category
    category_weights: dict[str, float]

    # Special instructions
    include_examples: bool
    include_objections: bool

# Agent-specific configurations
AGENT_CONFIGS = {
    AgentType.PROSPECTION: AgentRetrievalConfig(
        agent_type=AgentType.PROSPECTION,
        top_k=5,
        retrieval_method=RetrievalMethod.HYBRID,
        threshold=0.35,
        chunk_type_weights={
            "mindset": 1.5,         # Psychology is crucial
            "approach_intro": 1.3,
            "example": 1.0,
            "objection": 0.5,       # Less relevant for opening
            "closing_technique": 0.2,
        },
        category_weights={
            "approche": 1.5,
            "mindset": 1.3,
            "qualification": 0.6,
            "closing": 0.2,
        },
        include_examples=True,
        include_objections=False,
    ),

    AgentType.QUALIFICATION: AgentRetrievalConfig(
        agent_type=AgentType.QUALIFICATION,
        top_k=7,  # More context needed for discovery
        retrieval_method=RetrievalMethod.HYBRID,
        threshold=0.3,
        chunk_type_weights={
            "objection": 1.4,       # Key for qualifying
            "qualifier": 1.3,
            "tactic": 1.2,
            "example": 1.0,
            "mindset": 0.8,
        },
        category_weights={
            "qualification": 1.5,
            "objection_handling": 1.3,
            "approche": 0.7,
            "closing": 0.3,
        },
        include_examples=True,
        include_objections=True,
    ),

    AgentType.CLOSING: AgentRetrievalConfig(
        agent_type=AgentType.CLOSING,
        top_k=5,
        retrieval_method=RetrievalMethod.SEMANTIC,  # High specificity
        threshold=0.4,
        chunk_type_weights={
            "closing_technique": 1.6,
            "urgency": 1.4,
            "commitment": 1.3,
            "objection": 1.2,      # Still important for closing objections
            "example": 0.9,
        },
        category_weights={
            "closing": 1.6,
            "urgency": 1.4,
            "commitment": 1.3,
            "objection_handling": 0.8,
        },
        include_examples=True,
        include_objections=True,
    ),
}

class AgentSpecificRetriever:
    """Apply agent-specific tuning to retrieval."""

    def __init__(
        self,
        base_engine: HybridSearchEngine,
        agent_type: AgentType,
    ):
        self.engine = base_engine
        self.config = AGENT_CONFIGS[agent_type]

    def retrieve_for_agent(
        self,
        query: str,
        context: dict = None,  # lead info, conversation history, etc.
    ) -> list[RetrievalResult]:
        """
        Retrieve + reweight for specific agent.

        Applies:
        1. Agent-specific retrieval method
        2. Chunk type reweighting
        3. Category filtering
        4. Context-aware ranking
        """
        # Base retrieval
        results = self.engine.search(
            query,
            top_k=self.config.top_k * 2,  # over-fetch
            method=self.config.retrieval_method,
            threshold=self.config.threshold * 0.9,
        )

        # Apply agent-specific reweighting
        reweighted = []
        for result in results:
            # Fetch chunk type and video category
            chunk_type = self._get_chunk_type(result.chunk_id)
            category = self._get_video_category(result.video_id)

            # Compute adjusted score
            type_boost = self.config.chunk_type_weights.get(chunk_type, 1.0)
            cat_boost = self.config.category_weights.get(category, 1.0)

            adjusted_score = result.final_score * type_boost * cat_boost

            result.final_score = adjusted_score
            reweighted.append(result)

        # Filter by content type if specified
        if not self.config.include_objections:
            reweighted = [
                r for r in reweighted
                if self._get_chunk_type(r.chunk_id) not in ["objection", "objection_answer"]
            ]

        if not self.config.include_examples:
            reweighted = [
                r for r in reweighted
                if self._get_chunk_type(r.chunk_id) not in ["example", "case_study", "roleplay"]
            ]

        # Re-sort by adjusted score
        reweighted.sort(key=lambda x: x.final_score, reverse=True)

        return reweighted[:self.config.top_k]

    def _get_chunk_type(self, chunk_id: int) -> str:
        """Fetch chunk type from cache or DB."""
        # Implement with caching
        pass

    def _get_video_category(self, video_id: str) -> str:
        """Fetch video category from cache or DB."""
        pass
```

---

## Part 7: Feedback Loop & Learning

### 7.1 Feedback Collection

```python
class FeedbackCollector:
    """Capture outcome signals to improve retrieval."""

    @staticmethod
    def log_retrieval_event(
        conversation_id: str,
        query: str,
        retrieved_chunks: list[int],
        method: str,
        retrieval_time_ms: int,
        db_conn,
    ):
        """Log a retrieval event for later analysis."""
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_events
                (conversation_id, query, retrieved_chunk_ids, retrieval_method, retrieval_time_ms)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (conversation_id, query, retrieved_chunks, method, retrieval_time_ms),
            )
        db_conn.commit()

    @staticmethod
    def record_conversion(
        conversation_id: str,
        lead_id: str,
        converted: bool,
        db_conn,
    ):
        """Record if a conversation led to conversion."""
        # Mark all retrieval events in this conversation as successful/unsuccessful
        with db_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE rag_events
                SET lead_conversion = %s
                WHERE conversation_id = %s
                """,
                (converted, conversation_id),
            )
        db_conn.commit()

class RetrievalOptimizer:
    """Analyze feedback and improve retrieval."""

    @staticmethod
    def compute_chunk_quality_metrics(db_conn, days: int = 90):
        """
        Compute which chunks drive conversions.

        Returns chunks ranked by conversion impact.
        """
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    chunk_id,
                    COUNT(*) as retrievals,
                    COUNT(*) FILTER (WHERE lead_conversion) as conversions,
                    ROUND(
                        COUNT(*) FILTER (WHERE lead_conversion)::FLOAT /
                        NULLIF(COUNT(*), 0) * 100,
                        2
                    ) as conversion_rate
                FROM (
                    SELECT
                        UNNEST(retrieved_chunk_ids) as chunk_id,
                        lead_conversion
                    FROM rag_events
                    WHERE created_at > CURRENT_DATE - INTERVAL '%s days'
                ) t
                GROUP BY chunk_id
                ORDER BY conversion_rate DESC NULLS LAST
                """,
                (days,),
            )
            return cur.fetchall()

    @staticmethod
    def identify_low_quality_chunks(db_conn):
        """Find chunks with poor conversion rate → mark for re-chunking."""
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, conversion_rate
                FROM chunk_conversion_stats
                WHERE retrievals >= 5  -- at least 5 times
                AND conversion_rate < 20  -- <20% conversion
                ORDER BY conversion_rate ASC
                """
            )
            return cur.fetchall()

    @staticmethod
    def optimize_weights_per_agent(db_conn, agent_type: str):
        """
        Analyze which chunk types work best for each agent.

        Output: suggested weights for agent config.
        """
        with db_conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    vc.chunk_type,
                    COUNT(*) as retrievals,
                    COUNT(*) FILTER (WHERE re.lead_conversion) as conversions,
                    ROUND(
                        COUNT(*) FILTER (WHERE re.lead_conversion)::FLOAT /
                        NULLIF(COUNT(*), 0) * 100,
                        2
                    ) as conversion_rate
                FROM rag_events re
                JOIN conversations c ON re.conversation_id = c.id
                LEFT JOIN video_chunks vc ON re.retrieved_chunk_ids && ARRAY[vc.id]
                WHERE c.agent_type = %s
                GROUP BY vc.chunk_type
                ORDER BY conversion_rate DESC NULLS LAST
                """,
                (agent_type,),
            )
            return cur.fetchall()
```

### 7.2 Continuous Improvement Loop

```python
class ContinuousImprovement:
    """Automated improvement pipeline."""

    def __init__(self, db_conn, embedding_model):
        self.conn = db_conn
        self.model = embedding_model

    def weekly_optimization(self):
        """Weekly check: identify improvements."""
        print("\n=== Weekly RAG Optimization ===")

        # 1. Find chunks with poor conversion
        poor_chunks = RetrievalOptimizer.identify_low_quality_chunks(self.conn)
        if poor_chunks:
            print(f"\nFound {len(poor_chunks)} low-conversion chunks:")
            for chunk_id, rate in poor_chunks[:5]:
                print(f"  - Chunk {chunk_id}: {rate}% conversion")
            print("  Action: Re-chunk or verify content quality")

        # 2. Suggest weight updates per agent
        for agent in ["prospection", "qualification", "closing"]:
            print(f"\nOptimizing weights for {agent}:")
            stats = RetrievalOptimizer.optimize_weights_per_agent(self.conn, agent)
            for chunk_type, retrievals, conversions, rate in stats:
                suggested_weight = max(0.5, 1.0 + (rate - 30) / 100)  # target 30% baseline
                print(f"  - {chunk_type}: {rate}% conv → weight={suggested_weight:.2f}")

    def monthly_reembedding(self):
        """Monthly: re-embed all chunks with latest model."""
        print("\n=== Monthly Re-embedding ===")
        # Could implement model upgrades here
        pass
```

---

## Part 8: MCP Integration

### 8.1 Enhanced MCP Server

```python
# mcp_server.py (updated)

from __future__ import annotations

import logging
from dataclasses import asdict

import psycopg
from mcp.server.fastmcp import FastMCP

from search_videos import HybridSearchEngine, AgentType
from embedding_pipeline import EmbeddingPipeline
from feedback_loop import FeedbackCollector

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DB_URL = "postgresql://postgres:dev@localhost:5432/rag_videos"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"

mcp = FastMCP("video-rag-advanced")

# Global services
_embedding_model: EmbeddingPipeline | None = None
_search_engines: dict[AgentType, HybridSearchEngine] = {}


def get_embedding_model() -> EmbeddingPipeline:
    """Lazy-load embedding model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model...")
        _embedding_model = EmbeddingPipeline(EMBEDDING_MODEL)
    return _embedding_model


def get_search_engine(agent_type: str) -> HybridSearchEngine:
    """Get agent-specific search engine."""
    try:
        agent = AgentType(agent_type)
    except ValueError:
        agent = AgentType.PROSPECTION
        logger.warning(f"Unknown agent type, defaulting to prospection")

    if agent not in _search_engines:
        _search_engines[agent] = HybridSearchEngine(DB_URL, get_embedding_model(), agent)

    return _search_engines[agent]


@mcp.tool()
def search_content(
    query: str,
    agent_type: str = "prospection",
    top_k: int = 5,
    method: str = "hybrid",
) -> str:
    """
    Search training content with agent-specific optimization.

    Parameters
    ----------
    query : str
        Natural language search query in French or English.
    agent_type : str
        Agent type: "prospection", "qualification", or "closing".
        Optimizes results for that phase.
    top_k : int
        Number of results to return (default 5).
    method : str
        Retrieval method: "semantic", "keyword", "hybrid", or "graph".

    Returns
    -------
    str
        Formatted search results with video title, timestamp, text, and score.
    """
    engine = get_search_engine(agent_type)

    try:
        from retrieval_pipeline import RetrievalMethod
        method_enum = RetrievalMethod(method)
    except ValueError:
        method_enum = RetrievalMethod.HYBRID
        logger.warning(f"Unknown method, defaulting to hybrid")

    results = engine.search(query, top_k=top_k, method=method_enum)

    if not results:
        return f"No results found for query: '{query}'"

    lines = [f"Found {len(results)} results ({method} search):"]
    for i, r in enumerate(results, 1):
        lines.append("")
        lines.append(f"--- Result {i} (score: {r.final_score:.3f}) ---")
        lines.append(f"Video: {r.video_title}")
        lines.append(f"Time: {r.timestamp_str}")
        if r.youtube_url:
            lines.append(f"URL: {r.youtube_url}?t={int(r.start_time)}")
        lines.append(f"Text: {r.text[:300]}...")

    return "\n".join(lines)


@mcp.tool()
def search_objections(
    objection_text: str,
    top_k: int = 3,
) -> str:
    """
    Search for content about specific objections.

    Useful for the qualification and closing agents to handle objections.

    Parameters
    ----------
    objection_text : str
        The objection phrase (e.g., "I have a boyfriend").
    top_k : int
        Number of techniques to return.

    Returns
    -------
    str
        Ranked list of chunks addressing this objection.
    """
    engine = get_search_engine("qualification")
    results = engine.search(
        f"Comment répondre à: {objection_text}",
        top_k=top_k,
        method=RetrievalMethod.KEYWORD,  # Keyword better for exact phrases
    )

    if not results:
        return f"No techniques found for objection: {objection_text}"

    lines = [f"Techniques for handling: '{objection_text}'"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n--- Technique {i} ---")
        lines.append(f"Source: {r.video_title} @ {r.timestamp_str}")
        lines.append(f"Content: {r.text}")

    return "\n".join(lines)


@mcp.tool()
def search_by_concept(
    concept: str,
    agent_type: str = "prospection",
    top_k: int = 5,
) -> str:
    """
    Search by concept in knowledge graph.

    Retrieves all chunks associated with a specific concept
    (e.g., "Confiance en soi", "Qualification").

    Parameters
    ----------
    concept : str
        Concept name from knowledge graph.
    agent_type : str
        Filter by agent type.
    top_k : int
        Number of results.

    Returns
    -------
    str
        Chunks related to the concept.
    """
    engine = get_search_engine(agent_type)
    results = engine.search(concept, top_k=top_k, method=RetrievalMethod.GRAPH)

    if not results:
        return f"No content found for concept: {concept}"

    lines = [f"Content for concept: {concept}"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n--- {i}. {r.video_title} @ {r.timestamp_str} ---")
        lines.append(r.text[:250] + "...")

    return "\n".join(lines)


@mcp.tool()
def get_full_context(
    video_title: str,
    start_time: float = None,
    context_seconds: int = 300,
) -> str:
    """
    Get extended context around a specific timestamp.

    Parameters
    ----------
    video_title : str
        Video to retrieve context from.
    start_time : float
        Time in seconds (optional, gets full video if not specified).
    context_seconds : int
        How many seconds of context to include.

    Returns
    -------
    str
        Transcript with timestamps.
    """
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            if start_time is None:
                # Get entire video
                cur.execute(
                    """
                    SELECT e.text, e.start_time_seconds, e.end_time_seconds
                    FROM video_chunks e
                    JOIN videos v ON e.video_id = v.id
                    WHERE v.title ILIKE %s
                    ORDER BY e.start_time_seconds
                    """,
                    (f"%{video_title}%",),
                )
            else:
                # Get context window
                window_start = max(0, start_time - context_seconds / 2)
                window_end = start_time + context_seconds / 2

                cur.execute(
                    """
                    SELECT e.text, e.start_time_seconds, e.end_time_seconds
                    FROM video_chunks e
                    JOIN videos v ON e.video_id = v.id
                    WHERE v.title ILIKE %s
                    AND e.start_time_seconds BETWEEN %s AND %s
                    ORDER BY e.start_time_seconds
                    """,
                    (f"%{video_title}%", window_start, window_end),
                )

            rows = cur.fetchall()

    if not rows:
        return f"No content found for video: {video_title}"

    lines = [f"Context for: {video_title}"]
    for text, start, end in rows:
        mins = int(start // 60)
        secs = int(start % 60)
        lines.append(f"[{mins}:{secs:02d}] {text}")

    return "\n".join(lines)


@mcp.tool()
def log_retrieval_for_feedback(
    conversation_id: str,
    query: str,
    retrieved_chunk_ids: list[int],
    retrieval_method: str = "hybrid",
    retrieval_time_ms: int = 0,
) -> str:
    """
    Log a retrieval event for the feedback loop.

    Called by agents after using search results, to track what was useful.
    """
    try:
        with psycopg.connect(DB_URL) as conn:
            FeedbackCollector.log_retrieval_event(
                conversation_id,
                query,
                retrieved_chunk_ids,
                retrieval_method,
                retrieval_time_ms,
                conn,
            )
        return f"Logged retrieval event for conversation {conversation_id}"
    except Exception as e:
        logger.error(f"Error logging retrieval: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
def record_conversion(
    conversation_id: str,
    lead_id: str,
    converted: bool,
    reason: str = "",
) -> str:
    """
    Record the outcome of a conversation (success or failure).

    Used by agents to report conversion outcomes for the feedback loop.
    """
    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE conversations
                    SET conversion_result = %s, conversion_reason = %s
                    WHERE id = %s
                    """,
                    ("qualified" if converted else "unqualified", reason, conversation_id),
                )
                FeedbackCollector.record_conversion(
                    conversation_id,
                    lead_id,
                    converted,
                    conn,
                )
        return f"Recorded conversion for conversation {conversation_id}: {converted}"
    except Exception as e:
        logger.error(f"Error recording conversion: {e}")
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
```

---

## Part 9: Implementation Checklist

### Phase 1: Database Setup (Week 1)
- [ ] Create PostgreSQL schema with all tables
- [ ] Add pgvector and full-text search indexes
- [ ] Create agent-specific views
- [ ] Populate concept hierarchy
- [ ] Test connectivity

### Phase 2: Chunking & Embedding (Week 1-2)
- [ ] Implement multi-strategy chunking
- [ ] Download and test embedding model
- [ ] Embed existing YouTube SRT files (7 videos → ~5K chunks)
- [ ] Validate embedding quality (spot-check semantics)
- [ ] Store embeddings in pgvector

### Phase 3: Retrieval Pipeline (Week 2)
- [ ] Implement semantic search
- [ ] Implement keyword (BM25) search
- [ ] Implement hybrid search
- [ ] Implement graph-based search
- [ ] Add reranking (optional)
- [ ] Test all 4 methods with sample queries

### Phase 4: Agent-Specific Tuning (Week 3)
- [ ] Define agent-specific configs
- [ ] Implement agent-aware retriever
- [ ] Test each agent on sample queries
- [ ] Tune weights based on initial feedback

### Phase 5: MCP Integration (Week 3)
- [ ] Update MCP server with new tools
- [ ] Add feedback logging
- [ ] Add conversion tracking
- [ ] Test with agents

### Phase 6: Feedback Loop (Week 4)
- [ ] Implement feedback collection
- [ ] Create analytics views
- [ ] Set up weekly optimization
- [ ] Deploy continuous improvement

### Phase 7: Monitoring & Ops (Ongoing)
- [ ] Set up logging/monitoring
- [ ] Create operational dashboards
- [ ] Document runbooks
- [ ] Plan for scaling

---

## Part 10: Deployment & Scaling

### Single-Machine Deployment (0€/month)

```bash
# 1. PostgreSQL + pgvector
docker run -d \
  --name postgres-rag \
  -e POSTGRES_PASSWORD=dev \
  -v ./data:/var/lib/postgresql/data \
  pgvector/pgvector:latest

# 2. MCP server
python scripts/mcp_server.py

# 3. Agents query via MCP tools
# (Grok, Claude, etc. use the search_content tool)
```

### Cloud Deployment (€15-30/month)

```bash
# Supabase (managed pgvector)
# - Free tier: 500MB, good for 100K-500K chunks
# - €25/month: 8GB, 10M+ chunks

# Store embeddings in S3/GCS (if needed)
# - 1M chunks × 1KB = 1GB storage
# - ~€0.02/month at $0.023/GB (AWS S3)

# Total cost: €15-30/month
```

### Scaling Beyond 10M Chunks

If expanding beyond current 7 To:

1. **Sharding by domain** : Separate DBs for seduction/game, other courses
2. **Vector quantization** : Compress embeddings (384 → 128 dims, 5x smaller)
3. **Approximate NN search** : Switch from IVFFlat to HNSW
4. **Read replicas** : Distribute search queries

---

## Part 11: Quality Metrics & SLAs

### Retrieval Quality

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Latency p95** | <200ms | Track in RAG events table |
| **Precision@5** | >70% | Manual relevance scoring on sample queries |
| **Recall@10** | >80% | Verify top-10 includes known-relevant chunks |
| **Chunk diversity** | >60% from different videos | Track source spread in results |

### Business Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| **Qualified leads** | TBD | +25% with RAG |
| **Closing rate** | TBD | +15% with RAG |
| **Agent satisfaction** | N/A | >4/5 (RAG usefulness) |
| **Retrieval usefulness** | N/A | >70% of retrievals used |

---

## Summary

This architecture enables:

1. **Multi-dimensional retrieval** (semantic + keyword + graph)
2. **Agent-specific optimization** (each agent gets tailored results)
3. **Continuous learning** (feedback loop improves over time)
4. **Enterprise scalability** (up to 10M+ chunks)
5. **Zero operational cost** (self-hosted) or €15-30/month (managed)

The schema is designed for both performance (IVF indexes, full-text search) and learning (feedback tables, conversion tracking).

---

**Document Version**: 1.0
**Created**: 2026-03-14
**Author**: BMAD Knowledge Base Architect
**Next Steps**: Start Phase 1 (database setup) and Phase 2 (chunking) in parallel
