"""Minimal GitHub App client: app JWT -> installation token -> REST calls."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
import jwt

from sentinel.review.schema import Finding


class GitHubApp:
    def __init__(self, app_id: int, private_key_path: str, api_url: str) -> None:
        self.app_id = app_id
        self.private_key = Path(private_key_path).read_text() if app_id else ""
        self.api_url = api_url
        self._tokens: dict[int, tuple[str, float]] = {}

    def app_jwt(self) -> str:
        now = int(time.time())
        # backdate iat 60s to tolerate clock drift, GitHub caps exp at 10 min
        payload = {"iat": now - 60, "exp": now + 540, "iss": str(self.app_id)}
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def installation_token(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        if cached and cached[1] - time.time() > 300:
            return cached[0]
        async with httpx.AsyncClient(base_url=self.api_url) as client:
            r = await client.post(
                f"/app/installations/{installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {self.app_jwt()}"},
            )
            r.raise_for_status()
            token = r.json()["token"]
        self._tokens[installation_id] = (token, time.time() + 3600)
        return token

    async def client(self, installation_id: int) -> httpx.AsyncClient:
        token = await self.installation_token(installation_id)
        return httpx.AsyncClient(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )


async def get_pr_diff(gh: httpx.AsyncClient, repo: str, number: int) -> str:
    r = await gh.get(
        f"/repos/{repo}/pulls/{number}", headers={"Accept": "application/vnd.github.diff"}
    )
    r.raise_for_status()
    return r.text


async def post_review(
    gh: httpx.AsyncClient, repo: str, number: int, sha: str, summary: str, findings: list[Finding]
) -> dict[str, Any]:
    body = {
        "commit_id": sha,
        "event": "COMMENT",  # never APPROVE or REQUEST_CHANGES: humans own the verdict
        "body": summary,
        "comments": [f.to_github_comment() for f in findings],
    }
    r = await gh.post(f"/repos/{repo}/pulls/{number}/reviews", json=body)
    r.raise_for_status()
    return r.json()


async def get_failed_job_logs(gh: httpx.AsyncClient, repo: str, run_id: int) -> str:
    jobs = (await gh.get(f"/repos/{repo}/actions/runs/{run_id}/jobs")).json()["jobs"]
    chunks: list[str] = []
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        r = await gh.get(f"/repos/{repo}/actions/jobs/{job['id']}/logs", follow_redirects=True)
        chunks.append(f"### {job['name']}\n{r.text[-12_000:]}")
    return "\n\n".join(chunks)
