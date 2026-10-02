"""Entry point: `capoeira-agent [PATH] [flags]` → sempre abre a TUI."""
from __future__ import annotations

import sys
from pathlib import Path

from . import llm_client
from .config import AgentConfig, Premises, resolve_config_dir
from .core.command import AgentContext
from .core.loader import apply_context, load_all
from .core.registry import CommandRegistry
from .executor import Executor
from .injector import inject_environment
from .listener import Listener
from .permissions import PermissionGate
from .session import Session
from .tui.app import Tui

USAGE = """uso: capoeira-agent [PATH] [opções]

PATH  pasta raiz do projeto (padrão: diretório atual)

opções:
  --config DIR         diretório de configuração global
  --project NOME       premissas do projeto (projects/<nome>.yaml)
  --session NOME       sessão a abrir/criar (padrão: default)
  --model M            perfil de provedor do CapoeiraHost
  --base-url URL       base URL do CapoeiraHost (padrão: http://127.0.0.1:8765)
  --timeout SEG        timeout por requisição
  --policy MODE        auto | ask | readonly
  --readonly           atalho para --policy readonly
  --new-chat VAL       true | false (padrão do agente: false)
  -h, --help           mostra esta ajuda
"""


def parse_args(argv: list[str]) -> dict:
    opts = {"path": "."}
    i = 0
    flags = {
        "--config": "config_dir", "--project": "project", "--session": "session",
        "--model": "model", "--base-url": "base_url", "--timeout": "timeout",
        "--policy": "policy", "--new-chat": "new_chat",
    }
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            opts["help"] = True
            i += 1
            continue
        if arg == "--readonly":
            opts["readonly"] = True
            i += 1
            continue
        if arg in flags and i + 1 < len(argv):
            opts[flags[arg]] = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--"):
            print(f"opção desconhecida: {arg}", file=sys.stderr)
            opts["help"] = True
            i += 1
            continue
        opts["path"] = arg  # primeiro token posicional vira PATH
        i += 1
    return opts


def bootstrap(opts: dict, *, prompt_override=None) -> Tui:
    config_dir = Path(opts.get("config_dir") or resolve_config_dir())
    config = AgentConfig.load(config_dir)

    if opts.get("model"):
        config.host.model = opts["model"]
    if opts.get("base_url"):
        config.host.base_url = opts["base_url"].rstrip("/")
    if opts.get("timeout"):
        config.host.timeout = int(opts["timeout"])
    if opts.get("new_chat"):
        config.host.new_chat = opts["new_chat"].lower() in ("true", "1")
    if opts.get("readonly"):
        config.policy.mode = "readonly"
    if opts.get("policy"):
        config.policy.mode = opts["policy"]

    project_root = Path(opts["path"]).expanduser()
    session = Session(project_root, config_dir, session_name=opts.get("session") or "default")
    premises = Premises.load(config_dir, opts.get("project") or session.slug)
    session.premises = premises

    client = llm_client.LLMClient(config.host.base_url, config.host.model, config.host.timeout)
    registry = CommandRegistry()
    load_all(registry, project_root / "commands", config_dir / "commands")

    permissions = PermissionGate(mode=config.policy.mode)
    executor = Executor(project_root, python=config.python, timeout=config.host.timeout, registry=registry)

    tui = Tui(config, session, registry, permissions, client, executor,
              project_root=project_root, prompt_override=prompt_override)
    permissions.ask_user = tui.ask_approval

    def _inject_if_needed() -> str:
        if session.injected:
            return ""
        return inject_environment(client, session, registry, session.premises,
                                  new_chat=config.host.new_chat)

    listener = Listener(client, session, permissions, executor, registry,
                        poll_interval=config.host.clipboard_poll,
                        inject_environment=_inject_if_needed,
                        on_event=tui.event,
                        new_chat=config.host.new_chat)

    context = AgentContext(config, session, client, registry, permissions, tui, project_root)
    context.listener = listener
    tui.listener = listener
    apply_context(registry, context)
    return tui


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    opts = parse_args(argv)
    if opts.get("help"):
        print(USAGE)
        return 0
    tui = bootstrap(opts)
    tui.run()
    return 0


if __name__ == "__main__":  # permite `python -m capoeira_agent.entry`
    raise SystemExit(main())