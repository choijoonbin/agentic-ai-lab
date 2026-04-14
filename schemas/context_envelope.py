"""
Context Envelope — the single structured object passed between planes.
Every inter-service call includes this envelope for end-to-end traceability.
"""
from __future__ import annotations
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ConnectorScope(str, Enum):
    READ = "read"
    WRITE = "write"
    ACTION = "action"


class ContextEnvelope(BaseModel):
    """
    Immutable context passed through all planes.
    Created at P01 (Edge), enriched at P02 (Control), consumed everywhere.
    """
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    user_id: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_tier: RiskTier = RiskTier.LOW
    data_class: DataClass = DataClass.INTERNAL
    scope: List[ConnectorScope] = Field(default_factory=lambda: [ConnectorScope.READ])
    delegation_chain: List[str] = Field(default_factory=list)  # agent IDs
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True

    def with_delegation(self, agent_id: str) -> "ContextEnvelope":
        """Return new envelope with agent added to delegation chain."""
        return self.model_copy(
            update={"delegation_chain": self.delegation_chain + [agent_id]}
        )

    def elevate_risk(self, new_tier: RiskTier) -> "ContextEnvelope":
        """Return new envelope with elevated risk tier."""
        return self.model_copy(update={"risk_tier": new_tier})
