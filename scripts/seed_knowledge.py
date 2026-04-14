#!/usr/bin/env python3
"""
Seed demo knowledge documents into P05 Knowledge API.

Usage:
  # Ensure Knowledge API is running first
  docker compose up knowledge_api postgres -d

  python scripts/seed_knowledge.py
"""
import asyncio
import httpx

KNOWLEDGE_API_URL = "http://localhost:8003"
TENANT_ID = "acme"

DEMO_DOCUMENTS = [
    {
        "content": (
            "Enterprise Agentic AI 5-Plane Architecture: "
            "P01 Edge & Trust, P02 Control Plane, P03 Domain Agent Runtime, "
            "P04 Shared Integration, P05 Knowledge/Memory/Model. "
            "Each plane has a distinct responsibility and communicates via ContextEnvelope."
        ),
        "metadata": {"source": "architecture_overview", "plane": "all"},
    },
    {
        "content": (
            "P01 Edge & Trust Boundary handles all inbound requests. "
            "Responsibilities: JWT authentication (AuthN), OPA-style policy enforcement (AuthZ), "
            "risk classification (low/medium/high), ContextEnvelope creation with "
            "tenant_id, trace_id, risk_tier, scope, and delegation_chain."
        ),
        "metadata": {"source": "p01_guide", "plane": "P01"},
    },
    {
        "content": (
            "P02 Control Plane orchestrates multi-step agent workflows using LangGraph. "
            "Key nodes: planner (task decomposition), approval_gate (HITL for risk_score >= 0.8), "
            "dispatcher (calls P03 agents), aggregator (merges results). "
            "State is checkpointed to Redis for durable pause/resume."
        ),
        "metadata": {"source": "p02_guide", "plane": "P02"},
    },
    {
        "content": (
            "P02 HITL Approval Flow: "
            "1) planner calculates risk_score >= 0.8 → requires_approval=True. "
            "2) approval_gate saves pending approval to Redis. "
            "3) Human reviewer calls GET /approval/pending/{session_id} to inspect. "
            "4) Human calls POST /approval/decide with approved=true/false. "
            "5) Workflow resumes from checkpoint via dispatcher — does NOT re-plan from scratch."
        ),
        "metadata": {"source": "p02_hitl", "plane": "P02"},
    },
    {
        "content": (
            "P03 Domain Agent Runtime hosts 4 specialized agents: "
            "ResearchAgent (web_search via P04, knowledge via P05), "
            "OperationsAgent (get_metrics via P04), "
            "CustomerAgent (crm_lookup via P04), "
            "FinanceAgent (finance_query via P04, admin-only). "
            "All extend BaseDomainAgent which handles P04/P05 integration."
        ),
        "metadata": {"source": "p03_guide", "plane": "P03"},
    },
    {
        "content": (
            "P04 Shared Integration Layer (MCP Server) — Connector model: "
            "Read connectors (web_search, get_metrics, crm_lookup, finance_query): auto-approved. "
            "Write connectors (db_write, create_ticket): RBAC-checked (analyst+). "
            "Action connectors (send_email): HITL-gated (approval_granted=True required). "
            "All agents call tools via POST /tools/call."
        ),
        "metadata": {"source": "p04_guide", "plane": "P04"},
    },
    {
        "content": (
            "P05 Shared Knowledge / Memory / Model: "
            "RAG: pgvector with sentence-transformers (all-MiniLM-L6-v2, 384-dim). "
            "Memory: 3 layers — episodic (1h TTL), semantic (7d TTL), procedural (permanent). "
            "Model Gateway: LiteLLM abstracts Anthropic/OpenAI/etc behind single API. "
            "Write Path (Slide 9 Flow 5): agents write results to memory after task completion."
        ),
        "metadata": {"source": "p05_guide", "plane": "P05"},
    },
    {
        "content": (
            "ContextEnvelope — the single structured object passed between all planes. "
            "Fields: trace_id (uuid), tenant_id, user_id, session_id, "
            "risk_tier (low/medium/high), data_class (public/internal/confidential/restricted), "
            "scope (read/write/action), delegation_chain (agent IDs), metadata. "
            "Created at P01, enriched at P02, consumed by P03/P04/P05."
        ),
        "metadata": {"source": "schema_guide", "plane": "all"},
    },
    {
        "content": (
            "Flow Semantics (5 rules from Slide 9): "
            "Flow 1: All requests enter via T1 Admission (P01). "
            "Flow 2: P02 hands off subtasks to P03 domain agents. "
            "Flow 3: P02 control loop — HITL approval only for high-risk (conditional). "
            "Flow 4: P03 agents independently access P04 (tools) and P05 (knowledge). "
            "Flow 5: Write path — P03 writes results back to P05 memory after execution."
        ),
        "metadata": {"source": "flow_semantics", "plane": "all"},
    },
]


async def main():
    print(f"Seeding {len(DEMO_DOCUMENTS)} documents to {KNOWLEDGE_API_URL}...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Health check first
        try:
            r = await client.get(f"{KNOWLEDGE_API_URL}/health")
            print(f"Health: {r.json()}")
        except Exception as e:
            print(f"ERROR: Knowledge API not reachable at {KNOWLEDGE_API_URL}: {e}")
            return

        resp = await client.post(
            f"{KNOWLEDGE_API_URL}/knowledge/ingest",
            json={"documents": DEMO_DOCUMENTS, "tenant_id": TENANT_ID},
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"Seeded {result['ingested']} documents for tenant '{TENANT_ID}'")

        # Quick verification search
        resp2 = await client.post(
            f"{KNOWLEDGE_API_URL}/knowledge/search",
            json={"query": "HITL approval flow", "top_k": 2, "tenant_id": TENANT_ID},
        )
        resp2.raise_for_status()
        results = resp2.json()["results"]
        print(f"\nVerification search ('HITL approval flow'): {len(results)} results")
        for r in results:
            print(f"  [{r['similarity']:.3f}] {r['content'][:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
