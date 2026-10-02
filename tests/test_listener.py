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


def _tool_results(fh):
    """Requests de round-trip no fake host: o último par é o turno de resultado,
    serializado no fio como role=assistant com [TOOL_RESULT] (pass-through verbatim)."""
    out = []
    for path, form in fh["ctrl"].chat_requests:
        if path != "/api/chat":
            continue
        fields = dict(form)
        if "TOOL_RESULT" in (fields.get("content") or ""):
            out.append(fields)
    return out


def test_handle_response_runs_tool(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response("[TOOL_CALL] read_file | path='dados.txt'\n")

    contents = [m["content"] for m in session.messages()]
    assert any("read_file" in c for c in contents)
    results = _tool_results(fh)
    assert results
    assert "olá mundo" in results[0]["content"]


def test_handle_response_prose_does_nothing(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response("finalizado com sucesso, sem mais chamadas.")

    assert not session.messages()
    assert not _tool_results(fh)


def test_handle_response_denied_when_policy_readonly(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    gate.set_mode("readonly")
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response(
        "[TOOL_CALL] write_file | file_path='x.txt' | action=create_file | code_content=b2xhCg==\n")

    assert not (tmp_path / "p" / "x.txt").exists()
    round_results = _tool_results(fh)
    assert round_results
    assert "DENEGADO" in round_results[0]["content"]


def test_handle_response_unrecognized_command_not_resent(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    events: list[str] = []
    listener = Listener(client, session, gate, executor, registry, on_event=events.append, new_chat=False)

    listener.handle_response("[TOOL_CALL] foobar | a=1\n")

    assert not _tool_results(fh)
    assert any("não reconhecido" in e for e in events)


def test_handle_response_done_does_not_execute(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response("[TOOL_CALL] done\n")

    assert not _tool_results(fh)


def test_roundtrip_sends_only_current_tool_result(fake_host, tmp_path):
    """Não reinjetar histórico: o round-trip leva só o resultado do turno,
    sem header do /inject-environment nem [TOOL_CALL] anteriores."""
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    session.append_message("system", "ENV_HEADER_XYZ [TOOL] name=read_file desc=le")
    session.append_message("assistant", "[TOOL_CALL] list_dir | path='.'")

    listener.handle_response("[TOOL_CALL] read_file | path='dados.txt'\n")

    results = _tool_results(fh)
    assert len(results) == 1
    content = results[0]["content"]
    assert content.startswith("[TOOL_RESULT]")
    assert "olá mundo" in content
    assert "ENV_HEADER_XYZ" not in content
    assert "[TOOL] " not in content
    assert "list_dir" not in content
    # o round-trip é um único turno (sem o transcript acumulado)
    form = fh["ctrl"].chat_requests[0][1]
    assert sum(1 for key, _ in form if key == "role") == 1


def test_roundtrip_forces_new_chat_false_even_when_configured_true(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=True)

    listener.handle_response("[TOOL_CALL] read_file | path='dados.txt'\n")

    results = _tool_results(fh)
    assert results
    assert results[0]["new_chat"] == "false"


def test_duplicate_turn_not_executed_twice(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    events: list[str] = []
    listener = Listener(client, session, gate, executor, registry, on_event=events.append, new_chat=False)

    text = "[TOOL_CALL] read_file | path='dados.txt'\n"
    listener.handle_response(text)
    listener.handle_response(text)

    assert len(_tool_results(fh)) == 1
    assert any("anti-loop" in e for e in events)


def test_duplicate_turn_with_varying_whitespace(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response("[TOOL_CALL] read_file | path='dados.txt'")
    listener.handle_response("[TOOL_CALL] read_file | path='dados.txt'\n\n")

    assert len(_tool_results(fh)) == 1


def test_start_stop_monitor_uses_clipboard(fake_host, tmp_path, monkeypatch):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, poll_interval=0.05, new_chat=False)
    monkeypatch.setattr(listener, "_current_clipboard", staticmethod(lambda: "conteudo"))

    assert not listener.listening
    msg = listener.start()
    assert "monitor" in msg
    assert listener.listening
    assert listener.stop() == "monitor encerrado"
    assert not listener.listening


def test_clipboard_change_is_processed(fake_host, tmp_path, monkeypatch):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    events: list[str] = []
    listener = Listener(client, session, gate, executor, registry, poll_interval=0.05,
                        on_event=events.append, new_chat=False)

    state = {"text": ""}
    monkeypatch.setattr(listener, "_current_clipboard", staticmethod(lambda: state["text"]))

    listener.start()
    state["text"] = "[TOOL_CALL] read_file | path='dados.txt'\n"
    deadline = __import__("time").monotonic() + 3.0
    while __import__("time").monotonic() < deadline and not _tool_results(fh):
        __import__("time").sleep(0.02)
    listener.stop()

    assert _tool_results(fh), "mudança de clipboard deveria disparar a execução"
