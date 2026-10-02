from capoeira_agent.core.registry import CommandRegistry
from capoeira_agent.executor import Executor
from capoeira_agent.llm_client import LLMClient
from capoeira_agent.permissions import PermissionGate
from capoeira_agent.runner import Runner
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
    out = []
    for path, form in fh["ctrl"].chat_requests:
        if path != "/api/chat":
            continue
        fields = dict(form)
        if "TOOL_RESULT" in (fields.get("content") or ""):
            out.append(fields)
    return out


def test_run_text_executes_and_sends_roundtrip(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    runner = Runner(session, gate, executor, registry, client)

    outcome = runner.run_text("[TOOL_CALL] read_file | path='dados.txt'\n")

    assert outcome.any_recognized
    assert outcome.roundtrip_sent
    results = _tool_results(fh)
    assert results
    assert "olá mundo" in results[0]["content"]


def test_run_text_prose_is_noop(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    runner = Runner(session, gate, executor, registry, client)

    outcome = runner.run_text("apenas uma resposta em prosa, sem comandos.")

    assert not outcome.steps
    assert not _tool_results(fh)


def test_roundtrip_sends_only_current_tool_result(fake_host, tmp_path):
    """Não reinjetar histórico: o round-trip leva só o resultado do turno."""
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    runner = Runner(session, gate, executor, registry, client)

    session.append_message("system", "ENV_HEADER_XYZ [TOOL] name=read_file desc=le")
    session.append_message("assistant", "[TOOL_CALL] list_dir | path='.'")

    runner.run_text("[TOOL_CALL] read_file | path='dados.txt'\n")

    results = _tool_results(fh)
    assert len(results) == 1
    content = results[0]["content"]
    assert content.startswith("[TOOL_RESULT]")
    assert "ENV_HEADER_XYZ" not in content
    assert "list_dir" not in content
    form = fh["ctrl"].chat_requests[0][1]
    assert sum(1 for key, _ in form if key == "role") == 1


def test_roundtrip_forces_new_chat_false(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    runner = Runner(session, gate, executor, registry, client)

    runner.run_text("[TOOL_CALL] read_file | path='dados.txt'\n")

    assert _tool_results(fh)[0]["new_chat"] == "false"


def test_readonly_denies_write(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    gate.set_mode("readonly")
    runner = Runner(session, gate, executor, registry, client)

    outcome = runner.run_text(
        "[TOOL_CALL] write_file | file_path='x.txt' | action=create_file | code_content=b2xhCg==\n")

    assert not (tmp_path / "p" / "x.txt").exists()
    results = _tool_results(fh)
    assert results
    assert "DENEGADO" in results[0]["content"]


def test_unknown_tool_not_sent(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    events: list[str] = []
    runner = Runner(session, gate, executor, registry, client, on_event=events.append)

    outcome = runner.run_text("[TOOL_CALL] foobar | a=1\n")

    assert outcome.unknown == ["foobar"]
    assert not _tool_results(fh)
    assert any("não reconhecido" in e for e in events)


def test_run_text_accepts_web_markup(fake_host, tmp_path):
    """Texto copiado com bullet/negrito continua executando."""
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    runner = Runner(session, gate, executor, registry, client)

    outcome = runner.run_text("Claro:\n- **[TOOL_CALL] read_file | path='dados.txt'**\n")

    assert outcome.any_recognized
    assert "olá mundo" in _tool_results(fh)[0]["content"]


def test_run_text_without_roundtrip(fake_host, tmp_path):
    fh, session, registry, client, gate, executor = _runtime(fake_host, tmp_path)
    runner = Runner(session, gate, executor, registry, client)

    outcome = runner.run_text("[TOOL_CALL] read_file | path='dados.txt'\n",
                              send_roundtrip=False)

    assert outcome.any_recognized
    assert not outcome.roundtrip_sent
    assert not _tool_results(fh)
