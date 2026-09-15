"""Listener — loop de escuta (watch long-poll) + round-trip de tools via /api/chat."""
from __future__ import annotations

import threading

from .executor import ToolResult
from .llm_client import parse_delta_lines
from .steps import Step, parse_tool_calls

MAX_CONTEXT_MESSAGES = 60


class Listener:
    def __init__(self, client, session, gate, executor, registry, *, watch_timeout=30,
                 inject_environment=None, on_turn=None, new_chat=False) -> None:
        self.client = client
        self.session = session
        self.gate = gate
        self.executor = executor
        self.registry = registry
        self.watch_timeout = watch_timeout
        self.inject_environment = inject_environment  # callable() -> str
        self.on_turn = on_turn  # callable(tool, params, result, allowed) p/ monitor/TUI
        self.new_chat = new_chat

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.listen_messages: list[str] = []
        self._lock = threading.Lock()

    # -- controle ------------------------------------------------------------
    @property
    def listening(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        if self.listening:
            return "listener já ativo"
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="capoeira-listener", daemon=True)
        self._thread.start()
        return "escuta iniciada"

    def stop(self) -> str:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.watch_timeout + 5)
            self._thread = None
        return "escuta encerrada"

    # -- loop ----------------------------------------------------------------
    def _loop(self) -> None:
        try:
            if self.inject_environment is not None:
                self.inject_environment()
            while not self._stop.is_set():
                try:
                    delta, new_revision = self.client.watch(self.session.revision, self.watch_timeout)
                except Exception as exc:
                    self.listen_messages.append(f"watch falhou: {exc}")
                    if self._stop.wait(2):  # backoff curto
                        break
                    continue
                if not delta:
                    continue
                self.session.revision = new_revision
                self.session.save_state()
                self._process_delta(delta, new_revision)
        except Exception as exc:  # erro fatal no loop
            self.listen_messages.append(f"listener encerrado por erro: {exc}")

    # -- processamento -------------------------------------------------------
    def _process_delta(self, delta: str, revision: int) -> None:
        turns = parse_delta_lines(delta)
        for role, content in turns:
            self.session.append_message(role, content, revision=revision)
        self.listen_messages.append(f"delta [{revision}]: {len(turns)} turno(s)")
        # procura [TOOL_CALL] entre turnos de assistente
        assistant_text = "\n".join(c for r, c in turns if r == "assistant")
        if assistant_text and "[TOOL_CALL]" in assistant_text:
            self._run_tool_round(assistant_text)

    def _run_tool_round(self, assistant_text: str) -> None:
        steps = parse_tool_calls(assistant_text)
        if not steps:
            return
        # 'done' apenas encerra o turno — não é executado
        steps = [s for s in steps if s.tool != "done"]
        if not steps:
            return
        messages = self._tool_results_to_messages(steps)
        if not messages:
            return
        self.listen_messages.append(f"tool-calls executados: {len(steps)}")
        self._send_round(messages)

    def _tool_results_to_messages(self, steps: list[Step]) -> list[dict] | None:
        messages_base = self.session.messages()
        tool_msgs: list[dict] = []
        for idx, step in enumerate(steps):
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
        return allowed, result

    def _result_text(self, result: ToolResult) -> str:
        if result.ok:
            return result.output
        return f"ERRO: {result.error or result.output}"

    def _send_round(self, messages: list[dict]) -> None:
        tools = self.registry.tool_definitions()
        for _ in range(12):  # proteção contra loop infinito de tool calls
            reply = self.client.chat(messages, tools=tools, new_chat=self.new_chat)
            self._append_round_reply(reply.content)
            steps = parse_tool_calls(reply.content)
            if not steps:
                break
            more = self._tool_results_to_messages(steps)
            if not more:
                break
            messages = (messages + more)[-MAX_CONTEXT_MESSAGES:]

    def _append_round_reply(self, content: str) -> None:
        if not content:
            return
        self.session.append_message("assistant", content)