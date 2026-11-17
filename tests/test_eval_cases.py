"""Eval cases must stay valid: planted bugs point at lines the diff actually adds."""

from pathlib import Path

import pytest
import yaml

from sentinel.review.diff import parse_unified_diff
from sentinel.review.schema import Finding

CASES = sorted((Path(__file__).parent.parent / "evals" / "cases").glob("*.yaml"))


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_planted_bugs_are_on_added_lines(path: Path) -> None:
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    files = parse_unified_diff(case["diff"])
    for bug in case["planted"]:
        assert bug["line"] in files[bug["file"]].added_lines, bug


def test_scoring_matches_within_tolerance() -> None:
    from evals.run_review_eval import score

    f = Finding(
        file="a.py",
        line=12,
        severity="high",
        category="bug",
        comment="this loops forever on error",
        confidence=0.9,
    )
    extra = f.model_copy(update={"file": "b.py"})
    assert score([{"file": "a.py", "line": 10}], [f, extra]) == (1, 1)
    assert score([{"file": "a.py", "line": 30}], [f]) == (0, 1)
