from capoeira_agent.llm_client import LLMClient


def test_chat_sends_form_and_serializes_tool_result(fake_host):
    fh = fake_host
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    ctrl = fh["ctrl"]
    reply = client.chat(
        [
            {"role": "system", "content": "env"},
            {"role": "user", "content": "oi"},
            {"role": "tool", "content": "resultado", "tool_call_id": "call_0"},
        ],
        new_chat=False,
    )
    assert reply.content.startswith("accepted: ")
    assert reply.request_id is not None
    _, form = ctrl.chat_requests[0]
    fields = dict(form)
    assert fields["model"] == "gemini-pro"
    assert fields["new_chat"] == "false"
    assert "tools" not in fields  # pass-through verbatim: sem campo tools
    assert "tool_call_id" not in fields
    # role=tool é serializado como assistant + [TOOL_RESULT] no fio
    assert ("role", "assistant") in form
    assert ("content", "[TOOL_RESULT] (call_0) resultado") in form


def test_chat_returns_request_id(fake_host):
    fh = fake_host
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    reply = client.chat([{"role": "user", "content": "oi"}])
    assert reply.request_id == "req-1"


def test_chat_error_raises(fake_host):
    fh = fake_host
    ctrl = fh["ctrl"]
    ctrl.fail_chat = "503"
    client = LLMClient(fh["base"], "gemini-pro", timeout=10)
    import pytest
    from capoeira_agent.llm_client import LLMRequestError

    with pytest.raises(LLMRequestError):
        client.chat([{"role": "user", "content": "x"}])
