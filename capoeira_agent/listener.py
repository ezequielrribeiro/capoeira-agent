"""Listener — recebe o push do host (via receiver) e faz o round-trip de tools via /api/chat."""
from __future__ import annotations

import threading

from .executor import ToolResult
from .receiver import PushReceiver
from .steps import Step, parse_tool_calls

MAX_CONTEXT_MESSAGES = 60
MAX_ROUNDS = 12


class Listener:
    def __init__(self, client, session, gate, executor, registry, *,
                 app_host="127.0.0.1", app_port=8767, app_path="/api/capoeira/response",
                 inject_environment=None, on_turn=None, on_event=None, new_chat=False) -> None:
        self.client = client
        self.session = session
        self.gate = gate
        self.executor = executor
        self.registry = registry
        self.app_host = app_host
        self.app_port = app_port
        self.app_path = app_path
        self.inject_environment = inject_environment  # callable() -> str
        self.on_turn = on_turn  # callable(tool, params, result, allowed) p/ monitor/TUI
        self.on_event = on_event  # callable(text) p/ feedback em tempo real na TUI
        self.new_chat = new_chat

        self._receiver = PushReceiver(self.handle_response, host=app_host, port=app_port)
        self._round_count = 0
        self.listen_messages: list[str] = []
        self._lock = threading.Lock()

    # -- controle ------------------------------------------------------------
    @property
    def listening(self) -> bool:
        return self._receiver.listening

    def start(self) -> str:
        if self.listening:
            return "listener já ativo"
        self._receiver.start()
        self._emit(f"escuta iniciada (push em {self.app_host}:{self.app_port}{self.app_path})")
        try:
            self.client.register_app(self.app_port, host=self.app_host, name="capoeira-agent")
            self._emit("aplicação registrada no host como destino do push")
        except Exception as exc:
            self._emit(f"[yellow]registro no host falhou (continua escutando): {exc}[/yellow]")
        return "escuta iniciada"

    def stop(self) -> str:
        try:
            self.client.unregister_app()
        except Exception:
            pass
        self._receiver.stop()
        self._emit("escuta encerrada")
        return "escuta encerrada"

    def _emit(self, text: str) -> None:
        if self.on_event is not None:
            self.on_event(text)

    # -- processamento do push ----------------------------------------------
    def handle_response(self, payload: dict) -> None:
        """Chamado pelo receiver a cada push do host. Espelha o turno do
        assistente e, se houver [TOOL_CALL], executa as tools e reenvia o
        resultado ao modelo (fire-and-forget)."""
        try:
            error = payload.get("error")
            if error:
                self._emit(f"[red]erro do modelo: {error}[/red]")
                return
            text = (payload.get("text") or "").strip()
            if not text:
                return
            self._append_round_reply(text)
            steps = [s for s in parse_tool_calls(text) if s.tool != "done"]
            if not steps:
                self._round_count = 0
                return
            if self._round_count >= MAX_ROUNDS:
                self._emit("[red]limite de rounds de tool atingido — encerrando turno[/red]")
                self._round_count = 0
                return
            self._round_count += 1
            messages = self._tool_results_to_messages(steps)
            if not messages:
                return
            self.listen_messages.append(f"tool-calls executados: {len(steps)}")
            self._emit(f"executando {len(steps)} comando(s): {', '.join(s.tool for s in steps)}")
            self.client.chat(messages, new_chat=self.new_chat)
        except Exception as exc:
            msg = f"processamento do push falhou: {exc}"
            self.listen_messages.append(msg)
            self._emit(f"[red]{msg}[/red]")

    def _tool_results_to_messages(self, steps: list[Step]) -> list[dict] | None:
        """Converte steps executados em mensagens role=tool para o round-trip.
        Comandos não reconhecidos são apenas exibidos na TUI — nunca reenviados
        ao modelo (evita loop)."""
        messages_base = self.session.messages()
        tool_msgs: list[dict] = []
        for idx, step in enumerate(steps):
            if step.tool == "done":
                continue  # encerra o turno; não é executado nem reenviado
            if not self.executor.known_tool(step.tool):
                self._emit(f"[yellow]comando não reconhecido: '{step.tool}' — exibido na TUI, "
                           f"sem reenvio ao modelo[/yellow]")
                self.session.approval(step.tool, False)
                continue
            allowed, result = self._run_step(step, idx)
            msg = {"role": "tool", "content": self._result_text(result)}
            if not allowed:
                msg["content"] = f"[DENEGADO] comando '{step.tool}' negado pelo usuário"
                msg["tool_call_id"] = f"call_{idx}"
            else:
                msg["tool_call_id"] = f"call_{idx}"
            tool_msgs.append(msg)
        if not tool_msgs:
            return None
        messages = (messages_base + tool_msgs)[-MAX_CONTEXT_MESSAGES:]
        return messages

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
        if self.on_turn is not None:
            self.on_turn(step.tool, step.params, result, allowed)
        if result.ok:
            self._emit(f"ok: {step.tool}")
        else:
            self._emit(f"[red]falha: {step.tool}: {result.error or result.output}[/red]")
        return allowed, result

    def _result_text(self, result: ToolResult) -> str:
        if result.ok:
            return result.output
        return f"ERRO: {result.error or result.output}"

    def _append_round_reply(self, content: str) -> None:
        if not content:
            return
        self.session.append_message("assistant", content)
