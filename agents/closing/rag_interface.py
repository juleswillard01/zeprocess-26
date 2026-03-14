"""RAG interface for pgvector semantic search."""

from __future__ import annotations

import logging
from typing import Any, Optional

import asyncpg
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class RAGInterface:
    """pgvector semantic search for agent decision-making."""

    def __init__(self, db_url: str, model_name: str = "sentence-transformers/paraphrase-MiniLM-L6-v2"):
        """Initialize RAG interface."""
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
        self.embedding_model = SentenceTransformer(model_name)
        self.embedding_dim = 384  # MiniLM output dimension

    async def connect(self) -> None:
        """Initialize connection pool and verify pgvector."""
        self.pool = await asyncpg.create_pool(self.db_url)

        if self.pool is None:
            raise RuntimeError("Failed to create connection pool")

        # Verify pgvector is available
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT 1 FROM pg_extension WHERE extname='vector'"
            )
            if result is None:
                logger.warning("pgvector extension not found, creating...")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        logger.info("RAG interface connected to pgvector")

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search embeddings table for relevant content."""
        if not self.pool:
            raise RuntimeError("RAG interface not connected")

        # Generate embedding for query
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False)
        query_embedding_list = query_embedding.tolist()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    source,
                    content,
                    metadata,
                    1 - (embedding <=> $1::vector) as similarity
                FROM embeddings
                WHERE 1 - (embedding <=> $1::vector) > $2
                ORDER BY similarity DESC
                LIMIT $3
                """,
                query_embedding_list,
                threshold,
                top_k,
            )

        results = [
            {
                "id": row["id"],
                "source": row["source"],
                "content": row["content"],
                "similarity": float(row["similarity"]),
                "metadata": row["metadata"],
            }
            for row in rows
        ]

        logger.info(
            f"RAG search completed",
            extra={
                "query": query[:50],
                "results_count": len(results),
                "avg_similarity": (
                    sum(r["similarity"] for r in results) / len(results)
                    if results
                    else 0
                ),
            },
        )

        return results

    async def search_by_segment(
        self,
        query: str,
        segment: str,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search embeddings filtered by segment."""
        if not self.pool:
            raise RuntimeError("RAG interface not connected")

        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False)
        query_embedding_list = query_embedding.tolist()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    source,
                    content,
                    metadata,
                    1 - (embedding <=> $1::vector) as similarity
                FROM embeddings
                WHERE 1 - (embedding <=> $1::vector) > $2
                    AND metadata->>'segment' = $3
                ORDER BY similarity DESC
                LIMIT $4
                """,
                query_embedding_list,
                threshold,
                segment,
                top_k,
            )

        results = [
            {
                "id": row["id"],
                "source": row["source"],
                "content": row["content"],
                "similarity": float(row["similarity"]),
                "metadata": row["metadata"],
            }
            for row in rows
        ]

        return results

    async def index_document(
        self,
        content: str,
        source: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Index a new document."""
        if not self.pool:
            raise RuntimeError("RAG interface not connected")

        embedding = self.embedding_model.encode(content, convert_to_tensor=False)
        embedding_list = embedding.tolist()

        async with self.pool.acquire() as conn:
            doc_id = await conn.fetchval(
                """
                INSERT INTO embeddings (source, content, embedding, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                source,
                content,
                embedding_list,
                metadata or {},
            )

        logger.info(f"Indexed document: {source}")
        return doc_id

    def get_metrics(self) -> dict[str, Any]:
        """Get RAG interface metrics."""
        return {
            "embedding_model": self.embedding_model.get_sentence_embedding_dimension(),
            "pool_status": "connected" if self.pool else "disconnected",
        }
