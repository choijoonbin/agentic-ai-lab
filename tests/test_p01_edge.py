"""
P01 Edge API — Integration Tests (FastAPI TestClient, no external services needed)

Covers:
  - Health check
  - JWT login (success / wrong password / tenant mismatch)
  - Gateway request without token → 403
"""
import sys
import os

# Make edge_api importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "edge_api"))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ─── Health ────────────────────────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["plane"] == "P01-Edge"


# ─── Auth / JWT ────────────────────────────────────────────────────────────

def test_login_success():
    resp = client.post("/auth/login", json={
        "username":  "analyst",
        "password":  "demo123",
        "tenant_id": "acme",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password():
    resp = client.post("/auth/login", json={
        "username":  "analyst",
        "password":  "wrongpass",
        "tenant_id": "acme",
    })
    assert resp.status_code == 401


def test_login_tenant_mismatch():
    resp = client.post("/auth/login", json={
        "username":  "analyst",
        "password":  "demo123",
        "tenant_id": "other_tenant",
    })
    assert resp.status_code == 403


def test_login_unknown_user():
    resp = client.post("/auth/login", json={
        "username":  "ghost",
        "password":  "x",
        "tenant_id": "acme",
    })
    assert resp.status_code == 401


def test_gateway_without_token_denied():
    resp = client.post("/gateway/request", json={
        "task":   "list files",
        "domain": "operations",
    })
    assert resp.status_code in (401, 403)
