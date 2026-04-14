"""
Risk Classifier — assigns risk tier based on task content and context.
Simple keyword + heuristic classifier; swap with ML model in production.
"""
from typing import List, Tuple
import os

HIGH_RISK_THRESHOLD = float(os.getenv("HIGH_RISK_THRESHOLD", "0.7"))

HIGH_RISK_KEYWORDS = {
    "delete", "remove", "drop", "truncate", "wipe",
    "send email", "send message", "post", "publish",
    "transfer", "payment", "wire", "execute trade",
    "override", "bypass", "escalate", "admin",
}

MEDIUM_RISK_KEYWORDS = {
    "update", "modify", "change", "write", "create",
    "insert", "upload", "import", "configure",
}


class RiskClassifier:
    def classify(
        self,
        task: str,
        domain: str | None,
        user_role: str | None,
        requested_scope: List[str],
    ) -> Tuple[float, str]:
        """Returns (risk_score: float, risk_tier: str)."""
        score = 0.0
        task_lower = task.lower()

        # Keyword scoring
        for kw in HIGH_RISK_KEYWORDS:
            if kw in task_lower:
                score += 0.4
                break
        for kw in MEDIUM_RISK_KEYWORDS:
            if kw in task_lower:
                score += 0.2
                break

        # Scope scoring
        if "action" in requested_scope:
            score += 0.3
        elif "write" in requested_scope:
            score += 0.15

        # Domain scoring
        if domain in {"finance", "operations"}:
            score += 0.1

        # Role adjustment
        if user_role == "admin":
            score *= 0.8  # admins slightly lower risk

        score = min(score, 1.0)

        if score >= HIGH_RISK_THRESHOLD:
            tier = "high"
        elif score >= 0.4:
            tier = "medium"
        else:
            tier = "low"

        return round(score, 3), tier
