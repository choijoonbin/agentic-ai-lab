"""
RAG search and document ingestion endpoints.

Ingest flow : document → chunker → embedder (sentence-transformers) → pgvector
Search flow : query → embedder → ANN search (pgvector) → ranked results
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..rag.pipeline import RAGPipeline

router = APIRouter()
rag = RAGPipeline()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    tenant_id: str = "default"
    filters: Optional[Dict[str, Any]] = None


class IngestRequest(BaseModel):
    documents: List[Dict[str, Any]]  # Each: {"content": str, "metadata": dict}
    tenant_id: str = "default"


@router.post("/search")
async def search(req: SearchRequest):
    """
    Semantic search over ingested knowledge chunks.
    Returns top-k results sorted by cosine similarity.
    """
    try:
        results = await rag.search(
            query=req.query,
            top_k=req.top_k,
            tenant_id=req.tenant_id,
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def ingest(req: IngestRequest):
    """
    Ingest documents into the vector store.
    Documents are chunked, embedded, and stored in pgvector.
    """
    try:
        count = await rag.ingest(documents=req.documents, tenant_id=req.tenant_id)
        return {"ingested": count, "tenant_id": req.tenant_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
