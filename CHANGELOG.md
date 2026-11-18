# changelog

### 2026-11-18 · one-click suggestions you can actually click
`fix/suggestion-ranges`
- multi-line suggestions: comments span the replaced range (`start_line`..`line`)
- the range is inferred when the model omits `end_line` but the rewrite is obvious
- indentation re-based on the original line; prose or code that doesn't parse is dropped (the comment stays)
- prompt shows removed lines, so suggestions can follow the code's existing conventions

### 2026-11-14 · release pipeline gated on evals
`release/eval-gate`
- release: eval gate -> publish via WIF -> bump gitops tag

### 2026-11-13 · CI repair loop with sandboxed tests
`feat/repair-loop`
- repair budget + noise-tolerant failure fingerprints
- guard: reject patches that skip, weaken or delete tests
- sandbox job: non-root, no egress, cpu/mem/time limits
- repair graph with a retry back-edge

### 2026-11-08 · helm chart + gitops
`deploy/helm-argocd`
- helm chart: api + worker, hardened pods, probes
- secrets from GCP secret manager via external-secrets
- argo cd application + litellm budget config

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
