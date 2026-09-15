from capoeira_agent.config import slugify
from capoeira_agent.session import Session


def _make(tmp_path, name="default"):
    proj = tmp_path / "projeto-x"
    proj.mkdir(exist_ok=True)
    return Session(proj, config_dir=tmp_path / "cfg", session_name=name)


def test_messages_and_history(tmp_path):
    s = _make(tmp_path)
    s.append_message("user", "oi")
    s.append_message("assistant", "tudo bem?")
    msgs = s.messages()
    assert msgs == [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "tudo bem?"}]
    # recarrega do disco
    s2 = _make(tmp_path)
    assert len(s2.records()) == 2


def test_tool_call_message_with_id(tmp_path):
    s = _make(tmp_path)
    s.append_message("assistant", "[TOOL_CALL] x | a=1")
    s.append_message("tool", "resultado", tool_call_id="call_0")
    msgs = s.messages()
    assert msgs[1] == {"role": "tool", "content": "resultado", "tool_call_id": "call_0"}


def test_revision_state_persisted(tmp_path):
    s = _make(tmp_path)
    s.revision = 9
    s.injected = True
    s.save_state()
    s2 = _make(tmp_path)
    assert s2.revision == 9
    assert s2.injected is True


def test_clear(tmp_path):
    s = _make(tmp_path)
    s.append_message("user", "oi")
    s.revision = 5
    s.clear()
    assert s.records() == []
    assert s.revision == 0


def test_switch_session(tmp_path):
    s = _make(tmp_path, "default")
    s.append_message("user", "conteudo-default")
    s.switch("outra")
    assert s.records() == []
    s.append_message("user", "conteudo-outra")
    s.switch("default")
    assert [r["content"] for r in s.records()] == ["conteudo-default"]


def test_slugify():
    assert slugify("Meu Projeto X") == "meu-projeto-x"
    assert slugify("sistemas\\garagens") == "sistemas-garagens"
    assert slugify("meu-projeto") == "meu-projeto"
    assert slugify("") == "default"