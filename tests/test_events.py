from sentinel.events import RepairJob, ReviewJob, route_event


def pr_payload(action: str = "opened", ref: str = "feature/x", draft: bool = False) -> dict:
    return {
        "action": action,
        "installation": {"id": 42},
        "repository": {"full_name": "me/playground"},
        "pull_request": {"number": 7, "draft": draft, "head": {"sha": "abc123", "ref": ref}},
    }


def test_opened_pr_becomes_review_job() -> None:
    job = route_event("pull_request", pr_payload())
    assert isinstance(job, ReviewJob)
    assert (job.repo, job.pr_number, job.head_sha) == ("me/playground", 7, "abc123")


def test_closed_and_draft_prs_are_ignored() -> None:
    assert route_event("pull_request", pr_payload(action="closed")) is None
    assert route_event("pull_request", pr_payload(draft=True)) is None


def test_own_fix_branches_are_never_reviewed() -> None:
    assert route_event("pull_request", pr_payload(ref="sentinel/fix-123")) is None


def test_failed_pr_workflow_becomes_repair_job() -> None:
    payload = {
        "action": "completed",
        "installation": {"id": 42},
        "repository": {"full_name": "me/playground"},
        "workflow_run": {
            "id": 99,
            "conclusion": "failure",
            "head_branch": "feature/x",
            "head_sha": "abc123",
            "pull_requests": [{"number": 7}],
        },
    }
    job = route_event("workflow_run", payload)
    assert isinstance(job, RepairJob) and job.run_id == 99


def test_failures_on_main_are_not_repaired() -> None:
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 1,
            "conclusion": "failure",
            "head_branch": "main",
            "head_sha": "x",
            "pull_requests": [],
        },
    }
    assert route_event("workflow_run", payload) is None


def test_unknown_event_is_ignored() -> None:
    assert route_event("star", {}) is None
