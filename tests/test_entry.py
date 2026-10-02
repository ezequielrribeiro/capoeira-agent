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
    assert tui.config.host.timeout > 0
    assert tui.session.slug == "projeto"
    assert tui.runner is not None
    assert tui.registry.get("/help") is not None
    assert tui.registry.get("/init") is not None
    assert tui.registry.get("/exec") is not None
    assert len(tui.registry.tool_definitions()) >= 7


def test_exec_command_via_tui_executes_tool(fake_host, tmp_path):
    """Fluxo real: /exec colado na TUI executa o [TOOL_CALL] e faz round-trip."""
    proj = tmp_path / "projeto"
    proj.mkdir()
    (proj / "dados.txt").write_text("olá mundo", encoding="utf-8")
    opts = {
        "path": str(proj),
        "config_dir": str(tmp_path / "cfg"),
        "model": "gemini-pro",
        "new_chat": "false",
        "base_url": fake_host["base"],
    }
    tui = entry.bootstrap(opts, prompt_override=lambda t, p: "y")

    tui._dispatch("/exec [TOOL_CALL] read_file | path='dados.txt'")

    forms = [dict(form) for p, form in fake_host["ctrl"].chat_requests
             if p == "/api/chat" and "TOOL_RESULT" in (dict(form).get("content") or "")]
    assert forms, "round-trip com [TOOL_RESULT] deveria ter acontecido"
    assert "olá mundo" in forms[0]["content"]


def test_exec_without_tool_call_reports(fake_host, tmp_path, capsys):
    proj = tmp_path / "projeto"
    proj.mkdir()
    opts = {
        "path": str(proj),
        "config_dir": str(tmp_path / "cfg"),
        "model": "gemini-pro",
        "new_chat": "false",
        "base_url": fake_host["base"],
    }
    tui = entry.bootstrap(opts, prompt_override=lambda t, p: "y")

    tui._dispatch("/exec apenas uma resposta em prosa, sem comandos")

    out = capsys.readouterr().out
    assert "nenhum [TOOL_CALL]" in out


def test_exec_from_file(fake_host, tmp_path):
    proj = tmp_path / "projeto"
    proj.mkdir()
    (proj / "dados.txt").write_text("conteúdo do arquivo", encoding="utf-8")
    resposta = proj / "resposta.txt"
    resposta.write_text("[TOOL_CALL] read_file | path='dados.txt'\n", encoding="utf-8")
    opts = {
        "path": str(proj),
        "config_dir": str(tmp_path / "cfg"),
        "model": "gemini-pro",
        "new_chat": "false",
        "base_url": fake_host["base"],
    }
    tui = entry.bootstrap(opts, prompt_override=lambda t, p: "y")

    tui._dispatch(f"/exec --file {resposta}")

    forms = [dict(form) for p, form in fake_host["ctrl"].chat_requests
             if p == "/api/chat" and "TOOL_RESULT" in (dict(form).get("content") or "")]
    assert forms
    assert "conteúdo do arquivo" in forms[0]["content"]


def test_main_help_returns_zero(capsys):
    assert entry.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "capoeira-agent" in out