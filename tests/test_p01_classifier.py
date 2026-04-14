"""
P01 Risk Classifier — Unit Tests

Validates that the keyword + scope + domain heuristics produce
the correct risk tier for representative inputs.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "edge_api"))

from classifier.risk_classifier import RiskClassifier

clf = RiskClassifier()


# ─── Low risk ──────────────────────────────────────────────────────────────

def test_read_only_research_is_low():
    score, tier = clf.classify(
        task="What is the current project status?",
        domain="research",
        user_role="analyst",
        requested_scope=["read"],
    )
    assert tier == "low", f"Expected low, got {tier} (score={score})"


# ─── Medium risk ───────────────────────────────────────────────────────────

def test_write_scope_elevates_risk():
    score, tier = clf.classify(
        task="Update user profile settings",
        domain="customer",
        user_role="analyst",
        requested_scope=["write"],
    )
    assert tier in ("medium", "high")


# ─── High risk ─────────────────────────────────────────────────────────────

def test_delete_keyword_is_high():
    score, tier = clf.classify(
        task="Delete all old records from the production database",
        domain="operations",
        user_role="analyst",
        requested_scope=["action"],
    )
    assert tier == "high", f"Expected high, got {tier} (score={score})"


def test_action_scope_finance_is_high():
    score, tier = clf.classify(
        task="Execute wire transfer for Q1 settlement",
        domain="finance",
        user_role="admin",
        requested_scope=["action"],
    )
    assert tier == "high"


# ─── Role modifier ─────────────────────────────────────────────────────────

def test_admin_lower_score_than_analyst():
    score_admin,  _ = clf.classify("delete logs", "operations", "admin",   ["write"])
    score_analyst, _ = clf.classify("delete logs", "operations", "analyst", ["write"])
    assert score_admin < score_analyst, (
        f"Admin score ({score_admin}) should be lower than analyst ({score_analyst})"
    )


# ─── Score bounds ──────────────────────────────────────────────────────────

def test_score_between_0_and_1():
    for task in ["read status", "delete everything", "send payment wire transfer now"]:
        score, _ = clf.classify(task, "finance", "analyst", ["action"])
        assert 0.0 <= score <= 1.0, f"Score out of bounds: {score}"
