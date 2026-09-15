import pytest

from capoeira_agent.permissions import PermissionGate
from capoeira_agent.steps import Step


def step(tool, **params):
    return Step(tool=tool, params=params)


def test_read_tools_auto():
    gate = PermissionGate(mode="readonly")
    assert gate.decide(step("read_file", path="x")).action == "auto"
    assert gate.decide(step("list_dir")).action == "auto"


def test_readonly_denies_execution():
    gate = PermissionGate(mode="readonly")
    assert gate.decide(step("run_shell")).action == "deny"
    assert gate.decide(step("write_file")).action == "deny"


def test_auto_mode_allows_all():
    gate = PermissionGate(mode="auto")
    assert gate.decide(step("run_shell")).action == "auto"
    assert gate.decide(step("write_file")).action == "auto"


def test_ask_mode_questions():
    gate = PermissionGate(mode="ask")
    assert gate.decide(step("run_shell")).action == "question"


def test_ask_always_for_session():
    gate = PermissionGate(mode="ask", ask_user=lambda tool, params: "a")
    allowed, always = gate.ask(step("run_shell"))
    assert allowed and always == "always"
    assert gate.decide(step("run_shell")).action == "auto"  # na sessão


def test_ask_deny():
    gate = PermissionGate(mode="ask", ask_user=lambda t, p: "n")
    allowed, _ = gate.ask(step("run_shell"))
    assert allowed is False


def test_ask_yes():
    gate = PermissionGate(mode="ask", ask_user=lambda t, p: "y")
    allowed, _ = gate.ask(step("run_shell"))
    assert allowed is True


def test_reset_session_clears_always():
    gate = PermissionGate(mode="ask", ask_user=lambda t, p: "a")
    gate.ask(step("run_shell"))
    gate.reset_session()
    assert gate.decide(step("run_shell")).action == "question"