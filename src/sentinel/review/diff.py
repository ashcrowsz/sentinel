"""Unified-diff parsing. We only allow comments on lines the PR actually added."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass
class FileDiff:
    path: str
    added_lines: dict[int, str] = field(default_factory=dict)
    is_test: bool = False
    # hunk lines in order, for the prompt: numbered '+' lines, unnumbered '-' lines
    shown: list[str] = field(default_factory=list)


def parse_unified_diff(diff: str) -> dict[str, FileDiff]:
    files: dict[str, FileDiff] = {}
    current: FileDiff | None = None
    new_line = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path == "/dev/null":
                current = None
                continue
            path = path[2:] if path.startswith("b/") else path
            current = FileDiff(path=path, is_test=looks_like_test(path))
            files[path] = current
            continue
        if raw.startswith(("--- ", "diff --git", "index ", "new file", "deleted file")):
            continue
        m = HUNK.match(raw)
        if m:
            new_line = int(m.group(1))
            continue
        if current is None:
            continue
        if raw.startswith("+"):
            current.added_lines[new_line] = raw[1:]
            current.shown.append(f"{new_line:>5} + {raw[1:]}")
            new_line += 1
        elif raw.startswith("-"):
            current.shown.append(f"{'':>5} - {raw[1:]}")  # removed: context only
        elif raw.startswith("\\"):
            continue
        else:
            new_line += 1
    return files


def looks_like_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return "/tests/" in f"/{path}" or name.startswith("test_") or name.endswith("_test.py")


def render_for_prompt(files: dict[str, FileDiff], max_chars: int = 60_000) -> str:
    out: list[str] = []
    for f in files.values():
        out.append(f"### {f.path}")
        out.extend(f.shown)
    text = "\n".join(out)
    return text if len(text) <= max_chars else text[:max_chars] + "\n...[diff truncated]"
