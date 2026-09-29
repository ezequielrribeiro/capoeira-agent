from types import SimpleNamespace

from capoeira_agent.commands.model import ModelCommand


def test_model_updates_config_and_client():
    host = SimpleNamespace(model="old", base_url="http://x/", timeout=5, new_chat=False)
    client = SimpleNamespace(model="old", timeout=5)
    cmd = ModelCommand()
    cmd.context = SimpleNamespace(config=SimpleNamespace(host=host), client=client)

    cmd.execute(["gemini-2.0-flash"])

    assert host.model == "gemini-2.0-flash"
    assert client.model == "gemini-2.0-flash"


def test_model_optional_flags_update_config_and_client():
    host = SimpleNamespace(model="old", base_url="http://x/", timeout=5, new_chat=False)
    client = SimpleNamespace(model="old", timeout=5)
    cmd = ModelCommand()
    cmd.context = SimpleNamespace(config=SimpleNamespace(host=host), client=client)

    cmd.execute(["claude-sonnet", "--timeout", "60", "--base-url", "http://y/", "--new-chat", "true"])

    assert host.model == "claude-sonnet"
    assert client.model == "claude-sonnet"
    assert host.base_url == "http://y"
    assert host.timeout == 60
    assert client.timeout == 60
    assert host.new_chat is True


def test_model_without_args_shows_usage_and_keeps_state():
    host = SimpleNamespace(model="m", base_url="http://x/", timeout=5, new_chat=False)
    client = SimpleNamespace(model="m", timeout=5)
    cmd = ModelCommand()
    cmd.context = SimpleNamespace(config=SimpleNamespace(host=host), client=client)

    cmd.execute([])

    assert host.model == "m"
    assert client.model == "m"