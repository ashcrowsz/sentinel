"""Precision controls. A noisy reviewer gets muted, and then it catches nothing."""

from __future__ import annotations

from sentinel.review.diff import FileDiff
from sentinel.review.schema import Finding, Severity

SEVERITY_RANK = {Severity.critical: 0, Severity.high: 1, Severity.medium: 2, Severity.low: 3}

STYLE_WORDS = ("naming", "rename", "formatting", "whitespace", "docstring", "typo", "pep8", "style")


def is_style_nit(f: Finding) -> bool:
    text = f.comment.lower()
    return f.severity == Severity.low and any(w in text for w in STYLE_WORDS)


def filter_findings(
    findings: list[Finding],
    diff: dict[str, FileDiff],
    *,
    min_confidence: float,
    max_comments: int,
) -> list[Finding]:
    kept: list[Finding] = []
    seen: set[tuple[str, int]] = set()
    for f in findings:
        if f.confidence < min_confidence:
            continue
        if is_style_nit(f):
            continue  # the linter's job, not ours
        fd = diff.get(f.file)
        if fd is None or f.line not in fd.added_lines:
            continue  # hallucinated location, or outside the PR
        key = (f.file, f.line)
        if key in seen:
            continue
        seen.add(key)
        kept.append(f)
    kept.sort(key=lambda f: (SEVERITY_RANK[f.severity], -f.confidence))
    return kept[:max_comments]
