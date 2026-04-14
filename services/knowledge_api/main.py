"""
P05 — Shared Knowledge / Memory / Model Gateway

Responsibilities:
  - RAG pipeline: document ingestion + vector search via pgvector
  - 3-layer memory: episodic (short) / semantic (medium) / procedural (permanent)
  - LiteLLM model gateway: single interface to any LLM provider

All domain agents (P03) query this service for:
  1. Relevant knowledge before calling the LLM
  2. Writing/reading session memory
  3. LLM completions through a unified endpoint
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from .routers import knowledge, memory, models, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("P05 Knowledge API starting up")
    yield
    logger.info("P05 Knowledge API shutting down")


app = FastAPI(
    title="P05 — Shared Knowledge / Memory / Model",
    description="RAG pipeline (pgvector), 3-layer memory (Redis), LiteLLM model gateway",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
app.include_router(memory.router,    prefix="/memory",    tags=["memory"])
app.include_router(models.router,    prefix="/models",    tags=["models"])
app.include_router(health.router,    tags=["health"])
