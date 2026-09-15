"""/inject-environment: prompt de ambiente do projeto + dicionário de comandos (tools)."""
from __future__ import annotations

from pathlib import Path

from . import prompts


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
    """Envia ao chat ativo o ambiente + dicionário de comandos. Retorna a resposta do modelo."""
    tools = registry.tool_definitions()
    blocks = build_environment_blocks(session, premises)
    env_text = build_environment_message(
        premises.name if premises is not None else session.slug,
        premises.description if premises is not None else "",
        blocks + _tools_description(tools),
    )
    session.append_message("system", env_text)
    reply = client.chat([{"role": "system", "content": env_text}], tools=tools, new_chat=new_chat)
    session.injected = True
    session.save_state()
    return reply.content


def _tools_description(tools: list[dict]) -> list[str]:
    if not tools:
        return ["Nenhum comando remoto disponível neste momento."]
    lines = ["Comandos que você pode invocar localmente (dicionário):"]
    for tool in tools:
        args = ", ".join(f"{k}:{v}" for k, v in tool.get("args", {}).items()) or "(sem args)"
        lines.append(f"- {tool['name']}: {tool.get('desc') or 'sem descrição'} [{args}]")
    lines.append("Siga o contrato [TOOL_CALL] descrito nas instruções do sistema.")
    return lines