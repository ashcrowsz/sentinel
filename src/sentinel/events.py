"""Turn raw GitHub webhook payloads into the jobs Sentinel actually cares about."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


class ReviewJob(BaseModel):
    kind: Literal["review"] = "review"
    installation_id: int
    repo: str
    pr_number: int
    head_sha: str


class RepairJob(BaseModel):
    kind: Literal["repair"] = "repair"
    installation_id: int
    repo: str
    run_id: int
    head_branch: str
    head_sha: str


Job = ReviewJob | RepairJob


def route_event(event: str, payload: dict[str, Any]) -> Job | None:
    """Return a job for events we handle, ``None`` for everything else."""
    installation_id = int(payload.get("installation", {}).get("id", 0))
    repo = payload.get("repository", {}).get("full_name", "")

    if event == "pull_request":
        pr = payload.get("pull_request", {})
        if payload.get("action") not in REVIEWABLE_ACTIONS or pr.get("draft"):
            return None
        # never review our own fix PRs, that way lies infinite loops
        if pr.get("head", {}).get("ref", "").startswith("sentinel/fix-"):
            return None
        return ReviewJob(
            installation_id=installation_id,
            repo=repo,
            pr_number=int(pr["number"]),
            head_sha=pr["head"]["sha"],
        )

    if event == "workflow_run":
        run = payload.get("workflow_run", {})
        if payload.get("action") != "completed" or run.get("conclusion") != "failure":
            return None
        if not run.get("pull_requests"):
            return None  # only repair PR builds, never main
        return RepairJob(
            installation_id=installation_id,
            repo=repo,
            run_id=int(run["id"]),
            head_branch=run["head_branch"],
            head_sha=run["head_sha"],
        )

    return None
