"""E2E: wiring real do entry.bootstrap — /inject-environment + push do host -> execução local."""
import capoeira_agent.entry as entry


def _opts(tmp_path, fh):
    proj = tmp_path / "projeto"
    proj.mkdir()
    return {
        "path": str(proj),
        "config_dir": str(tmp_path / "cfg"),
        "model": "gemini-pro",
        "new_chat": "false",
        "base_url": fh["base"],
    }


def test_e2e_inject_then_push_executes_locally(fake_host, tmp_path):
    fh = fake_host
    tui = entry.bootstrap(_opts(tmp_path, fh), prompt_override=lambda t, p: "y")

    # /inject-environment (injeção real via client + sessão + registry)
    inject_cmd = tui.registry.get("/inject-environment")
    inject_cmd.execute([])
    assert tui.session.injected

    # push do host com [TOOL_CALL] -> executa localmente e faz round-trip
    listener = tui.listener
    listener.handle_response({
        "request_id": "req-1", "model": "gemini-pro", "provider": "gemini",
        "endpoint": "chat", "stream": False,
        "text": "[TOOL_CALL] write_file | file_path='novo.txt' | action=create_file | "
                "code_content=b2xhY2FwcG9laXJhCg==\n",
    })

    assert (tmp_path / "projeto" / "novo.txt").exists()
    results = [dict(form) for p, form in fh["ctrl"].chat_requests
               if p == "/api/chat" and "TOOL_RESULT" in (dict(form).get("content") or "")]
    assert results, "round-trip com [TOOL_RESULT] deveria ter acontecido"
