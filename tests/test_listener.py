import time

from capoeira_agent.core.registry import CommandRegistry
from capoeira_agent.executor import Executor
from capoeira_agent.listener import Listener
from capoeira_agent.llm_client import LLMClient
from capoeira_agent.permissions import PermissionGate
from capoeira_agent.session import Session


def _runtime(fake_host, tmp_path):
    fh = fake_host
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "dados.txt").write_text("olá mundo", encoding="utf-8")
    session = Session(proj, config_dir=tmp_path / "cfg")
    registry = CommandRegistry()
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    gate = PermissionGate(mode="auto")
    executor = Executor(proj, python="python", registry=registry)
    return fh, session, registry, client, gate, executor


def _send_round_of_listener(listener, delta, rev=1):
    listener._process_delta(delta, rev)


def test_process_delta_runs_tool(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, watch_timeout=5, new_chat=False)

    delta = "[USER] leia o arquivo por favor\n[ASSISTANT] [TOOL_CALL] read_file | path='dados.txt'\n"
    _send_round_of_listener(listener, delta)
    # o mirror registrou os turnos
    contents = [m["content"] for m in session.messages()]
    assert any("leia o arquivo" in c for c in contents)
    # round-trip enviado com role=tool
    tool_forms = [form for p, form in fh["ctrl"].chat_requests
                  if p == "/api/chat" and dict(form).get("role") == "tool"]
    assert tool_forms
    assert "olá mundo" in dict(tool_forms[0]).get("content", "")


def test_listener_round_trip_returns_prose_and_stops(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    fh["ctrl"].chat_default = "finalizado com sucesso, sem mais chamadas."
    listener = Listener(client, session, gate, executor, registry, watch_timeout=5, new_chat=False)
    _send_round_of_listener(listener,
                            "[USER] crie um arquivo\n"
                            "[ASSISTANT] [TOOL_CALL] write_file | file_path='novo.txt' | "
                            "action=create_file | code_content=b2xhCg==\n")
    assert (tmp_path / "p" / "novo.txt").exists()
    assert "finalizado com sucesso" in " ".join(m["content"] for m in session.messages())


def test_listened_tool_denied_when_policy_readonly(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    gate.set_mode("readonly")
    listener = Listener(client, session, gate, executor, registry, watch_timeout=5, new_chat=False)
    fh["ctrl"].chat_default = "[TOOL_CALL] write_file | file_path='x.txt' | action=create_file | code_content=b2xhCg==\n"
    _send_round_of_listener(listener,
                            "[USER] crie x.txt\n"
                            "[ASSISTANT] [TOOL_CALL] write_file | file_path='x.txt' | action=create_file | code_content=b2xhCg==\n")
    assert not (tmp_path / "p" / "x.txt").exists()
    # nota de negação chegou ao modelo
    round_forms = [form for p, form in fh["ctrl"].chat_requests if p == "/api/chat" and dict(form).get("role") == "tool"]
    assert round_forms
    assert "DENEGADO" in dict(round_forms[0]).get("content", "")


def test_listener_start_injects_and_watches(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)

    def fake_inject():
        session.injected = True
        session.save_state()
        return "ok"

    listener = Listener(client, session, gate, executor, registry, watch_timeout=1,
                        inject_environment=fake_inject, new_chat=False)
    listener.start()
    try:
        time.sleep(0.2)
        assert session.injected
        fh["ctrl"].push_watch(1, "[USER] oi\n[ASSISTANT] tudo bem\n")
        time.sleep(0.3)
        assert "oi" in " ".join(m["content"] for m in session.messages())
    finally:
        listener.stop()