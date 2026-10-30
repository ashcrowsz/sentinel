from pathlib import Path

import pytest

from sentinel.mcp.repo_index import RepoIndex


@pytest.fixture
def repo(tmp_path: Path) -> RepoIndex:
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "billing.py").write_text(
        "def charge(amount):\n    return amount * 100\n\nclass Invoice:\n    pass\n"
    )
    (tmp_path / "app" / "api.py").write_text("from app.billing import charge\n\ncharge(3)\n")
    (tmp_path / "tests" / "test_billing.py").write_text("from app.billing import charge\n")
    (tmp_path / "tests" / "test_other.py").write_text("import app.billing\n")
    return RepoIndex(tmp_path)


def test_search_and_read(repo: RepoIndex) -> None:
    hits = repo.search_code(r"def charge")
    assert [(h.path, h.line) for h in hits] == [("app/billing.py", 1)]
    assert "    2      return amount * 100" in repo.read_file("app/billing.py", 1, 2)


def test_definitions_and_references(repo: RepoIndex) -> None:
    assert [h.path for h in repo.definitions("Invoice")] == ["app/billing.py"]
    refs = {h.path for h in repo.find_references("charge")}
    assert refs == {"app/billing.py", "app/api.py", "tests/test_billing.py"}


def test_list_tests_for(repo: RepoIndex) -> None:
    assert repo.list_tests_for("app/billing.py") == ["tests/test_billing.py", "tests/test_other.py"]


def test_path_traversal_is_blocked(repo: RepoIndex) -> None:
    with pytest.raises(ValueError):
        repo.read_file("../../etc/passwd")
