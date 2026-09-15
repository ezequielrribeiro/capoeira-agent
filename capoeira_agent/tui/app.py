"""TUI do CapoeiraAgent — monitoramento, aprovações e comandos de ferramenta/plugins."""
from __future__ import annotations

import contextlib
import io
import queue
import sys
import threading
from dataclasses import dataclass, field

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from rich.console import Console

from capoeira_agent.core.parser import parse_line

STYLE = "bold cyan"
HINT = "capoeira-agent> "


@dataclass
class ApprovalRequest:
    tool: str
    params: dict
    event: threading.Event = field(default_factory=threading.Event)
    answer: str = "n"

    def finish(self, answer: str) -> None:
        self.answer = answer
        self.event.set()


class Tui:
    def __init__(self, config, session, registry, permissions, client, executor, listener=None,
                 project_root=None, prompt_override=None) -> None:
        self.config = config
        self.session = session
        self.registry = registry
        self.permissions = permissions
        self.client = client
        self.executor = executor
        self.listener = listener
        self.project_root = project_root
        self.prompt_override = prompt_override  # callable(tool, params) -> "y"/"n"/"a" (testes)

        self.console = Console()
        self.events: queue.Queue[str] = queue.Queue()
        self._approvals: list[ApprovalRequest] = []
        self._approval_lock = threading.Lock()
        self._running = True

    # -- eventos / aprovações ------------------------------------------------
    def event(self, text: str) -> None:
        self.events.put(text)

    def ask_approval(self, tool: str, params: dict) -> str:
        """Bloqueante: registra uma aprovação pendente e aguarda a TUI responder."""
        if self.prompt_override is not None:
            return self.prompt_override(tool, params)
        if not sys.stdin.isatty():
            return "n"
        req = ApprovalRequest(tool=tool, params=params)
        with self._approval_lock:
            self._approvals.append(req)
        self.event(f"[aprovação pendente] permitir '{tool}'? digite y/n/a")
        req.event.wait()
        return req.answer

    def _service_approvals(self) -> None:
        with self._approval_lock:
            pending = list(self._approvals)
            self._approvals = []
        if not pending:
            return
        ps = PromptSession(patch_stdout=True)
        for req in pending:
            try:
                answer = ps.prompt(
                    f"Permitir comando '[bold]{req.tool}[/bold]' da LLM? [y/n/a: permitir / negar / "
                    f"permitir sempre na sessão] ",
                    style="bold yellow",
                )
            except (KeyboardInterrupt, EOFError):
                answer = "n"
            req.finish(answer.strip().lower() or "n")
            self.event(f"aprovação '{req.tool}': {answer or 'n'}")

    # -- saída ---------------------------------------------------------------
    def _drain_events(self) -> None:
        while True:
            try:
                item = self.events.get_nowait()
            except queue.Empty:
                break
            self.console.print(item)

    def _toolbar(self) -> str:
        listen = "ON" if self.listener is not None and self.listener.listening else "off"
        with self._approval_lock:
            pend = len(self._approvals)
        return (f"[bold]{self.config.host.model}[/bold] · "
                f"policy={self.permissions.mode} · listen={listen} · "
                f"session={self.session.session_name} · pendentes={pend}")

    # -- loop principal ------------------------------------------------------
    def run(self) -> None:
        completer = WordCompleter(self.registry.names(), ignore_case=False)
        self.event(f"CapoeiraAgent — escutando execução de comandos da LLM via {self.config.host.base_url}")
        self.event(f"Política: {self.permissions.mode} · modelo: {self.config.host.model} · "
                   f"new_chat={self.config.host.new_chat}")
        self.event("Comandos: /help · /init · /inject-environment · /listen · /status · /quit")

        ps = PromptSession(patch_stdout=True)

        def _prompt() -> str:
            try:
                return ps.prompt(HINT, completer=completer, bottom_toolbar=self._toolbar)
            except KeyboardInterrupt:
                return ""
            except EOFError:
                self._running = False
                return ""

        while self._running:
            self._drain_events()
            self._service_approvals()
            if not self._running:
                break
            line = _prompt()
            self._service_approvals()
            if not self._running:
                break
            self._drain_events()
            if not line.strip():
                continue
            self._dispatch(line)

        self._shutdown()

    def quit(self) -> None:
        self._running = False

    def _dispatch(self, line: str) -> None:
        name, args = parse_line(line)
        if not name:
            self.console.print("[dim]A TUI não envia prompts ao LLM — converse na interface web; "
                               "use /... para comandos locais.[/dim]")
            return
        cmd = self.registry.get(name)
        if cmd is None:
            self.console.print(f"[red]comando desconhecido: {name}[/red] (use /help)")
            return
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                cmd.execute(args)
            except Exception as exc:
                self.console.print(f"[red]{name} falhou: {exc}[/red]")
                return
        output = buf.getvalue().strip()
        if output:
            self.console.print(output)

    def _shutdown(self) -> None:
        if self.listener is not None and self.listener.listening:
            self.listener.stop()
        self.session.save_state()