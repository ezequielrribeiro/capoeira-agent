import capoeira_agent.entry as entry


def test_parse_args_default_path():
    opts = entry.parse_args([])
    assert opts["path"] == "."


def test_parse_args_positional_and_flags():
    opts = entry.parse_args(["C:\\proj", "--model", "claude-sonnet", "--readonly", "--new-chat", "false"])
    assert opts["path"] == "C:\\proj"
    assert opts["model"] == "claude-sonnet"
    assert opts["readonly"] is True
    assert opts["new_chat"] == "false"


def test_help_flag():
    assert entry.parse_args(["--help"])["help"] is True


def test_bootstrap_builds_runtime(tmp_path):
    proj = tmp_path / "projeto"
    proj.mkdir()
    opts = {
        "path": str(proj),
        "config_dir": str(tmp_path / "cfg"),
        "model": "gemini-pro",
        "new_chat": "false",
        "base_url": "http://127.0.0.1:9999",
    }
    tui = entry.bootstrap(opts, prompt_override=lambda t, p: "n")
    assert tui.config.host.model == "gemini-pro"
    assert tui.config.host.new_chat is False
    assert tui.config.host.clipboard_poll > 0
    assert tui.session.slug == "projeto"
    assert tui.listener is not None
    assert tui.registry.get("/help") is not None
    assert tui.registry.get("/init") is not None
    assert len(tui.registry.tool_definitions()) >= 7


def test_main_help_returns_zero(capsys):
    assert entry.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "capoeira-agent" in out