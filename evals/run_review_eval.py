"""Replay seeded PRs against the review agent and score it.

Each case is a YAML file: a diff plus the bugs we planted (or none, for clean PRs).
A finding "catches" a planted bug if it lands within +/-2 lines of it in the same file.

    python -m evals.run_review_eval --cases evals/cases --out evals/results [--gate]

--gate exits non-zero if recall or false positives regress past the thresholds,
which is how a prompt change gets the same quality bar as a code change.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from sentinel.config import get_settings
from sentinel.llm import LLM
from sentinel.review.agent import build_graph, run_review
from sentinel.review.diff import FileDiff

MIN_RECALL = 0.70
MAX_FP_PER_PR = 0.5
LINE_TOLERANCE = 2


@dataclass
class CaseResult:
    name: str
    planted: int
    caught: int
    false_positives: int
    cost_usd: float
    seconds: float


class NoContext:
    async def gather(self, files: dict[str, FileDiff]) -> str:
        return ""


def score(planted: list[dict], findings: list) -> tuple[int, int]:
    caught, matched = 0, set()
    for bug in planted:
        for i, f in enumerate(findings):
            if i not in matched and f.file == bug["file"] and abs(f.line - bug["line"]) <= LINE_TOLERANCE:
                caught += 1
                matched.add(i)
                break
    return caught, len(findings) - len(matched)


async def run(cases_dir: Path) -> list[CaseResult]:
    s = get_settings()
    graph = build_graph(LLM(s.litellm_base_url, s.litellm_api_key, s.sentinel_model), NoContext(), s)
    results: list[CaseResult] = []
    for path in sorted(cases_dir.glob("*.yaml")):
        case = yaml.safe_load(path.read_text())
        t0 = time.perf_counter()
        state = await run_review(graph, case["title"], case.get("body", ""), case["diff"])
        caught, fps = score(case.get("planted", []), state.get("findings", []))
        results.append(CaseResult(path.stem, len(case.get("planted", [])), caught, fps,
                                  state.get("cost_usd", 0.0), time.perf_counter() - t0))
        print(f"{path.stem:<32} caught {caught}/{len(case.get('planted', []))}  fp {fps}")
    return results


def summarize(results: list[CaseResult]) -> dict[str, float]:
    planted = sum(r.planted for r in results)
    return {
        "cases": len(results),
        "recall": sum(r.caught for r in results) / planted if planted else 1.0,
        "fp_per_pr": sum(r.false_positives for r in results) / max(len(results), 1),
        "cost_usd_total": sum(r.cost_usd for r in results),
        "p50_seconds": sorted(r.seconds for r in results)[len(results) // 2] if results else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=Path("evals/cases"))
    ap.add_argument("--out", type=Path, default=Path("evals/results"))
    ap.add_argument("--gate", action="store_true")
    args = ap.parse_args()

    results = asyncio.run(run(args.cases))
    summary = summarize(results)
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (args.out / f"{stamp}.json").write_text(
        json.dumps({"summary": summary, "cases": [asdict(r) for r in results]}, indent=2)
    )
    print(json.dumps(summary, indent=2))
    if args.gate and (summary["recall"] < MIN_RECALL or summary["fp_per_pr"] > MAX_FP_PER_PR):
        print("eval gate FAILED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
