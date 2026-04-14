#!/usr/bin/env python3
"""
End-to-end demo: Login → low-risk research task → result.

This script walks through the full 5-plane request path:
  Step 1: POST /auth/login        → JWT token (P01 AuthN)
  Step 2: POST /gateway/request   → P01 policy check + risk classify → forward to P02
  Step 3: P02 plan → P03 execute → P04 tools + P05 knowledge → result

Usage:
  # Start full stack first
  docker compose up -d

  python scripts/demo_flow.py
"""
import asyncio
import httpx

EDGE_API_URL = "http://localhost:8000"


async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:

        # ── Step 1: Login ───────────────────────────────────────────────────
        print("=" * 60)
        print("Step 1: JWT Login (P01 AuthN)")
        resp = await client.post(f"{EDGE_API_URL}/auth/login", json={
            "username":  "analyst",
            "password":  "demo123",
            "tenant_id": "acme",
        })
        resp.raise_for_status()
        token = resp.json()["access_token"]
        print(f"  Token: {token[:50]}...")

        # ── Step 2: Low-risk research task ──────────────────────────────────
        print("\nStep 2: Submit research task (read scope → low risk, no HITL)")
        resp = await client.post(
            f"{EDGE_API_URL}/gateway/request",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "task":             "Summarize enterprise AI adoption trends for Q1 2026",
                "domain":           "research",
                "requested_scope":  ["read"],
            },
        )
        print(f"  Status: {resp.status_code}")
        body = resp.json()
        print(f"  Completed: {body.get('completed')}")
        print(f"  Requires approval: {body.get('requires_approval')}")
        print(f"  Subtask count: {body.get('subtask_count')}")

        # ── Step 3: Verify all service health ───────────────────────────────
        print("\nStep 3: Health check all planes")
        for name, url in [
            ("P01 Edge",         "http://localhost:8000/health"),
            ("P02 Control",      "http://localhost:8001/health"),
            ("P04 MCP Server",   "http://localhost:8002/health"),
            ("P05 Knowledge",    "http://localhost:8003/health"),
            ("P03 Agent Worker", "http://localhost:8004/health"),
        ]:
            try:
                r = await client.get(url, timeout=3.0)
                status = r.json().get("status", "?")
                print(f"  {name}: {status}")
            except Exception as e:
                print(f"  {name}: UNREACHABLE ({e})")

        print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
