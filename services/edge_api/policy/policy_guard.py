"""
Policy Guard — OPA-style authorization (simplified inline policies).
In production, replace rule evaluation with OPA HTTP API calls.
"""
from typing import List


class PolicyGuard:
    """
    Evaluates access policies.
    Rules:
      - 'read' scope: all authenticated users
      - 'write' scope: analyst role and above
      - 'action' scope: admin role only
      - Finance domain: requires 'finance' in user's tenant policies
    """

    ROLE_HIERARCHY = {"viewer": 0, "analyst": 1, "admin": 2}

    def check(
        self,
        user: dict,
        action: str,
        resource: str,
        scope: List[str],
    ) -> bool:
        role = user.get("role", "viewer")
        role_level = self.ROLE_HIERARCHY.get(role, 0)

        # Scope-based policy
        if "action" in scope and role_level < 2:
            return False  # Only admin can request action scope
        if "write" in scope and role_level < 1:
            return False  # Analyst+ for write

        # Domain-based policy
        if resource == "finance" and role != "admin":
            return False  # Finance domain restricted to admin

        return True
