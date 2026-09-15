from capoeira_agent.llm_client import LLMClient, parse_delta_lines, serialize_tools


def test_serialize_tools():
    tools = [{"name": "read_file", "desc": "lê arquivo", "args": {"path": "string"}}]
    out = serialize_tools(tools)
    assert "name=read_file" in out
    assert "path:string" in out


def test_chat_sends_form_and_tools(fake_host):
    fh = fake_host
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    ctrl = fh["ctrl"]
    ctrl.chat_default = "resposta legal"
    reply = client.chat(
        [
            {"role": "system", "content": "env"},
            {"role": "user", "content": "oi"},
            {"role": "tool", "content": "resultado", "tool_call_id": "call_0"},
        ],
        tools=[{"name": "x", "desc": "y", "args": {}}],
        new_chat=False,
    )
    assert reply.content == "resposta legal"
    _, form = ctrl.chat_requests[0]
    fields = dict(form)
    assert fields["model"] == "gemini-pro"
    assert fields["new_chat"] == "false"
    assert "tools" in fields
    assert ("role", "tool") in form
    assert ("tool_call_id", "call_0") in form


def test_read_chat(fake_host):
    fh = fake_host
    ctrl = fh["ctrl"]
    ctrl.transcript = "[USER] oi\n[ASSISTANT] resposta\n"
    ctrl.revision = 7
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    transcript, rev = client.read_chat()
    assert transcript == ctrl.transcript
    assert rev == 7


def test_watch_no_change_returns_empty(fake_host):
    fh = fake_host
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    delta, rev = client.watch(revision=3, timeout=5)
    assert delta == ""
    assert rev == 0  # header reflete 0 (sem revision no fake quando vazio)


def test_watch_returns_delta_and_revision(fake_host):
    fh = fake_host
    ctrl = fh["ctrl"]
    ctrl.push_watch(5, "[USER] novo\n[ASSISTANT] [TOOL_CALL] x | arg=1\n")
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    delta, rev = client.watch(revision=3, timeout=5)
    assert "[USER] novo" in delta
    assert rev >= 5


def test_chat_error_raises(fake_host):
    fh = fake_host
    ctrl = fh["ctrl"]
    ctrl.fail_chat = "503"
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    import pytest
    from capoeira_agent.llm_client import LLMRequestError

    with pytest.raises(LLMRequestError):
        client.chat([{"role": "user", "content": "x"}])


def test_parse_delta_lines():
    delta = "[USER] mensagem\n[ASSISTANT] resposta\n[USER] outra\n"
    turns = parse_delta_lines(delta)
    assert turns == [("user", "mensagem"), ("assistant", "resposta"), ("user", "outra")]