from sentinel.repair.budget import RepairBudget, StopReason, failure_fingerprint
from sentinel.repair.guard import patch_violations
from sentinel.repair.sandbox import SandboxSpec, build_job_manifest, job_name

LOG_A = "FAILED tests/test_math.py::test_add - AssertionError: assert 3 == 4\n took 0.12s"
LOG_A_AGAIN = "FAILED tests/test_math.py::test_add - AssertionError: assert 3 == 4\n took 0.98s"
LOG_B = "FAILED tests/test_math.py::test_sub - AssertionError: assert 1 == 0"


def test_fingerprint_ignores_timing_noise() -> None:
    assert failure_fingerprint(LOG_A) == failure_fingerprint(LOG_A_AGAIN)
    assert failure_fingerprint(LOG_A) != failure_fingerprint(LOG_B)


def test_green_tests_stop_immediately() -> None:
    assert RepairBudget().should_stop(tests_passed=True) is StopReason.fixed


def test_same_failure_twice_means_no_progress() -> None:
    b = RepairBudget()
    b.record(cost_usd=0.01, failure_log=LOG_A)
    assert b.should_stop(tests_passed=False) is None
    b.record(cost_usd=0.01, failure_log=LOG_A_AGAIN)
    assert b.should_stop(tests_passed=False) is StopReason.no_progress


def test_budget_and_iteration_caps() -> None:
    b = RepairBudget(max_cost_usd=0.05)
    b.record(cost_usd=0.06, failure_log=LOG_A)
    assert b.should_stop(tests_passed=False) is StopReason.budget

    b = RepairBudget(max_iterations=2)
    b.record(cost_usd=0, failure_log=LOG_A)
    b.record(cost_usd=0, failure_log=LOG_B)
    assert b.should_stop(tests_passed=False) is StopReason.max_iterations


GOOD_PATCH = """--- a/app/math.py
+++ b/app/math.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

CHEAT_PATCH = """--- a/tests/test_math.py
+++ b/tests/test_math.py
@@ -1,3 +1,4 @@
+@pytest.mark.skip
 def test_add():
-    assert add(1, 2) == 3
+    pass
"""


def test_guard_accepts_real_fix() -> None:
    assert patch_violations(GOOD_PATCH) == []


def test_guard_rejects_skipping_and_weakening_tests() -> None:
    problems = patch_violations(CHEAT_PATCH)
    assert any("skip" in p for p in problems)
    assert any("assert" in p for p in problems)


def test_guard_rejects_ci_edits() -> None:
    patch = "--- a/.github/workflows/ci.yml\n+++ b/.github/workflows/ci.yml\n@@ -1 +1 @@\n-x\n+y\n"
    assert any("protected" in p for p in patch_violations(patch))


def test_sandbox_job_is_locked_down() -> None:
    spec = SandboxSpec(
        repo_url="https://github.com/me/p.git", sha="abcdef1234", patch_configmap="p1"
    )
    m = build_job_manifest(spec, job_name("me/Playground", "abcdef1234", 1))
    pod = m["spec"]["template"]["spec"]
    assert m["metadata"]["name"] == "sbx-playground-abcdef12-1"
    assert m["spec"]["activeDeadlineSeconds"] == 300 and m["spec"]["backoffLimit"] == 0
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["automountServiceAccountToken"] is False
    c = pod["containers"][0]
    assert c["resources"]["limits"] == {"cpu": "2", "memory": "2Gi"}
    assert c["securityContext"]["capabilities"]["drop"] == ["ALL"]
    assert "git clone" not in c["command"][-1]  # test container never touches the network
