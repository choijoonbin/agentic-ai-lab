"""
P01 — Edge & Trust Boundary
FastAPI application that serves as the single entry point for all agent requests.
Responsibilities:
  - JWT authentication (AuthN)
  - Policy enforcement (AuthZ via OPA-style guard)
  - Risk classification
  - Context envelope creation
  - Session management
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .routers import auth, gateway, health
from .middleware.auth_middleware import AuthMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("P01 Edge API starting up")
    yield
    logger.info("P01 Edge API shutting down")


app = FastAPI(
    title="P01 — Edge & Trust Boundary",
    description="JWT auth, policy enforcement, risk classification, context envelope creation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(gateway.router, prefix="/gateway", tags=["gateway"])
app.include_router(health.router, tags=["health"])
