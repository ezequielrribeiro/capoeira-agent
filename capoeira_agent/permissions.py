"""Política de permissão: auto/ask/readonly + y/n/a ('a' = sempre na sessão)."""
from __future__ import annotations

from dataclasses import dataclass

READ_TOOLS = {"read_file", "list_dir"}
REMOTE_ONLY = {"done"}
ASK_CORE_TOOLS = {"run_shell", "run_python", "write_file"}


@dataclass
class Decision:
    action: str  # "auto" | "question" | "deny"
    reason: str = ""


class PermissionGate:
    def __init__(self, mode: str = "ask", ask_user: callable | None = None) -> None:
        self.mode = mode
        self.ask_user = ask_user or (lambda tool, params: True)
        self.session_allow: set[str] = set()  # nomes aprovados 'a' (sempre na sessão)

    def set_mode(self, mode: str) -> None:
        if mode in ("auto", "ask", "readonly"):
            self.mode = mode

    def _is_plugin_tool(self, tool: str, registry) -> bool:
        td = registry.get_tool(tool) if registry is not None else None
        return td is not None

    def decide(self, step, registry=None) -> Decision:
        """Leitura é automática; escrita/execução conforme política."""
        tool = step.tool
        if tool in READ_TOOLS:
            return Decision("auto", "leitura automática")
        if tool == "ask_user":
            return Decision("auto", "ask_user vira contexto (bloqueante)")
        if tool == "done":
            return Decision("auto", "encerra turno")
        # plugin com tool_def marcado auto
        if registry is not None and registry.tool_is_auto(tool):
            return Decision("auto", "tool marcada como automática")
        if self.mode == "readonly":
            return Decision("deny", "modo readonly (apenas leitura)")
        if tool in self.session_allow:
            return Decision("auto", "aprovado para a sessão")
        if self.mode == "auto":
            return Decision("auto", "independente: modo auto")
        return Decision("question", f"comando '{tool}' requer aprovação")

    def ask(self, step) -> tuple[bool, str | None]:
        """Pergunta ao usuário na TUI. Retorna (permitir, sempre_na_sessao|None)."""
        answer = self.ask_user(step.tool, step.params).strip().lower()
        if answer in ("a", "s"):
            self.session_allow.add(step.tool)
            return True, "always"
        return answer in ("y", ""), None

    def reset_session(self) -> None:
        self.session_allow.clear()