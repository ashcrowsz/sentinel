"""Anti-cheat checks on a proposed patch.

The cheapest way to make tests pass is to delete them. We reject any patch
that removes or skips tests, or touches CI config.
"""

from __future__ import annotations

import re

from sentinel.review.diff import looks_like_test

PROTECTED_PREFIXES = (
    ".github/",
    "pyproject.toml",
    "setup.cfg",
    "pytest.ini",
    "tox.ini",
    "conftest.py",
)
SKIP_MARKERS = re.compile(r"(@pytest\.mark\.(skip|xfail)|pytest\.skip\(|unittest\.skip)")
DELETED_FILE = re.compile(r"^deleted file mode", re.M)


def touched_paths(patch: str) -> list[str]:
    return [ln[6:] for ln in patch.splitlines() if ln.startswith("+++ b/")] + [
        ln[6:] for ln in patch.splitlines() if ln.startswith("--- a/")
    ]


def patch_violations(patch: str) -> list[str]:
    problems: list[str] = []
    paths = set(touched_paths(patch))
    for p in sorted(paths):
        if p.startswith(PROTECTED_PREFIXES) or p.endswith("conftest.py"):
            problems.append(f"touches protected file {p}")

    removed_asserts = 0
    for ln in patch.splitlines():
        if ln.startswith("+") and SKIP_MARKERS.search(ln):
            problems.append("adds a skip/xfail marker")
        if ln.startswith("-") and not ln.startswith("---") and re.search(r"\bassert\b", ln):
            removed_asserts += 1
    if removed_asserts:
        problems.append(f"removes {removed_asserts} assert line(s)")

    if DELETED_FILE.search(patch) and any(looks_like_test(p) for p in paths):
        problems.append("deletes a test file")
    return problems
