"""/init: cria os artefatos iniciais do projeto (árvore, specs/skills/commands com exemplos)."""
from __future__ import annotations

from pathlib import Path

SPEC_EXAMPLE = """# Spec do projeto

Escreva aqui as regras, padrões e convenções do sistema.
Este arquivo é injetado no chat ativo pelo /inject-environment.
"""

SKILL_EXAMPLE = """# Skill: procedimento exemplo

Descreva um procedimento reutilizável que a LLM deve seguir
ao executar comandos neste projeto.
"""

PLUGIN_EXAMPLE = '''"""Plug-in de exemplo — cria um comando do projeto e, opcionalmente, um tool para a LLM."""
from capoeira_agent.core.command import Command, ToolDef


class ExampleCommand(Command):
    name = "example"
    description = "Comando de exemplo criado pelo /init"
    tool_def = ToolDef(name="example", desc="Exemplo de comando remoto.", args={"arg1": "string"})

    def execute(self, args):
        print("example:", args)

    def execute_remote(self, params):
        return f"ok: recebido {params}"
'''

README_AGENT = """# CapoeiraAgent — projeto

Este diretório é acompanhado pelo CapoeiraAgent.

- `specs/` e `skills/`: instruções injetadas no chat web pelo `/inject-environment`.
- `commands/`: plugins do projeto (cada um pode expor um comando à LLM via `tool_def`).
- `.capoeira-agent/`: estado local de runtime do agente.

Uso:

    capoeira-agent "."
    /init                  # (re)cria estes artefatos
    /inject-environment    # envia ambiente + dicionário de comandos ao chat ativo
    /listen                # monitora o clipboard (copie a resposta da LLM com Ctrl+C)
"""


def init_project(project_root: Path, write_commands_example: bool = True) -> list[Path]:
    """Cria os artefatos iniciais na raiz do projeto. Retorna os caminhos criados."""
    root = Path(project_root)
    root.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []

    def _write(rel: str, content: str) -> None:
        target = root / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            created.append(target)

    _write("specs/project.md", SPEC_EXAMPLE)
    _write("skills/procedure.md", SKILL_EXAMPLE)
    if write_commands_example:
        _write("commands/example.py", PLUGIN_EXAMPLE)
    _write("README-agente.md", README_AGENT)
    runtime = root / ".capoeira-agent"
    if not runtime.exists():
        runtime.mkdir()
        created.append(runtime)
    return created