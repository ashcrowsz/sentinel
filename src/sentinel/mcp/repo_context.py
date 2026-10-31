"""repo-context: an MCP server that lets any agent explore a checked-out repo.

Run it standalone and point Claude Code (or any MCP client) at it:

    python -m sentinel.mcp.repo_context --root ../sentinel-playground

Same tools the review agent uses, which is the whole point of MCP.
"""

from __future__ import annotations

import argparse

from fastmcp import FastMCP

from sentinel.mcp.repo_index import RepoIndex


def create_server(root: str) -> FastMCP:
    index = RepoIndex(root)
    mcp = FastMCP("repo-context")

    @mcp.tool()
    def search_code(pattern: str, limit: int = 30) -> str:
        """Regex search over Python files. Returns `path:line: text` per hit."""
        return "\n".join(h.render() for h in index.search_code(pattern, limit)) or "no matches"

    @mcp.tool()
    def read_file(path: str, start: int = 1, end: int | None = None) -> str:
        """Read a file (optionally a line range) with line numbers."""
        return index.read_file(path, start, end)

    @mcp.tool()
    def find_references(symbol: str) -> str:
        """Definitions first, then every reference to `symbol`."""
        defs = [f"DEF {h.render()}" for h in index.definitions(symbol)]
        refs = [h.render() for h in index.find_references(symbol)]
        return "\n".join(defs + refs) or "no references"

    @mcp.tool()
    def list_tests_for(path: str) -> str:
        """Test files that likely exercise `path`."""
        return "\n".join(index.list_tests_for(path)) or "no tests found"

    @mcp.resource("repo://tree")
    def tree() -> str:
        """Every indexed Python file."""
        return "\n".join(index.rel(p) for p in index.files())

    return mcp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--transport", default="stdio", choices=["stdio", "http"])
    args = ap.parse_args()
    server = create_server(args.root)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
