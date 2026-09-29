from types import SimpleNamespace

from capoeira_agent.commands.inject_environment import InjectEnvironmentCommand
from capoeira_agent.core.registry import CommandRegistry
from capoeira_agent.injector import inject_environment
from capoeira_agent.llm_client import LLMClient
from capoeira_agent.session import Session
from capoeira_agent.config import Premises


def _make(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    session = Session(proj, config_dir=tmp_path / "cfg")
    return session


def test_inject_sends_system_and_tools(fake_host, tmp_path):
    fh = fake_host
    ctrl = fh["ctrl"]
    session = _make(tmp_path)
    registry = CommandRegistry()
    premises = Premises(name="meu-projeto", description="sistema de garagens")
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)

    ack = inject_environment(client, session, registry, premises, new_chat=False)

    assert session.injected is True
    assert ack.startswith("accepted: ")
    _, form = ctrl.chat_requests[0]
    fields = dict(form)
    assert fields["new_chat"] == "false"
    # pass-through verbatim: contrato de tools viaja no CONTENT da mensagem, sem campo 'tools'
    assert "tools" not in fields
    assert "meu-projeto" in fields["content"]  # ambiente via role=system
    assert "[TOOL] name=read_file" in fields["content"]  # dicionário de comandos no texto
    # o environment ficou no mirror da sessão (system)
    assert any(m["role"] == "system" and "meu-projeto" in m["content"] for m in session.messages())


def test_inject_command_prints_ack(fake_host, tmp_path, capsys):
    fh = fake_host
    session = _make(tmp_path)
    registry = CommandRegistry()
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    config = SimpleNamespace(host=SimpleNamespace(model="gemini-pro", new_chat=False))
    cmd = InjectEnvironmentCommand()
    cmd.context = SimpleNamespace(client=client, session=session, registry=registry,
                                  listener=None, config=config)

    cmd.execute([])

    out = capsys.readouterr().out
    assert "ambiente injetado" in out
    assert "accepted: " in out
    assert session.injected
