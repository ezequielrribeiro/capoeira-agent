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
    ctrl.chat_default = "[TOOL_CALL] read_file | path='a.txt'\n"
    session = _make(tmp_path)
    registry = CommandRegistry()
    premises = Premises(name="meu-projeto", description="sistema de garagens")
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)

    reply = inject_environment(client, session, registry, premises, new_chat=False)

    assert session.injected is True
    assert "[TOOL_CALL]" in reply
    _, form = ctrl.chat_requests[0]
    fields = dict(form)
    assert fields["new_chat"] == "false"
    assert "tools" in fields
    assert "meu-projeto" in fields["content"]  # ambiente via role=system
    # o environment ficou no mirror da sessão (system)
    assert any(m["role"] == "system" and "meu-projeto" in m["content"] for m in session.messages())