"""arq worker: the slow half. Picks jobs off Redis and runs the agents."""

from __future__ import annotations

import logging
from typing import Any

from sentinel.config import get_settings
from sentinel.events import RepairJob, ReviewJob
from sentinel.github_client import GitHubApp, get_failed_job_logs, get_pr_diff, post_review
from sentinel.llm import LLM
from sentinel.repair.budget import RepairBudget
from sentinel.review.agent import build_graph, run_review
from sentinel.review.diff import FileDiff

log = logging.getLogger("sentinel.worker")


class DiffOnlyContext:  # TODO(#4): replace with the repo-context MCP client
    """Fallback context provider when the repo-context MCP server is not reachable."""

    async def gather(self, files: dict[str, FileDiff]) -> str:
        return "Files touched: " + ", ".join(files)


async def startup(ctx: dict[str, Any]) -> None:
    s = get_settings()
    ctx["settings"] = s
    ctx["gh"] = GitHubApp(s.github_app_id, s.github_private_key_path, s.github_api_url)
    ctx["llm"] = LLM(
        s.litellm_base_url, s.litellm_api_key, s.sentinel_model, s.sentinel_reasoning_effort
    )
    ctx["review_graph"] = build_graph(ctx["llm"], DiffOnlyContext(), s)


async def run_review_job(ctx: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    job = ReviewJob.model_validate(raw)
    async with await ctx["gh"].client(job.installation_id) as gh:
        pr = (await gh.get(f"/repos/{job.repo}/pulls/{job.pr_number}")).json()
        diff = await get_pr_diff(gh, job.repo, job.pr_number)
        state = await run_review(
            ctx["review_graph"],
            pr["title"],
            pr.get("body") or "",
            diff,
            langsmith_extra={
                "tags": ["review"],
                "metadata": {"repo": job.repo, "pr": job.pr_number, "sha": job.head_sha},
            },
        )
        findings = state.get("findings", [])
        summary = (
            state["output"].summary
            if findings
            else "Sentinel looked, found nothing worth flagging. ✅"
        )
        await post_review(gh, job.repo, job.pr_number, job.head_sha, summary, findings)
    log.info("reviewed %s#%s: %d comments", job.repo, job.pr_number, len(findings))
    return {"comments": len(findings), "cost_usd": state.get("cost_usd", 0.0)}


async def run_repair_job(ctx: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    job = RepairJob.model_validate(raw)
    s = ctx["settings"]
    budget = RepairBudget(
        max_iterations=s.sentinel_max_iterations, max_cost_usd=s.sentinel_max_cost_usd
    )
    async with await ctx["gh"].client(job.installation_id) as gh:
        failure = await get_failed_job_logs(gh, job.repo, job.run_id)
    # TODO(#1): wire KubernetesSandbox (needs in-cluster credentials) into build_repair_graph.
    log.info(
        "repair requested for %s run %s (%d bytes of logs)", job.repo, job.run_id, len(failure)
    )
    return {"status": "awaiting_sandbox", "budget_usd": budget.max_cost_usd}


def _redis_settings() -> Any:
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    # arq reads these as plain attributes, not methods
    functions = [run_review_job, run_repair_job]
    on_startup = startup
    max_jobs = 4
    job_timeout = 900
    redis_settings = _redis_settings()
