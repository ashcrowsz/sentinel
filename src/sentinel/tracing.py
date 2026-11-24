"""Optional LangSmith tracing. Off unless LANGSMITH_TRACING=true (plus LANGSMITH_API_KEY).

When on, every review is one trace: review_pr -> the LangGraph nodes (LangGraph reports
them itself) -> the model call with its prompt, JSON reply and token counts. The eval
attaches its score to each case's trace as feedback, so a bad prompt change shows up
in LangSmith next to the exact review that got worse.
"""

from __future__ import annotations

import os
from typing import Any

from langsmith import traceable

__all__ = ["drop", "enabled", "traceable"]


def enabled() -> bool:
    flag = os.environ.get("LANGSMITH_TRACING") or os.environ.get("LANGCHAIN_TRACING_V2", "")
    return flag.strip().lower() == "true"


def drop(*names: str) -> Any:
    """process_inputs hook: keep secrets and big objects out of a span's inputs."""

    def _drop(inputs: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in inputs.items() if k not in names}

    return _drop
