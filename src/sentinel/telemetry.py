from __future__ import annotations

from prometheus_client import Counter, Histogram

REVIEW_SECONDS = Histogram(
    "sentinel_review_duration_seconds", "Wall time per review",
    buckets=(5, 15, 30, 60, 120, 300),
)
REVIEW_COMMENTS = Histogram(
    "sentinel_review_comments", "Comments posted per review", buckets=(0, 1, 2, 4, 8, 16)
)
LLM_COST = Counter("sentinel_llm_cost_usd_total", "LLM spend", ["job_kind"])
REPAIR_OUTCOME = Counter("sentinel_repair_outcome_total", "Repair loop outcomes", ["outcome"])


def setup_tracing(service_name: str) -> None:
    """OTLP exporter is configured via OTEL_* env vars in the Helm chart."""
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider

    trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": service_name})))
