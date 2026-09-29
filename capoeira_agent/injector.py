"""/inject-environment: prompt de ambiente do projeto + dicionário de comandos (tools)."""
from __future__ import annotations

from pathlib import Path

from . import prompts
from .prompts import build_tools_block


def build_environment_blocks(session, premises, config_dir: Path | None = None) -> list[str]:
    """Blocos extras de contexto (stack, specs, skills) — fora do escopo do dicionário."""
    blocks: list[str] = []
    if premises is not None and premises.stack:
        stack = premises.stack
        blocks.append(f"Stack do projeto: {stack.get('language', '')} "
                      f"(template: {stack.get('template_engine', 'n/d')}).")
    return blocks


def build_environment_message(premises_name: str, description: str, blocks: list[str]) -> str:
    return prompts.build_environment_message(premises_name, description, blocks)


def inject_environment(client, session, registry, premises=None, *, new_chat: bool = False) -> str:
    """Envia ao chat ativo o ambiente + dicionário de comandos (fire-and-forget).

    O host responde com `accepted: {request_id}` e entrega a resposta do modelo
    via push — o agente não aguarda nem faz polling aqui."""
    tools = registry.tool_definitions()
    blocks = build_environment_blocks(session, premises)
    env_text = build_environment_message(
        premises.name if premises is not None else session.slug,
        premises.description if premises is not None else "",
        blocks + [build_tools_block(tools)],
    )
    session.append_message("system", env_text)
    reply = client.chat([{"role": "system", "content": env_text}], new_chat=new_chat)
    session.injected = True
    session.save_state()
    return reply.content