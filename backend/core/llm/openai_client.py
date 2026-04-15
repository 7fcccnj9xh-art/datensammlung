"""OpenAI-Client: GPT-4o / GPT-4o-mini Integration."""

from __future__ import annotations

import logging

import tiktoken
from openai import AsyncOpenAI

from core.llm.llm_router import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

OPENAI_COSTS: dict[str, dict[str, float]] = {
    "gpt-4o":        {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15,  "output": 0.60},
}


class OpenAIClient:
    def __init__(self, api_key: str, default_model: str) -> None:
        self.client        = AsyncOpenAI(api_key=api_key)
        self.default_model = default_model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.default_model

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        content       = response.choices[0].message.content or ""
        input_tokens  = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        costs         = OPENAI_COSTS.get(model, {"input": 1.0, "output": 4.0})
        cost          = (input_tokens / 1_000_000 * costs["input"] +
                         output_tokens / 1_000_000 * costs["output"])

        return LLMResponse(
            content=content,
            provider="openai",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost,
        )
