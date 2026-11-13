"""The repair cycle as a LangGraph with an explicit back-edge.

    read_failure -> locate -> propose_patch -> guard -> run_tests -> decide
                                  ^                                    |
                                  +------------ retry -----------------+

On success Sentinel opens a PR from ``sentinel/fix-*``. It never pushes to the
PR branch or to main. On any other stop it posts a diagnosis comment instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

from sentinel.llm import LLM
from sentinel.repair.budget import RepairBudget, StopReason
from sentinel.repair.guard import patch_violations
from sentinel.telemetry import LLM_COST, REPAIR_OUTCOME

PATCH_SYSTEM = """You fix failing CI. Return ONLY a unified diff that applies with `git apply`.
Fix the code under test. Never delete, skip or weaken tests, and never edit CI config.
If the failure is in the test itself and the test is clearly wrong, say so in a
comment line starting with '# sentinel:' and still return a minimal diff."""


@dataclass
class TestRun:
    passed: bool
    log: str


class Sandbox(Protocol):
    async def run(self, patch: str, attempt: int) -> TestRun: ...


class RepoReader(Protocol):
    async def relevant_files(self, failure_log: str) -> str: ...


class RepairState(TypedDict, total=False):
    failure_log: str
    context: str
    patch: str
    last_run: TestRun
    budget: RepairBudget
    stop: StopReason | None
    history: list[str]


def build_repair_graph(llm: LLM, repo: RepoReader, sandbox: Sandbox) -> Any:
    from langgraph.graph import END, StateGraph

    async def locate(state: RepairState) -> RepairState:
        return {"context": await repo.relevant_files(state["failure_log"])}

    async def propose(state: RepairState) -> RepairState:
        prior = "\n\n".join(state.get("history", [])[-2:])
        user = (
            f"<untrusted>\nCI failure:\n{state['failure_log'][-8000:]}\n\n"
            f"Relevant code:\n{state['context']}\n\n"
            f"Previous attempts that did not work:\n{prior or '(none)'}\n</untrusted>"
        )
        res = await llm.complete(PATCH_SYSTEM, user)
        LLM_COST.labels("repair").inc(res.cost_usd)
        state["budget"].cost_usd += res.cost_usd
        return {"patch": res.text}

    async def guard(state: RepairState) -> RepairState:
        problems = patch_violations(state["patch"])
        if problems:
            return {"stop": StopReason.tampering, "history": [*state.get("history", []), *problems]}
        return {}

    async def run_tests(state: RepairState) -> RepairState:
        budget = state["budget"]
        run = await sandbox.run(state["patch"], attempt=budget.iterations + 1)
        budget.record(cost_usd=0.0, failure_log=None if run.passed else run.log)
        return {"last_run": run}

    async def decide(state: RepairState) -> RepairState:
        run = state["last_run"]
        stop = state["budget"].should_stop(tests_passed=run.passed)
        history = state.get("history", [])
        if not run.passed:
            history = [*history, f"patch:\n{state['patch']}\nresult:\n{run.log[-2000:]}"]
            return {"stop": stop, "history": history, "failure_log": run.log}
        return {"stop": stop}

    def after_guard(state: RepairState) -> str:
        return "end" if state.get("stop") else "run_tests"

    def after_decide(state: RepairState) -> str:
        return "end" if state.get("stop") else "retry"

    g = StateGraph(RepairState)
    g.add_node("locate", locate)
    g.add_node("propose", propose)
    g.add_node("guard", guard)
    g.add_node("run_tests", run_tests)
    g.add_node("decide", decide)
    g.set_entry_point("locate")
    g.add_edge("locate", "propose")
    g.add_edge("propose", "guard")
    g.add_conditional_edges("guard", after_guard, {"run_tests": "run_tests", "end": END})
    g.add_edge("run_tests", "decide")
    g.add_conditional_edges("decide", after_decide, {"retry": "propose", "end": END})
    return g.compile()


async def run_repair(graph: Any, failure_log: str, budget: RepairBudget) -> RepairState:
    state: RepairState = await graph.ainvoke({"failure_log": failure_log, "budget": budget})
    REPAIR_OUTCOME.labels((state.get("stop") or StopReason.max_iterations).value).inc()
    return state
