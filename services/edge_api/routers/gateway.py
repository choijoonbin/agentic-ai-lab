"""
Gateway router — receives agent requests, applies policy + classifier,
builds context envelope, forwards to Control Plane.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, Optional
import httpx
import os

from ..auth.jwt_handler import get_current_user
from ..policy.policy_guard import PolicyGuard
from ..classifier.risk_classifier import RiskClassifier
from schemas import ContextEnvelope, RiskTier, ConnectorScope

router = APIRouter()
policy_guard = PolicyGuard()
risk_classifier = RiskClassifier()

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8001")


class AgentRequest(BaseModel):
    task: str
    domain: Optional[str] = None
    parameters: Dict[str, Any] = {}
    requested_scope: list[str] = ["read"]


@router.post("/request")
async def submit_request(
    req: AgentRequest,
    current_user: dict = Depends(get_current_user),
):
    # 1. Policy check (AuthZ)
    allowed = policy_guard.check(
        user=current_user,
        action="submit_task",
        resource=req.domain or "general",
        scope=req.requested_scope,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Policy denied")

    # 2. Risk classification
    risk_score, risk_tier = risk_classifier.classify(
        task=req.task,
        domain=req.domain,
        user_role=current_user.get("role"),
        requested_scope=req.requested_scope,
    )

    # 3. Build context envelope
    envelope = ContextEnvelope(
        tenant_id=current_user["tenant_id"],
        user_id=current_user["sub"],
        risk_tier=risk_tier,
        scope=[ConnectorScope(s) for s in req.requested_scope if s in ConnectorScope.__members__.values() or s in [e.value for e in ConnectorScope]],
        metadata={"risk_score": risk_score, "domain": req.domain},
    )

    # 4. Forward to Control Plane
    payload = {
        "task": req.task,
        "domain": req.domain,
        "parameters": req.parameters,
        "context": envelope.model_dump(mode="json"),
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{CONTROL_PLANE_URL}/workflow/run", json=payload
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Control plane error: {e}")
