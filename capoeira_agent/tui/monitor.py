"""Helpers de renderização de estado do monitor (/status, toolbar)."""
from __future__ import annotations


def session_summary(session) -> str:
    n = len(session.records())
    return (f"projeto={session.slug} sessão={session.session_name} "
            f"revision={session.revision} registros={n}")


def status_block(config, session, registry, permissions, client, runner=None) -> str:
    providers = []
    try:
        providers = client.providers()
    except Exception:
        pass
    sl = []
    sl.append(f"host: {config.host.base_url}")
    sl.append(f"modelo: {config.host.model} (provider online: {len(providers)})")
    sl.append(f"new_chat: {config.host.new_chat}")
    sl.append(f"política: {permissions.mode} · sessão: {session.session_name}")
    sl.append("entrada de comandos: TUI (/exec <texto|--file CAMINHO>) · revision: "
              f"{session.revision}")
    sl.append(f"comandos registrados: {len(registry.names())} "
              f"· tools expostos à LLM: {len(registry.tool_definitions())}")
    for name in registry.tool_definitions():
        sl.append(f"  tool: {name['name']} — {name.get('desc') or ''}")
    return "\n".join(sl)
