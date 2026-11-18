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


def parse_json(text: str) -> Any:
    """Local models sometimes wrap JSON in ``` fences or add a preamble."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    start, end = t.find("{"), t.rfind("}")
    if start > 0 and end > start:
        t = t[start : end + 1]
    return json.loads(t)


class LLM:
    def __init__(self, base_url: str, api_key: str, model: str, reasoning_effort: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        # e.g. "none" for local reasoning models (gemma 4, qwen 3) to skip thinking tokens
        self.reasoning_effort = reasoning_effort

    async def complete(
        self, system: str, user: str, *, json_schema: dict[str, Any] | None = None
    ) -> LLMResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": 4000,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": json_schema, "strict": True},
            }
        async with httpx.AsyncClient(timeout=300) as client:
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
        return parse_json(res.text), res
