"""Pure-Python repo index used by the repo-context MCP server.

Kept separate from the server so it is trivially testable and usable without MCP.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", "dist", "build"}
MAX_FILE_BYTES = 200_000


@dataclass
class Hit:
    path: str
    line: int
    text: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.text.strip()}"


class RepoIndex:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _safe(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"path escapes repository: {rel}")
        return p

    def files(self, suffix: str = ".py") -> list[Path]:
        out: list[Path] = []
        for p in self.root.rglob(f"*{suffix}"):
            if any(part in IGNORED_DIRS for part in p.relative_to(self.root).parts):
                continue
            if p.stat().st_size <= MAX_FILE_BYTES:
                out.append(p)
        return sorted(out)

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def read_file(self, path: str, start: int = 1, end: int | None = None) -> str:
        lines = self._safe(path).read_text(encoding="utf-8", errors="replace").splitlines()
        end = end or len(lines)
        return "\n".join(f"{i:>5}  {ln}" for i, ln in enumerate(lines[start - 1 : end], start))

    def search_code(self, pattern: str, limit: int = 30) -> list[Hit]:
        rx = re.compile(pattern)
        hits: list[Hit] = []
        for p in self.files():
            for i, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(ln):
                    hits.append(Hit(self.rel(p), i, ln))
                    if len(hits) >= limit:
                        return hits
        return hits

    def definitions(self, symbol: str) -> list[Hit]:
        hits: list[Hit] = []
        for p in self.files():
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == symbol:
                        hits.append(Hit(self.rel(p), node.lineno, f"def/class {node.name}"))
        return hits

    def find_references(self, symbol: str, limit: int = 50) -> list[Hit]:
        return self.search_code(rf"\b{re.escape(symbol)}\b", limit=limit)

    def list_tests_for(self, path: str) -> list[str]:
        """Heuristic: tests named after the module, or tests importing it."""
        module = Path(path).stem
        dotted = path.removesuffix(".py").replace("/", ".").removeprefix("src.")
        found: set[str] = set()
        for p in self.files():
            rel = self.rel(p)
            name = p.name
            if not (name.startswith("test_") or name.endswith("_test.py")):
                continue
            if module in name:
                found.add(rel)
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if dotted in text or re.search(rf"\bimport {re.escape(module)}\b", text):
                found.add(rel)
        return sorted(found)
