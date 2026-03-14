# RAG Implementation Guide - Week by Week

**For Full-Stack Engineers & Python Developers**
**Read Time: 30-40 minutes**

---

## Week 1: Foundation - Database & Chunking

### Overview
Establish the database infrastructure and implement the chunking service to process 7TB of YouTube training content into semantic chunks ready for embedding.

### Day 1-2: PostgreSQL + pgvector Setup

#### Install PostgreSQL and pgvector Extension

```bash
# On Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib postgresql-15-pgvector

# Verify installation
psql --version
psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS pgvector;"
```

#### Create Database and Schema

```sql
-- Connect as postgres user
CREATE DATABASE rag_videos;
\c rag_videos

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For trigram search

-- Videos table (metadata)
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    youtube_url VARCHAR(255) NOT NULL UNIQUE,
    playlist_id VARCHAR(255),
    category VARCHAR(100),
    language VARCHAR(10) DEFAULT 'fr',
    duration_seconds INT,
    chunks_count INT DEFAULT 0,
    embedding_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Video chunks (indexed content with embeddings)
CREATE TABLE video_chunks (
    id SERIAL PRIMARY KEY,
    video_id INT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    start_time_seconds INT NOT NULL,
    duration_seconds INT,
    chunk_type VARCHAR(50) NOT NULL,  -- MINDSET, TACTIC, EXAMPLE, etc.
    embedding vector(384),
    confidence FLOAT DEFAULT 1.0,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, chunk_index)
);

-- Leads (CRM data for tracking)
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(20),
    qualification_score INT DEFAULT 0,
    qualification_status VARCHAR(50) DEFAULT 'new',
    conversion_stage VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversations (agent interactions)
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    lead_id INT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,  -- prospection, qualification, closing
    context_chunks_used INT DEFAULT 0,
    conversion_result BOOLEAN,
    outcome VARCHAR(500),
    messages JSONB DEFAULT '[]',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RAG events (feedback loop)
CREATE TABLE rag_events (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    chunk_id INT NOT NULL REFERENCES video_chunks(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    retrieval_method VARCHAR(50),  -- semantic, keyword, hybrid, graph
    retrieval_time_ms INT,
    was_useful BOOLEAN,
    lead_conversion BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Concepts (knowledge graph)
CREATE TABLE concepts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    domain VARCHAR(100),  -- psychology, strategy, execution
    parent_id INT REFERENCES concepts(id),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, domain)
);

-- Concept relations
CREATE TABLE concept_relations (
    id SERIAL PRIMARY KEY,
    source_concept_id INT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    target_concept_id INT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    relation_type VARCHAR(100),  -- causes, leads_to, similar_to, etc.
    strength FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunk-Concept mapping
CREATE TABLE chunk_concepts (
    id SERIAL PRIMARY KEY,
    chunk_id INT NOT NULL REFERENCES video_chunks(id) ON DELETE CASCADE,
    concept_id INT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chunk_id, concept_id)
);

-- Entities (for knowledge extraction)
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    chunk_id INT NOT NULL REFERENCES video_chunks(id) ON DELETE CASCADE,
    entity_type VARCHAR(50),  -- OBJECTION, TECHNIQUE, PERSON, etc.
    entity_text TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_video_chunks_video_id ON video_chunks(video_id);
CREATE INDEX idx_video_chunks_embedding ON video_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_video_chunks_chunk_type ON video_chunks(chunk_type);
CREATE INDEX idx_video_chunks_text_trgm ON video_chunks USING gin(text gin_trgm_ops);
CREATE INDEX idx_conversations_lead_id ON conversations(lead_id);
CREATE INDEX idx_conversations_agent_type ON conversations(agent_type);
CREATE INDEX idx_rag_events_conversation_id ON rag_events(conversation_id);
CREATE INDEX idx_rag_events_chunk_id ON rag_events(chunk_id);
CREATE INDEX idx_chunk_concepts_chunk_id ON chunk_concepts(chunk_id);
CREATE INDEX idx_chunk_concepts_concept_id ON chunk_concepts(concept_id);

-- Views for agent-specific retrieval
CREATE VIEW prospection_chunks AS
SELECT vc.id, vc.text, vc.start_time_seconds, vc.chunk_type, vc.embedding,
       CASE
           WHEN vc.chunk_type = 'MINDSET' THEN 1.5
           WHEN vc.chunk_type = 'APPROACH_INTRO' THEN 1.3
           WHEN vc.chunk_type = 'EXAMPLE' THEN 1.0
           ELSE 0.8
       END as agent_relevance
FROM video_chunks vc
WHERE vc.is_verified = TRUE;

CREATE VIEW qualification_chunks AS
SELECT vc.id, vc.text, vc.start_time_seconds, vc.chunk_type, vc.embedding,
       CASE
           WHEN vc.chunk_type = 'OBJECTION' THEN 1.4
           WHEN vc.chunk_type = 'QUALIFIER' THEN 1.3
           WHEN vc.chunk_type = 'TACTIC' THEN 1.1
           ELSE 0.8
       END as agent_relevance
FROM video_chunks vc
WHERE vc.is_verified = TRUE;

CREATE VIEW closing_chunks AS
SELECT vc.id, vc.text, vc.start_time_seconds, vc.chunk_type, vc.embedding,
       CASE
           WHEN vc.chunk_type = 'CLOSING_TECHNIQUE' THEN 1.6
           WHEN vc.chunk_type = 'URGENCY' THEN 1.4
           WHEN vc.chunk_type = 'TACTIC' THEN 1.2
           ELSE 0.8
       END as agent_relevance
FROM video_chunks vc
WHERE vc.is_verified = TRUE;

CREATE VIEW chunk_conversion_stats AS
SELECT
    vc.id,
    vc.chunk_type,
    COUNT(DISTINCT re.conversation_id) as total_uses,
    COUNT(CASE WHEN re.was_useful THEN 1 END) as useful_count,
    COUNT(CASE WHEN re.lead_conversion THEN 1 END) as conversion_count,
    ROUND(100.0 * COUNT(CASE WHEN re.was_useful THEN 1 END) /
          NULLIF(COUNT(*), 0), 2) as usefulness_rate
FROM video_chunks vc
LEFT JOIN rag_events re ON vc.id = re.chunk_id
GROUP BY vc.id, vc.chunk_type;
```

#### Verify Setup

```bash
# Connect to database
psql -d rag_videos

# Check tables created
\dt

# Check indexes
\di

# Test vector extension
SELECT pgvector_version();
```

### Day 3-4: Chunking Service Implementation

Create `scripts/chunking_service.py`:

```python
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import srt

logger = logging.getLogger(__name__)

class ChunkType(str, Enum):
    """Types of content chunks."""
    MINDSET = "MINDSET"
    APPROACH_INTRO = "APPROACH_INTRO"
    TACTIC = "TACTIC"
    EXAMPLE = "EXAMPLE"
    OBJECTION = "OBJECTION"
    OBJECTION_RESPONSE = "OBJECTION_RESPONSE"
    QUALIFIER = "QUALIFIER"
    CLOSING_TECHNIQUE = "CLOSING_TECHNIQUE"
    URGENCY = "URGENCY"
    COMMITMENT = "COMMITMENT"
    STORY = "STORY"
    FRAMEWORK = "FRAMEWORK"

@dataclass
class Chunk:
    """Represents a single chunk of content."""
    text: str
    start_time_seconds: int
    duration_seconds: int
    chunk_type: ChunkType
    chunk_index: int
    confidence: float = 1.0

class ChunkingService:
    """Chunks SRT content using multi-strategy approach."""

    def __init__(self, base_chunk_duration: int = 90):
        """
        Initialize chunking service.

        Args:
            base_chunk_duration: Target duration in seconds (default 90s)
        """
        self.base_chunk_duration = base_chunk_duration
        self.objection_keywords = [
            "mais", "cependant", "mais pourquoi", "ça ne marche pas",
            "j'ai un copain", "j'ai un petit ami", "t'es pas sérieux"
        ]
        self.closing_keywords = [
            "engagement", "commit", "action", "commencer", "dès maintenant"
        ]

    def chunk_srt(self, srt_path: Path, strategy: str = "hybrid") -> list[Chunk]:
        """
        Chunk SRT file into semantic units.

        Args:
            srt_path: Path to SRT file
            strategy: 'time', 'semantic', or 'hybrid'

        Returns:
            List of Chunk objects
        """
        with open(srt_path, encoding='utf-8') as f:
            subtitles = list(srt.parse(f))

        if not subtitles:
            return []

        if strategy == "time":
            return self._chunk_by_time(subtitles)
        elif strategy == "semantic":
            return self._chunk_by_semantic_change(subtitles)
        else:  # hybrid
            return self._chunk_hybrid(subtitles)

    def _chunk_by_time(self, subtitles: list) -> list[Chunk]:
        """Chunk based on fixed time intervals."""
        chunks = []
        current_text = []
        current_start = None
        chunk_index = 0

        for sub in subtitles:
            if current_start is None:
                current_start = int(sub.start.total_seconds())

            current_text.append(sub.content)
            current_end = int(sub.end.total_seconds())
            duration = current_end - current_start

            if duration >= self.base_chunk_duration:
                text = " ".join(current_text)
                chunk_type = self._classify_chunk(text)
                chunks.append(Chunk(
                    text=text,
                    start_time_seconds=current_start,
                    duration_seconds=duration,
                    chunk_type=chunk_type,
                    chunk_index=chunk_index
                ))
                current_text = []
                current_start = None
                chunk_index += 1

        # Add remaining text
        if current_text:
            text = " ".join(current_text)
            chunk_type = self._classify_chunk(text)
            chunks.append(Chunk(
                text=text,
                start_time_seconds=current_start,
                duration_seconds=int(subtitles[-1].end.total_seconds()) - current_start,
                chunk_type=chunk_type,
                chunk_index=chunk_index
            ))

        return chunks

    def _chunk_by_semantic_change(self, subtitles: list) -> list[Chunk]:
        """Chunk based on topic/semantic changes."""
        chunks = []
        current_text = []
        current_start = None
        chunk_index = 0

        for i, sub in enumerate(subtitles):
            if current_start is None:
                current_start = int(sub.start.total_seconds())

            current_text.append(sub.content)

            # Check for semantic change (topic shift)
            is_topic_change = (
                i > 0 and
                any(kw in sub.content.lower() for kw in self.objection_keywords) and
                not any(kw in subtitles[i-1].content.lower() for kw in self.objection_keywords)
            )

            current_end = int(sub.end.total_seconds())
            duration = current_end - current_start

            if is_topic_change or duration >= self.base_chunk_duration * 1.5:
                text = " ".join(current_text)
                chunk_type = self._classify_chunk(text)
                chunks.append(Chunk(
                    text=text,
                    start_time_seconds=current_start,
                    duration_seconds=duration,
                    chunk_type=chunk_type,
                    chunk_index=chunk_index
                ))
                current_text = []
                current_start = None
                chunk_index += 1

        if current_text:
            text = " ".join(current_text)
            chunk_type = self._classify_chunk(text)
            chunks.append(Chunk(
                text=text,
                start_time_seconds=current_start,
                duration_seconds=int(subtitles[-1].end.total_seconds()) - current_start,
                chunk_type=chunk_type,
                chunk_index=chunk_index
            ))

        return chunks

    def _chunk_hybrid(self, subtitles: list) -> list[Chunk]:
        """Hybrid approach: combine time-based and semantic boundaries."""
        # Start with semantic chunking
        chunks = self._chunk_by_semantic_change(subtitles)

        # Merge chunks that are too small
        merged = []
        for chunk in chunks:
            if merged and chunk.duration_seconds < self.base_chunk_duration * 0.3:
                # Merge with previous chunk
                last = merged.pop()
                merged.append(Chunk(
                    text=f"{last.text} {chunk.text}",
                    start_time_seconds=last.start_time_seconds,
                    duration_seconds=chunk.start_time_seconds + chunk.duration_seconds - last.start_time_seconds,
                    chunk_type=last.chunk_type,  # Keep original type
                    chunk_index=last.chunk_index
                ))
            else:
                merged.append(chunk)

        return merged

    def _classify_chunk(self, text: str) -> ChunkType:
        """Classify chunk type based on content."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in self.objection_keywords):
            if "répondre" in text_lower or "comment" in text_lower:
                return ChunkType.OBJECTION_RESPONSE
            return ChunkType.OBJECTION

        if any(kw in text_lower for kw in self.closing_keywords):
            if "engagement" in text_lower or "commit" in text_lower:
                return ChunkType.COMMITMENT
            if "urgence" in text_lower or "maintenant" in text_lower:
                return ChunkType.URGENCY
            return ChunkType.CLOSING_TECHNIQUE

        if "par exemple" in text_lower or "histoire" in text_lower:
            return ChunkType.EXAMPLE

        if "mindset" in text_lower or "mentalité" in text_lower or "croyance" in text_lower:
            return ChunkType.MINDSET

        if "approche" in text_lower or "technique" in text_lower or "tactic" in text_lower:
            return ChunkType.TACTIC

        return ChunkType.FRAMEWORK  # Default

def batch_chunk_srt_files(srt_directory: Path) -> dict:
    """Process all SRT files in directory."""
    service = ChunkingService()
    results = {
        "total_files": 0,
        "total_chunks": 0,
        "chunks_by_type": {},
        "errors": []
    }

    for srt_file in srt_directory.glob("*.srt"):
        try:
            chunks = service.chunk_srt(srt_file, strategy="hybrid")
            results["total_files"] += 1
            results["total_chunks"] += len(chunks)

            for chunk in chunks:
                chunk_type = chunk.chunk_type.value
                results["chunks_by_type"][chunk_type] = (
                    results["chunks_by_type"].get(chunk_type, 0) + 1
                )

            logger.info(f"Chunked {srt_file.name}: {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Error chunking {srt_file.name}: {e}")
            results["errors"].append({"file": srt_file.name, "error": str(e)})

    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    srt_dir = Path("/path/to/srt/files")
    stats = batch_chunk_srt_files(srt_dir)
    print(json.dumps(stats, indent=2))
```

### Day 5: Validation & Testing

```bash
# Test chunking service
python scripts/chunking_service.py

# Expected output:
# {
#   "total_files": 150,
#   "total_chunks": 45000,
#   "chunks_by_type": {
#     "TACTIC": 15000,
#     "EXAMPLE": 10000,
#     "OBJECTION": 8000,
#     ...
#   }
# }
```

---

## Week 2: Intelligence - Embedding & Search

### Day 1-2: Embedding Pipeline

Create `scripts/embedding_service.py`:

```python
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import psycopg
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingPipeline:
    """Generates embeddings for chunks."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu"
    ):
        """
        Initialize embedding pipeline.

        Args:
            model_name: HuggingFace model identifier
            device: 'cpu' or 'cuda'
        """
        self.model_name = model_name
        self.device = device
        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(
            f"Loaded embedding model {model_name} "
            f"(dim={self.embedding_dim}, device={device})"
        )

    def embed_text(self, text: str) -> np.ndarray:
        """Embed single text."""
        return self.model.encode(text, convert_to_numpy=True)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed batch of texts efficiently."""
        return self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True
        )

    def embed_chunks_from_db(
        self,
        db_conn: psycopg.Connection,
        limit: int = 10000
    ) -> int:
        """Embed chunks from database."""
        cursor = db_conn.cursor()

        # Get chunks without embeddings
        cursor.execute(
            "SELECT id, text FROM video_chunks WHERE embedding IS NULL LIMIT %s",
            (limit,)
        )
        rows = cursor.fetchall()

        if not rows:
            logger.info("No chunks to embed")
            return 0

        chunk_ids = [row[0] for row in rows]
        texts = [row[1] for row in rows]

        # Generate embeddings
        embeddings = self.embed_texts(texts)

        # Store in database
        for chunk_id, embedding in zip(chunk_ids, embeddings):
            embedding_list = embedding.tolist()
            cursor.execute(
                "UPDATE video_chunks SET embedding = %s WHERE id = %s",
                (embedding_list, chunk_id)
            )

        db_conn.commit()
        logger.info(f"Embedded {len(chunk_ids)} chunks")

        return len(chunk_ids)

def initialize_embeddings(
    db_url: str,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 10000
) -> dict:
    """Embed all chunks in database."""
    pipeline = EmbeddingPipeline(model_name=model_name)

    with psycopg.connect(db_url) as conn:
        total_embedded = 0
        while True:
            embedded = pipeline.embed_chunks_from_db(conn, limit=batch_size)
            if embedded == 0:
                break
            total_embedded += embedded

    return {"total_embedded": total_embedded}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = initialize_embeddings(
        db_url="postgresql://user:password@localhost/rag_videos"
    )
    print(f"Embedding complete: {result}")
```

### Day 3-4: Hybrid Search Implementation

Create `scripts/search_service.py`:

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import psycopg
from pgvector.psycopg import register_vector

logger = logging.getLogger(__name__)

class RetrievalMethod(str, Enum):
    """Search methods available."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    GRAPH = "graph"

@dataclass
class RetrievalResult:
    """Single search result."""
    chunk_id: int
    text: str
    start_time_seconds: int
    chunk_type: str
    relevance_score: float
    retrieval_method: str
    video_title: Optional[str] = None

class HybridSearchEngine:
    """Hybrid search combining semantic and keyword methods."""

    def __init__(self, db_url: str):
        """Initialize search engine."""
        self.db_url = db_url

    def search(
        self,
        query: str,
        agent_type: str = "prospection",
        top_k: int = 5,
        method: RetrievalMethod = RetrievalMethod.HYBRID,
        threshold: float = 0.3
    ) -> list[RetrievalResult]:
        """
        Search for relevant chunks.

        Args:
            query: Search query
            agent_type: Which agent is searching
            top_k: Number of results
            method: Search method
            threshold: Minimum relevance score

        Returns:
            List of RetrievalResult objects
        """
        with psycopg.connect(self.db_url) as conn:
            register_vector(conn)

            if method == RetrievalMethod.SEMANTIC:
                return self._search_semantic(conn, query, top_k, threshold)
            elif method == RetrievalMethod.KEYWORD:
                return self._search_keyword(conn, query, top_k, threshold)
            elif method == RetrievalMethod.HYBRID:
                return self._search_hybrid(conn, query, agent_type, top_k, threshold)
            else:
                return self._search_graph(conn, query, top_k, threshold)

    def _search_semantic(
        self,
        conn,
        query: str,
        top_k: int,
        threshold: float
    ) -> list[RetrievalResult]:
        """Search using semantic similarity."""
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode(query).tolist()

        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id, text, start_time_seconds, chunk_type,
                1 - (embedding <=> %s::vector) as similarity
            FROM video_chunks
            WHERE embedding IS NOT NULL
            AND (1 - (embedding <=> %s::vector)) > %s
            ORDER BY similarity DESC
            LIMIT %s
        """, (query_embedding, query_embedding, threshold, top_k))

        results = []
        for row in cursor:
            results.append(RetrievalResult(
                chunk_id=row[0],
                text=row[1],
                start_time_seconds=row[2],
                chunk_type=row[3],
                relevance_score=row[4],
                retrieval_method="semantic"
            ))

        return results

    def _search_keyword(
        self,
        conn,
        query: str,
        top_k: int,
        threshold: float
    ) -> list[RetrievalResult]:
        """Search using full-text search."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id, text, start_time_seconds, chunk_type,
                ts_rank(to_tsvector('french', text), plainto_tsquery('french', %s)) as rank
            FROM video_chunks
            WHERE to_tsvector('french', text) @@ plainto_tsquery('french', %s)
            ORDER BY rank DESC
            LIMIT %s
        """, (query, query, top_k))

        results = []
        for row in cursor:
            rank = row[4] if row[4] else 0
            if rank > threshold:
                results.append(RetrievalResult(
                    chunk_id=row[0],
                    text=row[1],
                    start_time_seconds=row[2],
                    chunk_type=row[3],
                    relevance_score=rank,
                    retrieval_method="keyword"
                ))

        return results

    def _search_hybrid(
        self,
        conn,
        query: str,
        agent_type: str,
        top_k: int,
        threshold: float
    ) -> list[RetrievalResult]:
        """Combine semantic and keyword search."""
        semantic_results = self._search_semantic(conn, query, top_k * 2, threshold)
        keyword_results = self._search_keyword(conn, query, top_k * 2, threshold)

        # Merge and weight results
        combined = {}

        for result in semantic_results:
            score = result.relevance_score * 0.6  # 60% semantic
            combined[result.chunk_id] = RetrievalResult(
                chunk_id=result.chunk_id,
                text=result.text,
                start_time_seconds=result.start_time_seconds,
                chunk_type=result.chunk_type,
                relevance_score=score,
                retrieval_method="hybrid",
                video_title=result.video_title
            )

        for result in keyword_results:
            score = result.relevance_score * 0.4  # 40% keyword
            if result.chunk_id in combined:
                combined[result.chunk_id].relevance_score += score
            else:
                combined[result.chunk_id] = RetrievalResult(
                    chunk_id=result.chunk_id,
                    text=result.text,
                    start_time_seconds=result.start_time_seconds,
                    chunk_type=result.chunk_type,
                    relevance_score=score,
                    retrieval_method="hybrid",
                    video_title=result.video_title
                )

        # Apply agent-specific weighting
        agent_weights = self._get_agent_weights(agent_type)
        for result in combined.values():
            weight = agent_weights.get(result.chunk_type, 1.0)
            result.relevance_score *= weight

        # Sort and return top_k
        sorted_results = sorted(
            combined.values(),
            key=lambda r: r.relevance_score,
            reverse=True
        )

        return sorted_results[:top_k]

    def _search_graph(
        self,
        conn,
        query: str,
        top_k: int,
        threshold: float
    ) -> list[RetrievalResult]:
        """Search using knowledge graph relationships."""
        # This is a simplified version - full implementation in architecture doc
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT
                vc.id, vc.text, vc.start_time_seconds, vc.chunk_type,
                COUNT(cc.concept_id) as concept_matches
            FROM video_chunks vc
            LEFT JOIN chunk_concepts cc ON vc.id = cc.chunk_id
            LEFT JOIN concepts c ON cc.concept_id = c.id
            WHERE c.name ILIKE %s OR vc.text ILIKE %s
            GROUP BY vc.id
            ORDER BY concept_matches DESC
            LIMIT %s
        """, (f"%{query}%", f"%{query}%", top_k))

        results = []
        for row in cursor:
            score = min(1.0, row[4] / 10.0)  # Normalize concept matches to 0-1
            if score > threshold:
                results.append(RetrievalResult(
                    chunk_id=row[0],
                    text=row[1],
                    start_time_seconds=row[2],
                    chunk_type=row[3],
                    relevance_score=score,
                    retrieval_method="graph"
                ))

        return results

    def _get_agent_weights(self, agent_type: str) -> dict:
        """Get chunk type weights for agent."""
        weights = {
            "prospection": {
                "MINDSET": 1.5,
                "APPROACH_INTRO": 1.3,
                "EXAMPLE": 1.0,
                "STORY": 1.2
            },
            "qualification": {
                "OBJECTION": 1.4,
                "QUALIFIER": 1.3,
                "TACTIC": 1.1,
                "EXAMPLE": 1.0
            },
            "closing": {
                "CLOSING_TECHNIQUE": 1.6,
                "URGENCY": 1.4,
                "COMMITMENT": 1.5,
                "TACTIC": 1.2
            }
        }

        return weights.get(agent_type, {})
```

### Day 5: Integration Testing

```bash
# Test search on sample queries
python -c "
from scripts.search_service import HybridSearchEngine

engine = HybridSearchEngine('postgresql://user:password@localhost/rag_videos')
results = engine.search('Comment gérer les objections', agent_type='qualification', top_k=5)

for r in results:
    print(f'{r.chunk_type}: {r.text[:100]}... (score: {r.relevance_score:.2f})')
"
```

---

## Week 3: Integration - Agent & MCP

### Day 1-2: Update MCP Server

Add to existing `mcp_server.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Optional

import psycopg
from fastmcp import FastMCP

from scripts.search_service import HybridSearchEngine, RetrievalMethod

mcp = FastMCP("rag-server")
logger = logging.getLogger(__name__)

search_engine = HybridSearchEngine("postgresql://user:password@localhost/rag_videos")

@mcp.tool()
def search_content(
    query: str,
    agent_type: str = "prospection",
    top_k: int = 5,
    method: str = "hybrid"
) -> str:
    """Search knowledge base for relevant content."""
    try:
        results = search_engine.search(
            query=query,
            agent_type=agent_type,
            top_k=top_k,
            method=RetrievalMethod(method)
        )

        output = f"Found {len(results)} relevant chunks:\n\n"
        for i, r in enumerate(results, 1):
            output += (
                f"{i}. [{r.chunk_type}] {r.text[:200]}...\n"
                f"   Score: {r.relevance_score:.2f} | "
                f"Start: {r.start_time_seconds}s\n\n"
            )

        # Log retrieval event
        log_retrieval_for_feedback(
            conversation_id=0,  # Will be set by agent
            query=query,
            retrieved_chunk_ids=[r.chunk_id for r in results],
            retrieval_method=method
        )

        return output
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error searching knowledge base: {e}"

@mcp.tool()
def search_objections(objection_text: str, top_k: int = 3) -> str:
    """Find objection handling techniques."""
    try:
        results = search_engine.search(
            query=objection_text,
            agent_type="qualification",
            top_k=top_k,
            method=RetrievalMethod.HYBRID
        )

        output = "Objection handling techniques:\n\n"
        for r in results:
            output += f"- {r.text[:150]}...\n"

        return output
    except Exception as e:
        return f"Error searching objections: {e}"

@mcp.tool()
def log_retrieval_for_feedback(
    conversation_id: int,
    query: str,
    retrieved_chunk_ids: list[int],
    retrieval_method: str = "hybrid",
    retrieval_time_ms: int = 0
) -> str:
    """Log retrieval event for feedback loop."""
    try:
        with psycopg.connect("postgresql://user:password@localhost/rag_videos") as conn:
            cursor = conn.cursor()

            for chunk_id in retrieved_chunk_ids:
                cursor.execute("""
                    INSERT INTO rag_events
                    (conversation_id, chunk_id, query, retrieval_method, retrieval_time_ms)
                    VALUES (%s, %s, %s, %s, %s)
                """, (conversation_id, chunk_id, query, retrieval_method, retrieval_time_ms))

            conn.commit()

        return f"Logged {len(retrieved_chunk_ids)} retrieval events"
    except Exception as e:
        logger.error(f"Error logging retrieval: {e}")
        return f"Error logging retrieval: {e}"

@mcp.tool()
def record_conversion(
    conversation_id: int,
    lead_id: int,
    converted: bool,
    reason: str = ""
) -> str:
    """Record conversion outcome."""
    try:
        with psycopg.connect("postgresql://user:password@localhost/rag_videos") as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE conversations
                SET conversion_result = %s, outcome = %s
                WHERE id = %s
            """, (converted, reason, conversation_id))

            cursor.execute("""
                UPDATE rag_events
                SET lead_conversion = %s
                WHERE conversation_id = %s
            """, (converted, conversation_id))

            conn.commit()

        return f"Recorded conversion: {converted}"
    except Exception as e:
        logger.error(f"Error recording conversion: {e}")
        return f"Error recording conversion: {e}"
```

### Day 3-4: Agent Integration Testing

```bash
# Start MCP server
python scripts/mcp_server.py &

# Test with curl
curl -X POST http://localhost:8000/tools/search_content \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Comment gérer les objections",
    "agent_type": "qualification",
    "top_k": 5
  }'
```

### Day 5: Production Testing

```bash
# Test with all three agent types
for agent in prospection qualification closing; do
  echo "Testing $agent agent..."
  python -c "
from scripts.search_service import HybridSearchEngine
engine = HybridSearchEngine('postgresql://user:password@localhost/rag_videos')
results = engine.search('formation seduction', agent_type='$agent', top_k=3)
print(f'Agent {$agent}: {len(results)} results')
  "
done
```

---

## Week 4: Optimization - Feedback Loop & Launch

### Day 1-2: Feedback Collection Service

Create `scripts/feedback_service.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime

import psycopg

logger = logging.getLogger(__name__)

class FeedbackCollector:
    """Collects and analyzes feedback for optimization."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def get_feedback_stats(self, days: int = 7) -> dict:
        """Get feedback statistics for last N days."""
        with psycopg.connect(self.db_url) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    chunk_type,
                    COUNT(*) as total_uses,
                    COUNT(CASE WHEN was_useful THEN 1 END) as useful_count,
                    COUNT(CASE WHEN lead_conversion THEN 1 END) as conversion_count,
                    ROUND(100.0 * COUNT(CASE WHEN was_useful THEN 1 END) /
                          NULLIF(COUNT(*), 0), 2) as usefulness_rate
                FROM rag_events
                JOIN video_chunks ON rag_events.chunk_id = video_chunks.id
                WHERE rag_events.created_at > NOW() - INTERVAL '%d days'
                GROUP BY chunk_type
                ORDER BY usefulness_rate DESC
            """ % days)

            stats = {}
            for row in cursor:
                stats[row[0]] = {
                    "total_uses": row[1],
                    "useful_count": row[2],
                    "conversion_count": row[3],
                    "usefulness_rate": row[4]
                }

            return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = FeedbackCollector("postgresql://user:password@localhost/rag_videos")
    stats = collector.get_feedback_stats(days=7)

    import json
    print(json.dumps(stats, indent=2))
```

### Day 3-4: Analytics & Reporting

Create `scripts/analytics.py`:

```python
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import psycopg

logger = logging.getLogger(__name__)

class RAGAnalytics:
    """Generates analytics reports."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def weekly_report(self) -> dict:
        """Generate weekly optimization report."""
        with psycopg.connect(self.db_url) as conn:
            cursor = conn.cursor()

            # Conversion rate
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT conversation_id) as total_conversations,
                    COUNT(DISTINCT CASE WHEN lead_conversion THEN conversation_id END) as conversions,
                    ROUND(100.0 * COUNT(DISTINCT CASE WHEN lead_conversion THEN conversation_id END) /
                          NULLIF(COUNT(DISTINCT conversation_id), 0), 2) as conversion_rate
                FROM rag_events
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)

            conv_row = cursor.fetchone()
            report = {
                "period": "Last 7 days",
                "total_conversations": conv_row[0],
                "conversions": conv_row[1],
                "conversion_rate": conv_row[2],
                "top_chunks": []
            }

            # Top performing chunks
            cursor.execute("""
                SELECT
                    chunk_id,
                    chunk_type,
                    COUNT(*) as uses,
                    ROUND(100.0 * COUNT(CASE WHEN lead_conversion THEN 1 END) /
                          NULLIF(COUNT(*), 0), 2) as conversion_rate
                FROM rag_events
                JOIN video_chunks ON rag_events.chunk_id = video_chunks.id
                WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY chunk_id, chunk_type
                ORDER BY conversion_rate DESC
                LIMIT 10
            """)

            for row in cursor:
                report["top_chunks"].append({
                    "chunk_id": row[0],
                    "chunk_type": row[1],
                    "uses": row[2],
                    "conversion_rate": row[3]
                })

            return report

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analytics = RAGAnalytics("postgresql://user:password@localhost/rag_videos")
    report = analytics.weekly_report()
    print(json.dumps(report, indent=2))
```

### Day 5: Production Deployment

```bash
# Create systemd service for background tasks
sudo cat > /etc/systemd/system/rag-optimizer.service << EOF
[Unit]
Description=RAG Weekly Optimizer
After=network.target

[Service]
Type=simple
User=rag_user
WorkingDirectory=/opt/rag
ExecStart=/usr/bin/python3 scripts/analytics.py
Restart=always
RestartSec=604800

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable rag-optimizer.service
sudo systemctl start rag-optimizer.service
```

---

## Validation Checklist

- [ ] All 7 database tables created successfully
- [ ] pgvector extension installed and working
- [ ] Chunking service processes SRT files without errors
- [ ] Embedding pipeline generates vectors (dimension: 384)
- [ ] Semantic search returns results with latency <200ms
- [ ] Keyword search finds relevant phrases
- [ ] Hybrid search combines results correctly
- [ ] All 3 agents can retrieve agent-specific chunks
- [ ] MCP tools exposed and callable
- [ ] Feedback loop logs retrieval events
- [ ] Analytics report generates weekly

---

## Success Criteria

**Week 1**: ✓ Database ready, 10K+ chunks created
**Week 2**: ✓ Embeddings generated, search latency <200ms
**Week 3**: ✓ All agents integrated, MCP tools working
**Week 4**: ✓ Feedback loop operational, ready for production

---

**Document Version**: 1.0
**Created**: 2026-03-14
**Status**: Ready for Implementation
