"""LLM-Konfiguration und Status Endpunkte."""

from __future__ import annotations
from fastapi import APIRouter
from core.llm.llm_router import get_llm_router

router = APIRouter()


@router.get("/status")
async def llm_status():
    """Status aller konfigurierten LLM-Provider."""
    return get_llm_router().get_status()


@router.get("/models")
async def list_models():
    """Verfügbare Modelle pro Provider auflisten."""
    router_inst = get_llm_router()
    models = {}
    if router_inst._ollama and router_inst._ollama.available:
        models["ollama"] = await router_inst._ollama.list_models()
    if router_inst._claude:
        models["claude"] = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"]
    if router_inst._openai:
        models["openai"] = ["gpt-4o-mini", "gpt-4o"]
    return models


@router.post("/test")
async def test_llm(provider: str = "ollama", model: str = None):
    """LLM-Provider testen."""
    from core.llm.llm_router import LLMRequest
    response = await get_llm_router().complete(LLMRequest(
        prompt      = "Antworte mit genau einem Satz auf Deutsch: Was ist 2+2?",
        provider    = provider,
        model       = model,
        max_tokens  = 50,
        prompt_type = "test",
        use_cache   = False,
    ))
    return {
        "success":       response.success,
        "provider":      response.provider,
        "model":         response.model,
        "content":       response.content,
        "input_tokens":  response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost_eur":      response.cost_eur,
        "duration_ms":   response.duration_ms,
        "error":         response.error,
    }
