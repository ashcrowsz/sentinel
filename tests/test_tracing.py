"""LangSmith tracing: one trace per review, the model call inside it, no secrets in it.

No network: LiteLLM is mocked with respx and the LangSmith client is a mock that records
the runs it would have sent.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from langsmith import Client, tracing_context

from sentinel.config import Settings
from sentinel.llm import LLM
from sentinel.review.agent import build_graph, run_review
from sentinel.review.diff import FileDiff

DIFF = """diff --git a/app/users.py b/app/users.py
--- a/app/users.py
+++ b/app/users.py
@@ -10,3 +10,4 @@ def get_user(db, user_id):
     conn = db.connect()
-    q = "SELECT * FROM users WHERE id = %s"
+    q = f"SELECT * FROM users WHERE id = {user_id}"
+    rows = conn.execute(q)
     return rows
"""

REPLY = {
    "summary": "SQL injection.",
    "findings": [
        {
            "file": "app/users.py",
            "line": 11,
            "severity": "high",
            "category": "security",
            "comment": "user_id is formatted straight into the SQL string.",
            "confidence": 0.9,
        }
    ],
}


class NoContext:
    async def gather(self, files: dict[str, FileDiff]) -> str:
        return ""


def review_once() -> dict[str, Any]:
    llm = LLM("http://litellm.test", "sk-secret-master-key", "reviewer")
    graph = build_graph(llm, NoContext(), Settings())
    with respx.mock:
        respx.post("http://litellm.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": json.dumps(REPLY)}}],
                    "usage": {"prompt_tokens": 900, "completion_tokens": 80},
                },
                headers={"x-litellm-response-cost": "0"},
            )
        )
        return asyncio.run(run_review(graph, "Add user lookup", "", DIFF))  # type: ignore[return-value]


def test_review_works_with_tracing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    state = review_once()
    assert [f.line for f in state["findings"]] == [11]


def test_one_trace_per_review_with_the_model_call_inside(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    client = MagicMock(spec=Client)
    monkeypatch.setattr("langsmith.run_trees.get_cached_client", lambda **_: client)
    with tracing_context(enabled=True, client=client):
        state = review_once()
    assert [f.line for f in state["findings"]] == [11]

    runs = [c.kwargs for c in client.create_run.call_args_list]
    names = [r["name"] for r in runs]
    for expected in ("review_pr", "parse", "gather", "review", "filter", "chat_completion"):
        assert expected in names, names
    assert len({r["trace_id"] for r in runs}) == 1  # all of it is one trace

    llm_run = next(r for r in runs if r["name"] == "chat_completion")
    assert llm_run["run_type"] == "llm"
    assert "sk-secret-master-key" not in json.dumps(llm_run["inputs"], default=str)
