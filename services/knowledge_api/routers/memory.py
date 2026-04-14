"""
Memory layer endpoints.

3 memory types (Write Path from slide 9, Flow 5):
  episodic   — session-scoped interaction history  (TTL: 1h)
  semantic   — cross-session learned facts         (TTL: 7d)
  procedural — task execution patterns / workflows (TTL: permanent)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from ..memory.store import MemoryStore

router = APIRouter()
store = MemoryStore()


class MemoryEntry(BaseModel):
    session_id: str
    agent_id: str
    content: str
    memory_type: str = "episodic"  # episodic | semantic | procedural
    metadata: Dict[str, Any] = {}


class MemoryQuery(BaseModel):
    agent_id: str
    memory_type: Optional[str] = None  # None = all types
    limit: int = 10


@router.post("/write")
async def write_memory(entry: MemoryEntry):
    """Write an interaction or learned fact to the appropriate memory layer."""
    try:
        key = await store.write(entry.model_dump())
        return {"key": key, "status": "stored", "memory_type": entry.memory_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_memory(req: MemoryQuery):
    """Retrieve recent memory entries for a given agent."""
    try:
        results = await store.query(
            agent_id=req.agent_id,
            memory_type=req.memory_type,
            limit=req.limit,
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
