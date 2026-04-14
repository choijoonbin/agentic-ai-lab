"""
LiteLLM Model Gateway — unified LLM completion endpoint.

Abstracts over multiple LLM providers (Anthropic, OpenAI, etc.)
so all agents use a single interface regardless of underlying model.
Switch models by changing LITELLM_MODEL env var — no code changes needed.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import litellm
import os

router = APIRouter()
DEFAULT_MODEL = os.getenv("LITELLM_MODEL", "anthropic/claude-sonnet-4-6")


class CompletionRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7
    metadata: Dict[str, Any] = {}


@router.post("/complete")
async def complete(req: CompletionRequest):
    """
    Unified LLM completion. Supports all LiteLLM-compatible models.
    Set model in request body or via LITELLM_MODEL env var.
    """
    try:
        response = await litellm.acompletion(
            model=req.model or DEFAULT_MODEL,
            messages=req.messages,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_models():
    """List available models and their tiers."""
    return {
        "models": [
            {"id": "anthropic/claude-sonnet-4-6",          "provider": "anthropic", "tier": "T1", "use_case": "complex reasoning"},
            {"id": "anthropic/claude-haiku-4-5-20251001",  "provider": "anthropic", "tier": "T2", "use_case": "fast tasks"},
            {"id": "openai/gpt-4o",                        "provider": "openai",    "tier": "T1", "use_case": "general purpose"},
        ]
    }
