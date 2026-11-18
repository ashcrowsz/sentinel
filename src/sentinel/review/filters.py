"""Precision controls. A noisy reviewer gets muted, and then it catches nothing."""

from __future__ import annotations

import ast
import textwrap
from difflib import SequenceMatcher

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
        kept.append(fit_suggestion(f, fd))
    kept.sort(key=lambda f: (SEVERITY_RANK[f.severity], -f.confidence))
    return kept[:max_comments]


def _parses(code: str) -> bool:
    """True if a Python fragment is valid on its own (a trailing block header is fine)."""
    candidates = [code]
    if code.rstrip().endswith(":"):
        candidates.append(code + "\n    pass")
    for c in candidates:
        try:
            ast.parse(c)
            return True
        except SyntaxError:
            continue
    return False


def _inferred_end(line: int, new_lines: list[str], fd: FileDiff) -> int | None:
    """A k-line suggestion with no end_line: accept it only if it is plainly a rewrite
    of the k added lines starting at `line` (each line still resembles its original)."""
    for i, new in enumerate(new_lines):
        old = fd.added_lines.get(line + i)
        if old is None:
            return None
        if SequenceMatcher(None, old.strip(), new.strip()).ratio() < 0.5:
            return None
    return line + len(new_lines) - 1


def _indent(s: str) -> str:
    return s[: len(s) - len(s.lstrip())]


def fit_suggestion(f: Finding, fd: FileDiff) -> Finding:
    """Make a suggestion safe to apply in one click, or drop it (the comment stays).

    - the replaced range must be lines this PR added, back to back
    - a multi-line suggestion with no end_line is ambiguous (applied to one line it
      leaves the old code below it in place): keep it only if the range is obvious
    - indentation is re-based on the original first line: models often drop it
    """
    if not f.suggestion:
        return f
    new_lines = f.suggestion.strip("\n").splitlines()
    end = f.end_line or f.line
    if f.end_line is None and len(new_lines) > 1:
        end = _inferred_end(f.line, new_lines, fd)
    rng = range(f.line, end + 1) if end else range(0)
    ok = bool(end) and end >= f.line and all(n in fd.added_lines for n in rng)
    if not ok:
        return f.model_copy(update={"suggestion": None, "end_line": None})
    want = _indent(fd.added_lines[f.line])
    body = textwrap.dedent("\n".join(new_lines))
    if f.file.endswith(".py") and not _parses(body):
        # prose ("use parameterized queries…") or broken code: never one-click it
        return f.model_copy(update={"suggestion": None, "end_line": None})
    fixed = "\n".join(want + ln.rstrip() if ln.strip() else "" for ln in body.splitlines())
    return f.model_copy(update={"suggestion": fixed, "end_line": end if end > f.line else None})
