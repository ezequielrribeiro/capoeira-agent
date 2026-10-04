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
                                  runner=None, config=config)

    cmd.execute([])

    out = capsys.readouterr().out
    assert "ambiente injetado" in out
    assert "accepted: " in out
    assert session.injected


def test_inject_filters_disabled_tools(fake_host, tmp_path):
    fh = fake_host
    ctrl = fh["ctrl"]
    session = _make(tmp_path)
    cfg_dir = tmp_path / "cfg"
    (cfg_dir).mkdir(exist_ok=True)
    (cfg_dir / "tools.yaml").write_text(
        "tools:\n  - name: write_file\n    enabled: false\n", encoding="utf-8")
    registry = CommandRegistry()
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)

    inject_environment(client, session, registry, None, new_chat=False)

    _, form = ctrl.chat_requests[0]
    content = dict(form)["content"]
    assert "[TOOL] name=read_file" in content
    assert "[TOOL] name=write_file" not in content
    # a contagem reflete o filtro
    assert all(t["name"] != "write_file" for t in registry.tool_definitions())


def test_inject_without_tools_yaml_keeps_all(fake_host, tmp_path):
    fh = fake_host
    ctrl = fh["ctrl"]
    session = _make(tmp_path)
    registry = CommandRegistry()
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)

    inject_environment(client, session, registry, None, new_chat=False)

    _, form = ctrl.chat_requests[0]
    content = dict(form)["content"]
    assert "[TOOL] name=write_file" in content


def test_init_creates_tools_yaml(tmp_path):
    from types import SimpleNamespace as NS
    from capoeira_agent.commands.init import InitCommand

    proj = tmp_path / "p"
    proj.mkdir()
    session = Session(proj, config_dir=tmp_path / "cfg")
    registry = CommandRegistry()
    cmd = InitCommand()
    cmd.context = NS(project_root=proj, session=session, registry=registry)

    cmd.execute([])

    path = tmp_path / "cfg" / "tools.yaml"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "name: read_file" in text
    assert "enabled: true" in text
