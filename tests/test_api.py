import json

from fastapi.testclient import TestClient

from sentinel.api import app, get_queue
from sentinel.config import Settings, get_settings
from sentinel.queue import InMemoryQueue
from sentinel.security import compute_signature

SECRET = "test-secret"
queue = InMemoryQueue()
app.dependency_overrides[get_settings] = lambda: Settings(github_webhook_secret=SECRET)
app.dependency_overrides[get_queue] = lambda: queue
client = TestClient(app)


def post(event: str, payload: dict, secret: str = SECRET):
    body = json.dumps(payload).encode()
    return client.post(
        "/webhook",
        content=body,
        headers={"X-GitHub-Event": event, "X-Hub-Signature-256": compute_signature(secret, body)},
    )


def test_healthz() -> None:
    assert client.get("/healthz").json()["status"] == "ok"


def test_bad_signature_is_rejected() -> None:
    assert post("pull_request", {}, secret="wrong").status_code == 401


def test_pr_is_queued_and_answered_with_202() -> None:
    payload = {
        "action": "opened",
        "installation": {"id": 1},
        "repository": {"full_name": "me/r"},
        "pull_request": {"number": 3, "draft": False, "head": {"sha": "s", "ref": "f"}},
    }
    r = post("pull_request", payload)
    assert r.status_code == 202 and r.json()["status"] == "queued"
    assert queue.jobs[-1].pr_number == 3


def test_irrelevant_event_is_ignored() -> None:
    r = post("issues", {"action": "opened"})
    assert r.status_code == 202 and r.json()["status"] == "ignored"
