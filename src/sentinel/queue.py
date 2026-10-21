from __future__ import annotations

from typing import Protocol

from sentinel.events import Job


class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> str: ...


class ArqQueue:
    """Thin wrapper so the API never imports arq directly (easy to fake in tests)."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool = None

    async def _get_pool(self):  # type: ignore[no-untyped-def]
        if self._pool is None:
            from arq import create_pool
            from arq.connections import RedisSettings

            self._pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        return self._pool

    async def enqueue(self, job: Job) -> str:
        pool = await self._get_pool()
        # job id = idempotency key: GitHub redelivers, we don't double-review
        key = f"{job.kind}:{job.repo}:{getattr(job, 'pr_number', getattr(job, 'run_id', ''))}:{job.head_sha}"
        await pool.enqueue_job(f"run_{job.kind}", job.model_dump(), _job_id=key)
        return key


class InMemoryQueue:
    def __init__(self) -> None:
        self.jobs: list[Job] = []

    async def enqueue(self, job: Job) -> str:
        self.jobs.append(job)
        return f"mem-{len(self.jobs)}"
