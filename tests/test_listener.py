from capoeira_agent.core.registry import CommandRegistry
from capoeira_agent.executor import Executor
from capoeira_agent.listener import Listener
from capoeira_agent.llm_client import LLMClient
from capoeira_agent.permissions import PermissionGate
from capoeira_agent.session import Session


class _StubReceiver:
    def __init__(self):
        self.listening = False
        self.started = False
        self.stopped = False

    def start(self):
        self.listening = True
        self.started = True

    def stop(self):
        self.listening = False
        self.stopped = True


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


def _payload(text, error=None):
    return {"request_id": "req-1", "model": "gemini-pro", "provider": "gemini",
            "endpoint": "chat", "stream": False, "text": text, "error": error}


def test_handle_response_runs_tool(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response(_payload("[TOOL_CALL] read_file | path='dados.txt'\n"))

    contents = [m["content"] for m in session.messages()]
    assert any("read_file" in c for c in contents)
    results = _tool_results(fh)
    assert results
    assert "olá mundo" in results[0]["content"]


def test_handle_response_prose_mirrors_without_roundtrip(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response(_payload("finalizado com sucesso, sem mais chamadas."))

    assert "finalizado com sucesso" in " ".join(m["content"] for m in session.messages())
    assert not _tool_results(fh)


def test_handle_response_error_emits(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    events: list[str] = []
    listener = Listener(client, session, gate, executor, registry, on_event=events.append, new_chat=False)

    listener.handle_response(_payload("", error="falha na injeção"))

    assert any("falha na injeção" in e for e in events)
    assert not _tool_results(fh)


def test_handle_response_denied_when_policy_readonly(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    gate.set_mode("readonly")
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response(_payload(
        "[TOOL_CALL] write_file | file_path='x.txt' | action=create_file | code_content=b2xhCg==\n"))

    assert not (tmp_path / "p" / "x.txt").exists()
    round_results = _tool_results(fh)
    assert round_results
    assert "DENEGADO" in round_results[0]["content"]


def test_handle_response_unrecognized_command_not_resent(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    events: list[str] = []
    listener = Listener(client, session, gate, executor, registry, on_event=events.append, new_chat=False)

    listener.handle_response(_payload("[TOOL_CALL] foobar | a=1\n"))

    assert not _tool_results(fh)
    assert any("não reconhecido" in e for e in events)


def test_handle_response_done_does_not_execute(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, new_chat=False)

    listener.handle_response(_payload("[TOOL_CALL] done\n"))

    assert not _tool_results(fh)


def test_start_registers_and_stop_unregisters(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    listener = Listener(client, session, gate, executor, registry, app_port=8123, new_chat=False)
    listener._receiver = _StubReceiver()

    listener.start()
    assert listener.listening
    assert fh["ctrl"].app_port == 8123
    assert fh["ctrl"].register_requests

    listener.stop()
    assert not listener.listening
    assert fh["ctrl"].unregister_requests == 1
    assert fh["ctrl"].app_port is None
