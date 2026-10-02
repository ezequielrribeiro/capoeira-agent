"""Execução de comandos [TOOL_CALL] a partir do texto colado na TUI.

A entrada dos comandos é a própria interface do agente: o usuário cola o texto
da resposta da LLM (com as linhas ``[TOOL_CALL]``) em ``/exec`` e o agente faz o
parse, aplica o permission gate, executa e devolve o resultado à LLM via
``/api/chat`` (round-trip, ``new_chat=False``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .executor import Executor, ToolResult
from .steps import Step, parse_tool_calls

MAX_ROUNDS = 12


@dataclass
class ExecOutcome:
    """Resultado de um bloco de [TOOL_CALL] processado."""

    steps: list[Step] = field(default_factory=list)
    executed: list[tuple[str, bool, ToolResult]] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    roundtrip_sent: bool = False
    roundtrip_reply: str = ""

    @property
    def any_recognized(self) -> bool:
        return bool(self.executed)


class Runner:
    """Executa [TOOL_CALL] com gate de permissão e monta o round-trip."""

    def __init__(self, session, gate, executor, registry, client, on_event=None) -> None:
        self.session = session
        self.gate = gate
        self.executor = executor
        self.registry = registry
        self.client = client
        self.on_event = on_event
        self._round_count = 0

    def _emit(self, text: str) -> None:
        if self.on_event is not None:
            self.on_event(text)

    def run_text(self, text: str, *, send_roundtrip: bool = True) -> ExecOutcome:
        """Processa um texto com [TOOL_CALL]: executa e (opcional) faz round-trip."""
        outcome = ExecOutcome()
        steps = [s for s in parse_tool_calls(text or "") if s.tool != "done"]
        outcome.steps = steps
        if not steps:
            return outcome

        if self._round_count >= MAX_ROUNDS:
            self._emit("[red]limite de rounds de tool atingido — encerrando turno[/red]")
            self._round_count = 0
            return outcome

        for idx, step in enumerate(steps):
            if not self.executor.known_tool(step.tool):
                outcome.unknown.append(step.tool)
                self._emit(f"[yellow]comando não reconhecido: '{step.tool}'[/yellow]")
                self.session.approval(step.tool, False)
                continue
            allowed, result = self._run_step(step, idx)
            outcome.executed.append((step.tool, allowed, result))
            msg = {"role": "tool", "content": self._result_text(result),
                   "tool_call_id": f"call_{idx}"}
            if not allowed:
                msg["content"] = f"[DENEGADO] comando '{step.tool}' negado pelo usuário"
            outcome.messages.append(msg)

        if not outcome.messages:
            return outcome
        self._round_count += 1
        if send_roundtrip:
            self.send_roundtrip(outcome)
        return outcome

    def send_roundtrip(self, outcome: ExecOutcome) -> None:
        """Envia ao modelo apenas os resultados do turno (fire do round-trip)."""
        if not outcome.messages or self.client is None:
            return
        reply = self.client.chat(outcome.messages, new_chat=False)
        outcome.roundtrip_sent = True
        outcome.roundtrip_reply = reply.content

    def reset_rounds(self) -> None:
        self._round_count = 0

    def _run_step(self, step: Step, idx: int) -> tuple[bool, ToolResult]:
        dec = self.gate.decide(step, self.registry)
        if dec.action == "deny":
            result = ToolResult(False, error=f"negado: {dec.reason}")
            allowed = False
        elif dec.action == "auto":
            result = self.executor.apply(step)
            allowed = True
        else:
            allowed, _ = self.gate.ask(step)
            if allowed:
                result = self.executor.apply(step)
            else:
                result = ToolResult(False, error="negado pelo usuário (n)")
        self.session.approval(step.tool, allowed)
        if result.ok:
            self._emit(f"ok: {step.tool}")
        else:
            self._emit(f"[red]falha: {step.tool}: {result.error or result.output}[/red]")
        return allowed, result

    @staticmethod
    def _result_text(result: ToolResult) -> str:
        if result.ok:
            return result.output
        return f"ERRO: {result.error or result.output}"
