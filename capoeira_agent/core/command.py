"""Classe base de comandos/plugins (estilo Crivonansky)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolDef:
    """Definição de tool exposta à LLM (dicionário de comandos do /inject-environment)."""

    name: str
    desc: str = ""
    args: dict[str, str] = field(default_factory=dict)
    auto: bool = False  # True => execução sem perguntar (categoria de leitura, etc.)

    def to_dict(self) -> dict:
        return {"name": self.name, "desc": self.desc, "args": dict(self.args)}


class Command(ABC):
    name: str = ""
    description: str = ""
    tool_def: ToolDef | None = None  # presente => invocável pela LLM

    def __init__(self) -> None:
        self.context: "AgentContext | None" = None  # type: ignore[name-defined]

    @abstractmethod
    def execute(self, args: list[str]) -> None:
        """Executa o comando a partir da TUI. Pode imprimir com print()."""

    def execute_remote(self, params: dict[str, str]) -> str:
        """Executa o comando a partir de uma chamada da LLM ([TOOL_CALL])."""
        raise NotImplementedError(f"comando '{self.name}' não é invocável remotamente")


class AgentContext:
    """Injeção de dependências disponível a todos os comandos (self.context)."""

    def __init__(self, config, session, client, registry, permissions, tui, project_root):
        self.config = config
        self.session = session
        self.client = client
        self.registry = registry
        self.permissions = permissions
        self.tui = tui
        self.project_root = project_root
        self.listener = None

    def echo(self, text: str) -> None:
        if self.tui is not None:
            self.tui.event(text)
        else:
            print(text)