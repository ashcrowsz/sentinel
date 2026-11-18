from sentinel.review.diff import parse_unified_diff, render_for_prompt
from sentinel.review.filters import filter_findings
from sentinel.review.schema import Finding

DIFF = """diff --git a/app/users.py b/app/users.py
index 1111111..2222222 100644
--- a/app/users.py
+++ b/app/users.py
@@ -10,3 +10,5 @@ def get_user(db, user_id):
     conn = db.connect()
-    q = "SELECT * FROM users WHERE id = %s"
+    q = f"SELECT * FROM users WHERE id = {user_id}"
+    rows = conn.execute(q)
     return rows
diff --git a/tests/test_users.py b/tests/test_users.py
new file mode 100644
--- /dev/null
+++ b/tests/test_users.py
@@ -0,0 +1,2 @@
+def test_get_user():
+    assert True
"""


def finding(**kw) -> Finding:
    base = dict(
        file="app/users.py",
        line=11,
        severity="critical",
        category="security",
        comment="SQL injection: user_id is interpolated into the query.",
        confidence=0.9,
    )
    base.update(kw)
    return Finding(**base)


def test_parse_tracks_new_line_numbers() -> None:
    files = parse_unified_diff(DIFF)
    assert set(files) == {"app/users.py", "tests/test_users.py"}
    assert files["app/users.py"].added_lines == {
        11: '    q = f"SELECT * FROM users WHERE id = {user_id}"',
        12: "    rows = conn.execute(q)",
    }
    assert files["tests/test_users.py"].is_test
    assert "   11 + " in render_for_prompt(files)


def test_keeps_confident_finding_on_added_line() -> None:
    files = parse_unified_diff(DIFF)
    assert len(filter_findings([finding()], files, min_confidence=0.6, max_comments=5)) == 1


def test_drops_low_confidence_and_hallucinated_lines() -> None:
    files = parse_unified_diff(DIFF)
    out = filter_findings(
        [finding(confidence=0.3), finding(line=10), finding(file="nope.py")],
        files,
        min_confidence=0.6,
        max_comments=5,
    )
    assert out == []


def test_drops_style_nits() -> None:
    files = parse_unified_diff(DIFF)
    nit = finding(severity="low", category="bug", comment="Consider better naming for q here.")
    assert filter_findings([nit], files, min_confidence=0.0, max_comments=5) == []


def test_caps_and_sorts_by_severity() -> None:
    files = parse_unified_diff(DIFF)
    low = finding(
        line=12, severity="medium", confidence=0.95, comment="rows may be unbound on error."
    )
    crit = finding()
    out = filter_findings([low, crit], files, min_confidence=0.5, max_comments=1)
    assert out == [crit]


def test_github_comment_has_suggestion_block() -> None:
    c = finding(suggestion='    q = "SELECT * FROM users WHERE id = %s"').to_github_comment()
    assert c["path"] == "app/users.py" and c["line"] == 11 and "```suggestion" in c["body"]


def test_parse_json_tolerates_fences_and_preamble() -> None:
    from sentinel.llm import parse_json

    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go:\n{"a": {"b": 2}}') == {"a": {"b": 2}}


def fit(**kw) -> Finding:
    files = parse_unified_diff(DIFF)
    [out] = filter_findings([finding(**kw)], files, min_confidence=0.0, max_comments=5)
    return out


def test_multiline_suggestion_replaces_the_whole_range() -> None:
    # the live bug: a 2-line fix posted on line 11 only left the old line 12 behind
    out = fit(
        end_line=12,
        suggestion='q = "SELECT * FROM users WHERE id = %s"\nrows = conn.execute(q, (user_id,))',
    )
    c = out.to_github_comment()
    assert (c["start_line"], c["line"]) == (11, 12)
    assert c["start_side"] == c["side"] == "RIGHT"
    # indentation restored from the original line
    assert out.suggestion == (
        '    q = "SELECT * FROM users WHERE id = %s"\n    rows = conn.execute(q, (user_id,))'
    )


def test_multiline_suggestion_without_end_line_is_dropped_comment_kept() -> None:
    out = fit(suggestion="q = 1\nrows = conn.execute(q)")
    assert out.suggestion is None and "SQL injection" in out.comment
    assert "start_line" not in out.to_github_comment()


def test_suggestion_range_outside_the_pr_is_dropped() -> None:
    out = fit(end_line=13, suggestion="a\nb\nc")
    assert out.suggestion is None and out.end_line is None


def test_multiline_suggestion_without_end_line_inferred_when_obvious() -> None:
    # gemma never sets end_line: a 2-line rewrite of lines 11-12 is still unambiguous
    out = fit(
        suggestion='q = "SELECT * FROM users WHERE id = %s"\nrows = conn.execute(q, (user_id,))'
    )
    c = out.to_github_comment()
    assert (c["start_line"], c["line"]) == (11, 12)


def test_prompt_shows_removed_lines_unnumbered() -> None:
    text = render_for_prompt(parse_unified_diff(DIFF))
    assert '      -     q = "SELECT * FROM users WHERE id = %s"' in text
    assert text.index(" - ") < text.index("   11 + ")


def test_prose_suggestion_is_dropped_comment_kept() -> None:
    # the second live bug: advice in the suggestion block would replace the code with English
    out = fit(suggestion="Use parameterized queries instead of string formatting.")
    assert out.suggestion is None and "SQL injection" in out.comment


def test_block_header_suggestion_is_allowed() -> None:
    out = fit(suggestion="if user_id is None:")
    assert out.suggestion == "    if user_id is None:"


def test_single_line_suggestion_keeps_relative_indent() -> None:
    out = fit(suggestion='q = "SELECT * FROM users WHERE id = %s"')
    assert out.suggestion == '    q = "SELECT * FROM users WHERE id = %s"'
    assert out.to_github_comment()["line"] == 11
