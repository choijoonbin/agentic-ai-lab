"""
RAG Pipeline — pgvector-backed retrieval augmented generation.

Architecture:
  Ingest: document → text chunker → sentence-transformers embedder → pgvector INSERT
  Search: query string → embedder → pgvector ANN (cosine) → top-k results

Prerequisites (handled by docker-compose):
  - PostgreSQL 16 with pgvector extension
  - Tables auto-created on first use via _ensure_schema()
"""
import os
from typing import Any, Dict, List
import asyncpg
from sentence_transformers import SentenceTransformer

POSTGRES_HOST     = os.getenv("POSTGRES_HOST",     "localhost")
POSTGRES_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB       = os.getenv("POSTGRES_DB",       "agentic_ai")
POSTGRES_USER     = os.getenv("POSTGRES_USER",     "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM      = 384  # all-MiniLM-L6-v2 output dimension


class RAGPipeline:
    def __init__(self):
        self._pool: asyncpg.Pool | None = None
        # Load once at startup; runs locally via sentence-transformers
        self._embedder = SentenceTransformer(EMBEDDING_MODEL)

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                min_size=2,
                max_size=10,
            )
            await self._ensure_schema()
        return self._pool

    async def _ensure_schema(self):
        """Create pgvector extension and knowledge_chunks table if not present."""
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id          SERIAL PRIMARY KEY,
                    tenant_id   TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    embedding   vector({VECTOR_DIM}),
                    metadata    JSONB DEFAULT '{{}}'::jsonb,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            # IVFFlat index for approximate nearest neighbour search
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS knowledge_chunks_vec_idx
                ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)

    def _embed(self, text: str) -> List[float]:
        return self._embedder.encode(text, normalize_embeddings=True).tolist()

    async def ingest(self, documents: List[Dict[str, Any]], tenant_id: str) -> int:
        """
        Embed and store documents.
        Each document: {"content": str, "metadata": dict}
        Returns number of documents stored.
        """
        pool = await self._get_pool()
        count = 0
        async with pool.acquire() as conn:
            for doc in documents:
                embedding = self._embed(doc["content"])
                await conn.execute(
                    """
                    INSERT INTO knowledge_chunks (tenant_id, content, embedding, metadata)
                    VALUES ($1, $2, $3::vector, $4::jsonb)
                    """,
                    tenant_id,
                    doc["content"],
                    str(embedding),
                    doc.get("metadata", {}),
                )
                count += 1
        return count

    async def search(
        self, query: str, top_k: int, tenant_id: str
    ) -> List[Dict[str, Any]]:
        """
        Semantic search via cosine similarity.
        Returns top-k chunks with similarity score [0, 1].
        """
        pool = await self._get_pool()
        embedding = self._embed(query)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content, metadata,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM knowledge_chunks
                WHERE tenant_id = $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                str(embedding),
                tenant_id,
                top_k,
            )
        return [
            {
                "content":    row["content"],
                "metadata":   dict(row["metadata"]),
                "similarity": round(float(row["similarity"]), 4),
            }
            for row in rows
        ]
