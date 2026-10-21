"""HTTP edge: verify, route, enqueue, answer 202. Never run the agent here.

GitHub gives a webhook 10 seconds. A review takes a minute or more, so the
handler only validates and queues; the worker does the slow part.
"""

from __future__ import annotations

import json

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from sentinel import __version__
from sentinel.config import Settings, get_settings
from sentinel.events import route_event
from sentinel.queue import ArqQueue, JobQueue
from sentinel.security import verify_signature

WEBHOOKS = Counter("sentinel_webhooks_total", "Webhook deliveries", ["event", "outcome"])

app = FastAPI(title="Sentinel", version=__version__)
_queue: JobQueue | None = None


def get_queue(settings: Settings = Depends(get_settings)) -> JobQueue:
    global _queue
    if _queue is None:
        _queue = ArqQueue(settings.redis_url)
    return _queue


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook", status_code=202)
async def webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str | None = Header(None),
    settings: Settings = Depends(get_settings),
    queue: JobQueue = Depends(get_queue),
) -> dict[str, str]:
    body = await request.body()
    if not verify_signature(settings.github_webhook_secret, body, x_hub_signature_256):
        WEBHOOKS.labels(x_github_event, "bad_signature").inc()
        raise HTTPException(status_code=401, detail="invalid signature")

    job = route_event(x_github_event, json.loads(body))
    if job is None:
        WEBHOOKS.labels(x_github_event, "ignored").inc()
        return {"status": "ignored"}

    job_id = await queue.enqueue(job)
    WEBHOOKS.labels(x_github_event, "queued").inc()
    return {"status": "queued", "job_id": job_id}
