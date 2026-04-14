"""
3-layer Memory Store backed by Redis.

PPT Slide 9 — Flow 5 (Write Path):
  After task execution, agents write results to P05 memory.
  This creates a persistent audit trail and enables cross-session learning.

Memory layers:
  episodic   — session-scoped interaction log          TTL: 1 hour
  semantic   — cross-session facts and learned context TTL: 7 days
  procedural — validated workflows and task patterns   TTL: permanent

Keys:
  memory:{type}:{agent_id}:{uuid}   → JSON entry
  memory_index:{agent_id}:{type}    → sorted set for ordered retrieval
"""
import json
import os
import uuid
from typing import Any, Dict, List, Optional
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

TTL_MAP = {
    "episodic":   3600,            # 1 hour
    "semantic":   3600 * 24 * 7,  # 7 days
    "procedural": 0,               # no expiry
}


class MemoryStore:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                REDIS_URL, encoding="utf-8", decode_responses=True
            )
        return self._redis

    async def write(self, entry: Dict[str, Any]) -> str:
        """
        Write a memory entry.
        Returns the Redis key for the stored entry.
        """
        r = await self._get_redis()
        memory_type = entry.get("memory_type", "episodic")
        agent_id    = entry.get("agent_id", "unknown")
        key = f"memory:{memory_type}:{agent_id}:{uuid.uuid4()}"

        ttl = TTL_MAP.get(memory_type, 3600)
        if ttl > 0:
            await r.setex(key, ttl, json.dumps(entry))
        else:
            await r.set(key, json.dumps(entry))

        # Maintain a sorted set per agent + type for recency-ordered queries
        import time
        score = time.time()
        await r.zadd(
            f"memory_index:{agent_id}:{memory_type}",
            {key: score},
        )
        return key

    async def query(
        self,
        agent_id: str,
        memory_type: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent memory entries for a given agent.
        If memory_type is None, retrieves across all types.
        """
        r = await self._get_redis()

        if memory_type:
            index_keys = [f"memory_index:{agent_id}:{memory_type}"]
        else:
            index_keys = [f"memory_index:{agent_id}:{mt}" for mt in TTL_MAP]

        all_keys = []
        for idx_key in index_keys:
            keys = await r.zrange(idx_key, -limit, -1, rev=True)
            all_keys.extend(keys)

        all_keys = all_keys[:limit]

        results = []
        for key in all_keys:
            data = await r.get(key)
            if data:
                results.append(json.loads(data))
        return results
