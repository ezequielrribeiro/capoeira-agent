"""Registro central de comandos + serialização do dicionário de tools para a LLM."""
from __future__ import annotations

from .. import toolsdef
from .command import Command, ToolDef


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, name: str, command: Command) -> None:
        self._commands[name] = command

    def register_many(self, commands: list[Command]) -> None:
        for cmd in commands:
            self._commands[cmd.name] = cmd

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def all(self) -> dict[str, Command]:
        return dict(self._commands)

    def names(self) -> list[str]:
        return sorted(self._commands)

    def tool_definitions(self) -> list[dict]:
        """Tools core + tools dos comandos-plugin que declaram tool_def."""
        tools: list[dict] = [dict(t) for t in toolsdef.CORE_TOOL_DEFS]
        for cmd in self._commands.values():
            td = cmd.tool_def
            if td is not None:
                tools.append(td.to_dict())
        return tools

    def get_tool(self, name: str) -> dict | None:
        for td in toolsdef.CORE_TOOL_DEFS:
            if td["name"] == name:
                return td
        for cmd in self._commands.values():
            td = cmd.tool_def
            if td is not None and td.name == name:
                return td.to_dict()
        return None

    def tool_is_auto(self, name: str) -> bool:
        """True se o comando-plugin correspondente foi marcado tool_def.auto."""
        for cmd in self._commands.values():
            td = cmd.tool_def
            if td is not None and td.name == name:
                return bool(td.auto)
        return False