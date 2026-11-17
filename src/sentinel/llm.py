"""All model traffic goes through the LiteLLM proxy (budgets, fallbacks, one cost view)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLM:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(
        self, system: str, user: str, *, json_schema: dict[str, Any] | None = None
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
        }
        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": json_schema, "strict": True},
            }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get("usage", {})
        cost = float(r.headers.get("x-litellm-response-cost", 0) or 0)
        return LLMResult(
            text=data["choices"][0]["message"]["content"],
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cost_usd=cost,
        )

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any]
    ) -> tuple[Any, LLMResult]:
        res = await self.complete(system, user, json_schema=schema)
        return json.loads(res.text), res
