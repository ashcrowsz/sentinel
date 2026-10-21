# changelog

### 2026-10-21 · webhook endpoint with signature verification
`feat/webhook-edge`
- config via pydantic-settings
- verify webhook signatures (HMAC-SHA256, constant-time)
- route pull_request / workflow_run events to jobs
- api: verify, route, enqueue, answer 202
