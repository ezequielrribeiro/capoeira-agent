"""Listener — recebe o push do host (via receiver) e faz o round-trip de tools via /api/chat."""
from __future__ import annotations

import threading
import time

from .executor import ToolResult
from .receiver import PushReceiver
from .steps import Step, parse_tool_calls

MAX_ROUNDS = 12
_SEEN_REQUEST_LIMIT = 64
_DUPLICATE_WINDOW_S = 5.0
_TURN_WINDOW_S = 30.0
_SEEN_TURN_LIMIT = 128


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
        self._seen_request_ids: list[str] = []
        self._last_signature: tuple[str, ...] | None = None
        self._last_signature_at = 0.0
        self._recent_turns: list[tuple[str, float]] = []
        self._outstanding: list[str] = []

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
        assistente e, se houver [TOOL_CALL], executa as tools e reenvia APENAS
        o resultado do turno ao modelo (fire-and-forget).

        O histórico da sessão não é reenviado: com ``new_chat=false`` o chat web
        já contém o ambiente/contrato e os ``[TOOL_CALL]`` anteriores — reenviá-los
        faria o modelo reler os próprios comandos e entrar em loop."""
        try:
            error = payload.get("error")
            if error:
                self._emit(f"[red]erro do modelo: {error}[/red]")
                return
            request_id = payload.get("request_id")
            if request_id and not self._claim_request(str(request_id)):
                self._emit(f"[dim]push ignorado (request_id já processado: {request_id})[/dim]")
                return
            solicited = bool(request_id) and self._take_outstanding(str(request_id))
            text = (payload.get("text") or "").strip()
            if not text:
                return
            self._append_round_reply(text)
            steps = [s for s in parse_tool_calls(text) if s.tool != "done"]
            if not steps:
                self._round_count = 0
                return
            if self._duplicate_block(steps) or self._duplicate_turn(text):
                self._emit("[yellow]turno de [TOOL_CALL] idêntico a um já tratado — "
                           "não reexecutando (proteção anti-loop)[/yellow]")
                return
            if self._round_count >= MAX_ROUNDS:
                self._emit("[red]limite de rounds de tool atingido — encerrando turno[/red]")
                self._round_count = 0
                return
            self._round_count += 1
            origin = "" if solicited else "[dim](turno digitado na Web) [/dim]"
            recognized = [s for s in steps if self.executor.known_tool(s.tool)]
            if recognized:
                self.listen_messages.append(f"tool-calls executados: {len(recognized)}")
                self._emit(f"{origin}executando {len(recognized)} comando(s): "
                           f"{', '.join(s.tool for s in recognized)}")
            messages = self._tool_results_to_messages(steps)
            if not messages:
                return
            reply = self.client.chat(messages, new_chat=False)
            if reply.request_id:
                self._track_request(reply.request_id)
        except Exception as exc:
            msg = f"processamento do push falhou: {exc}"
            self.listen_messages.append(msg)
            self._emit(f"[red]{msg}[/red]")

    # -- proteção anti-loop --------------------------------------------------
    def _claim_request(self, request_id: str) -> bool:
        """True se o request_id ainda não foi processado (e o registra).

        Evita tratar duas vezes o mesmo push (redelivery do host)."""
        with self._lock:
            if request_id in self._seen_request_ids:
                return False
            self._seen_request_ids.append(request_id)
            if len(self._seen_request_ids) > _SEEN_REQUEST_LIMIT:
                del self._seen_request_ids[:-_SEEN_REQUEST_LIMIT]
            return True

    def _duplicate_block(self, steps: list[Step]) -> bool:
        """True se o bloco de [TOOL_CALL] é idêntico ao último detectado há
        poucos segundos (eco do watcher sobre um turno já tratado)."""
        now = time.monotonic()
        signature = tuple(s.line for s in steps)
        with self._lock:
            duplicate = (
                signature == self._last_signature
                and (now - self._last_signature_at) <= _DUPLICATE_WINDOW_S
            )
            self._last_signature = signature
            self._last_signature_at = now
        return duplicate

    def _duplicate_turn(self, text: str) -> bool:
        """True se o texto do turno (normalizado) já foi tratado há pouco.

        Pega o eco do watcher mesmo quando o bloco de ``[TOOL_CALL]`` vem com
        entorno diferente (prosa, espaços) da resposta original."""
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

    def _track_request(self, request_id: str) -> None:
        """Registra o request_id de uma geração disparada pelo agente, para
        distinguir respostas solicitadas de turnos espontâneos (watcher)."""
        with self._lock:
            self._outstanding.append(request_id)
            if len(self._outstanding) > _SEEN_REQUEST_LIMIT:
                del self._outstanding[:-_SEEN_REQUEST_LIMIT]

    def _take_outstanding(self, request_id: str) -> bool:
        """True (e remove) se o request_id é resposta de uma geração do agente."""
        with self._lock:
            if request_id in self._outstanding:
                self._outstanding.remove(request_id)
                return True
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
