"""
P01 Policy Guard — Unit Tests

Validates RBAC rules:
  viewer  : read only
  analyst : read + write, no action, no finance
  admin   : read + write + action, including finance
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "edge_api"))

from policy.policy_guard import PolicyGuard

guard = PolicyGuard()


# ─── Viewer ────────────────────────────────────────────────────────────────

def test_viewer_read_allowed():
    assert guard.check({"role": "viewer"}, "submit_task", "research", ["read"]) is True


def test_viewer_write_denied():
    assert guard.check({"role": "viewer"}, "submit_task", "research", ["write"]) is False


def test_viewer_action_denied():
    assert guard.check({"role": "viewer"}, "submit_task", "research", ["action"]) is False


# ─── Analyst ───────────────────────────────────────────────────────────────

def test_analyst_read_allowed():
    assert guard.check({"role": "analyst"}, "submit_task", "research", ["read"]) is True


def test_analyst_write_allowed():
    assert guard.check({"role": "analyst"}, "submit_task", "customer", ["write"]) is True


def test_analyst_action_denied():
    assert guard.check({"role": "analyst"}, "submit_task", "research", ["action"]) is False


def test_analyst_finance_denied():
    assert guard.check({"role": "analyst"}, "submit_task", "finance", ["read"]) is False


# ─── Admin ─────────────────────────────────────────────────────────────────

def test_admin_action_allowed():
    assert guard.check({"role": "admin"}, "submit_task", "research", ["action"]) is True


def test_admin_finance_allowed():
    assert guard.check({"role": "admin"}, "submit_task", "finance", ["read"]) is True


def test_admin_finance_write_allowed():
    assert guard.check({"role": "admin"}, "submit_task", "finance", ["write"]) is True
