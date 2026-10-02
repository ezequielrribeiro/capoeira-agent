"""Listener — monitora o clipboard e executa os [TOOL_CALL] vindos do chat web.

Comunicação unidirecional: o CapoeiraHost é usado **apenas para injetar** texto
no LLM web (``/inject-environment`` e o round-trip de resultados). O retorno não
usa mais push/HTTP: o usuário copia a resposta do chat (Ctrl+C) para o clipboard
e o agente detecta a mudança, faz o parse dos ``[TOOL_CALL]`` e executa.

O host não registra aplicação e não há API local no agente (sem receiver).
"""
from __future__ import annotations

import threading
import time

from .clipboard import read_clipboard
from .executor import ToolResult
from .steps import Step, parse_tool_calls

MAX_ROUNDS = 12
_TURN_WINDOW_S = 30.0
_SEEN_TURN_LIMIT = 128


class Listener:
    def __init__(self, client, session, gate, executor, registry, *,
                 poll_interval: float = 0.5, inject_environment=None, on_turn=None,
                 on_event=None, new_chat=False, debug: bool = False) -> None:
        self.client = client
        self.session = session
        self.gate = gate
        self.executor = executor
        self.registry = registry
        self.poll_interval = poll_interval
        self.inject_environment = inject_environment  # callable() -> str
        self.on_turn = on_turn  # callable(tool, params, result, allowed) p/ monitor/TUI
        self.on_event = on_event  # callable(text) p/ feedback em tempo real na TUI
        self.new_chat = new_chat
        self.debug = debug
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._round_count = 0
        self.listen_messages: list[str] = []
        self._lock = threading.Lock()
        self._baseline: str | None = None
        self._recent_turns: list[tuple[str, float]] = []

    # -- controle ------------------------------------------------------------
    @property
    def listening(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        if self.listening:
            return "monitor já ativo"
        self._baseline = self._current_clipboard()
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="capoeira-clipboard", daemon=True)
        self._thread.start()
        self._emit(f"monitor de clipboard iniciado (intervalo {self.poll_interval:g}s)")
        return "monitor iniciado"

    def stop(self) -> str:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        self._thread = None
        self._emit("monitor de clipboard encerrado")
        return "monitor encerrado"

    # -- monitoramento -------------------------------------------------------
    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_interval):
            try:
                text = self._current_clipboard()
                if text is None:
                    continue
                if text == self._baseline:
                    continue
                self._baseline = text
                if not text.strip():
                    continue
                if self.debug:
                    preview = text.strip().replace("\n", " ")[:120]
                    self._emit(f"[dim]clipboard mudou: {preview!r}[/dim]")
                self.handle_response(text)
            except Exception as exc:  # noqa: BLE001 - thread nunca deve morrer silenciosamente
                self._emit(f"[red]falha ao ler o clipboard: {exc}[/red]")

    @staticmethod
    def _current_clipboard() -> str | None:
        try:
            return read_clipboard()
        except Exception:
            return None

    def _emit(self, text: str) -> None:
        if self.on_event is not None:
            self.on_event(text)

    # -- processamento do clipboard -----------------------------------------
    def handle_response(self, text: str) -> None:
        """Processa um turno copiado do chat web. Espelha o texto e, se houver
        [TOOL_CALL], executa as tools e envia APENAS o resultado do turno ao
        modelo (round-trip via /api/chat, new_chat=False).

        O histórico da sessão não é reenviado: com ``new_chat=false`` o chat web
        já contém o ambiente/contrato e os ``[TOOL_CALL]`` anteriores — reenviá-los
        faria o modelo reler os próprios comandos e entrar em loop."""
        try:
            text = (text or "").strip()
            if not text:
                return
            steps = [s for s in parse_tool_calls(text) if s.tool != "done"]
            if not steps:
                return
            if self._duplicate_turn(text):
                self._emit("[yellow]turno de [TOOL_CALL] idêntico a um já tratado — "
                           "não reexecutando (proteção anti-loop)[/yellow]")
                return
            if self._round_count >= MAX_ROUNDS:
                self._emit("[red]limite de rounds de tool atingido — encerrando turno[/red]")
                self._round_count = 0
                return
            self._round_count += 1
            self._append_round_reply(text)
            recognized = [s for s in steps if self.executor.known_tool(s.tool)]
            if recognized:
                self.listen_messages.append(f"tool-calls executados: {len(recognized)}")
                self._emit(f"executando {len(recognized)} comando(s): "
                           f"{', '.join(s.tool for s in recognized)}")
            messages = self._tool_results_to_messages(steps)
            if not messages:
                return
            self.client.chat(messages, new_chat=False)
        except Exception as exc:
            msg = f"processamento do clipboard falhou: {exc}"
            self.listen_messages.append(msg)
            self._emit(f"[red]{msg}[/red]")

    # -- proteção anti-loop --------------------------------------------------
    def _duplicate_turn(self, text: str) -> bool:
        """True se o texto do turno (normalizado) já foi tratado há pouco.

        Pega re-cópias do mesmo turno (o usuário copia de novo, o clipboard
        recebe a resposta duas vezes) sem reexecutar o comando."""
        normalized = " ".join(text.split())
        now = time.monotonic()
        with self._lock:
            self._recent_turns = [(t, ts) for (t, ts) in self._recent_turns
                                  if now - ts <= _TURN_WINDOW_S]
            if any(t == normalized for t, _ in self._recent_turns):
                return True
            self._recent_turns.append((normalized, now))
            if len(self._recent_turns) > _SEEN_TURN_LIMIT:
                del self._recent_turns[:-_SEEN_TURN_LIMIT]
            return False

    def _tool_results_to_messages(self, steps: list[Step]) -> list[dict] | None:
        """Converte os steps executados em mensagens role=tool do turno atual.

        Retorna APENAS os resultados deste turno — nunca o histórico da sessão,
        nunca o header do /inject-environment nem [TOOL_CALL] anteriores.
        Comandos não reconhecidos são apenas exibidos na TUI — nunca reenviados
        ao modelo (evita loop)."""
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
            msg = {"role": "tool", "content": self._result_text(result), "tool_call_id": f"call_{idx}"}
            if not allowed:
                msg["content"] = f"[DENEGADO] comando '{step.tool}' negado pelo usuário"
            tool_msgs.append(msg)
        if not tool_msgs:
            return None
        return tool_msgs

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
