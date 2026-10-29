# changelog

### 2026-10-29 · review agent with structured findings
`feat/review-agent`
- unified diff parser that tracks new-file line numbers
- Finding schema + github suggestion rendering
- precision filters: confidence floor, cap, no nits, added lines only
- review prompt: fence repo content as untrusted
- litellm client, metrics, review langgraph
- github app auth + post review from the arq worker

### 2026-10-22 · CI: lint, types, tests, image build + trivy
`ci/github-actions`
- ci workflow + multi-stage non-root Dockerfile

### 2026-10-21 · webhook endpoint with signature verification
`feat/webhook-edge`
- config via pydantic-settings
- verify webhook signatures (HMAC-SHA256, constant-time)
- route pull_request / workflow_run events to jobs
- api: verify, route, enqueue, answer 202
