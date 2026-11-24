"""Review agent as a small LangGraph: parse -> gather context -> review -> filter.

The graph is deliberately boring. The interesting parts are what the model is
allowed to see (MCP tools) and what we let through (filters).
"""

from __future__ import annotations

import time
from typing import Any, Protocol, TypedDict

from sentinel.config import Settings
from sentinel.llm import LLM
from sentinel.review.diff import FileDiff, parse_unified_diff, render_for_prompt
from sentinel.review.filters import filter_findings
from sentinel.review.prompts import REVIEW_SYSTEM, review_user_prompt
from sentinel.review.schema import REVIEW_JSON_SCHEMA, Finding, ReviewOutput
from sentinel.telemetry import LLM_COST, REVIEW_COMMENTS, REVIEW_SECONDS
from sentinel.tracing import drop, traceable


class ReviewState(TypedDict, total=False):
    title: str
    body: str
    raw_diff: str
    files: dict[str, FileDiff]
    context: str
    output: ReviewOutput
    findings: list[Finding]
    cost_usd: float


class ContextProvider(Protocol):
    """Anything that can answer repo questions. In prod: the repo-context MCP server."""

    async def gather(self, files: dict[str, FileDiff]) -> str: ...


def build_graph(llm: LLM, ctx: ContextProvider, settings: Settings) -> Any:
    from langgraph.graph import END, StateGraph

    async def parse(state: ReviewState) -> ReviewState:
        return {"files": parse_unified_diff(state["raw_diff"])}

    async def gather(state: ReviewState) -> ReviewState:
        return {"context": await ctx.gather(state["files"])}

    async def review(state: ReviewState) -> ReviewState:
        user = review_user_prompt(
            state.get("title", ""),
            state.get("body", ""),
            render_for_prompt(state["files"]),
            state.get("context", ""),
        )
        data, res = await llm.complete_json(REVIEW_SYSTEM, user, REVIEW_JSON_SCHEMA)
        LLM_COST.labels("review").inc(res.cost_usd)
        return {"output": ReviewOutput.model_validate(data), "cost_usd": res.cost_usd}

    async def filt(state: ReviewState) -> ReviewState:
        kept = filter_findings(
            state["output"].findings,
            state["files"],
            min_confidence=settings.sentinel_min_confidence,
            max_comments=settings.sentinel_max_comments,
        )
        return {"findings": kept}

    g = StateGraph(ReviewState)
    g.add_node("parse", parse)
    g.add_node("gather", gather)
    g.add_node("review", review)
    g.add_node("filter", filt)
    g.set_entry_point("parse")
    g.add_edge("parse", "gather")
    g.add_edge("gather", "review")
    g.add_edge("review", "filter")
    g.add_edge("filter", END)
    return g.compile()


@traceable(run_type="chain", name="review_pr", process_inputs=drop("graph"))
async def run_review(graph: Any, title: str, body: str, diff: str) -> ReviewState:
    """Root span of a review trace. Callers add repo / PR / SHA via langsmith_extra."""
    started = time.perf_counter()
    state: ReviewState = await graph.ainvoke({"title": title, "body": body, "raw_diff": diff})
    REVIEW_SECONDS.observe(time.perf_counter() - started)
    REVIEW_COMMENTS.observe(len(state.get("findings", [])))
    return state
