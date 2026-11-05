# changelog

### 2026-11-05 · GCP infra as code
`infra/terraform`
- terraform: vpc, firewall, artifact registry, k3s vm
- workload identity federation: no JSON keys in github

### 2026-11-03 · seeded-PR eval harness
`feat/eval-set`
- eval harness: replay cases, score recall and FP/PR
- seed cases: sqli, off-by-one, missing auth, clean refactor
- case: prompt injection hiding an infinite retry

### 2026-10-31 · repo-context MCP server
`feat/repo-context-mcp`
- repo index: search, definitions, references, tests-for
- expose the repo index as a FastMCP server

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
