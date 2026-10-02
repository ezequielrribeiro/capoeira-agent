"""TUI do CapoeiraAgent — monitoramento, aprovações e comandos de ferramenta/plugins."""
from __future__ import annotations

import contextlib
import io
import queue
import re
import sys
import threading
from dataclasses import dataclass, field

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from rich.console import Console

from capoeira_agent.core.parser import parse_line

STYLE = "bold cyan"
HINT = "capoeira-agent> "


class _LiveStdout:
    """Encaminha para o sys.stdout vigente a cada chamada. Assim os prints dos
    comandos saem pelo StdoutProxy do patch_stdout durante a TUI e a
    formatação rich/prompt_toolkit não é corrompida (sem sequências \x1b soltas)."""

    def write(self, data: str) -> int:
        sys.stdout.write(data)
        return len(data)

    def flush(self) -> None:
        sys.stdout.flush()

    def isatty(self) -> bool:
        return sys.stdout.isatty()

    def __getattr__(self, name):
        return getattr(sys.stdout, name)


_STYLE_TAG = re.compile(
    r"\[/?(?:bold|dim|red|yellow|green|cyan|magenta|blue|white|bright_[a-z]+"
    r"|underline|italic)\b[^\]]*\]",
    re.IGNORECASE,
)


def _plain(text: str) -> str:
    """Remove tags de estilo rich ([red], [dim], ...) preservando marcadores de
    conteúdo como [TOOL_CALL]/[USER], para que as linhas saiam legíveis mesmo sob
    o patch_stdout (que não renderiza ANSI de outra thread)."""
    return _STYLE_TAG.sub("", text)


def approval_style() -> Style:
    """Estilo do prompt de aprovações como objeto Style (str quebra no
    prompt_toolkit 3.0.53: 'str' object has no attribute 'invalidation_hash')."""
    return Style.from_dict({"": "bold yellow"})


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
    def __init__(self, config, session, registry, permissions, client, executor, runner=None,
                 project_root=None, prompt_override=None) -> None:
        self.config = config
        self.session = session
        self.registry = registry
        self.permissions = permissions
        self.client = client
        self.executor = executor
        self.runner = runner
        self.project_root = project_root
        self.prompt_override = prompt_override  # callable(tool, params) -> "y"/"n"/"a" (testes)

        self.console = Console(file=_LiveStdout(), highlight=False)
        self.events: queue.Queue[str] = queue.Queue()
        self._approvals: list[ApprovalRequest] = []
        self._approval_lock = threading.Lock()
        self._running = True

    # -- eventos / aprovações ------------------------------------------------
    def event(self, text: str) -> None:
        """Registra e imprime um evento. Chamável de outras threads: com
        patch_stdout ativo, a linha aparece acima do prompt em tempo real."""
        self.events.put(text)
        self.console.print(_plain(text))

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
        ps = PromptSession()
        with patch_stdout():
            for req in pending:
                try:
                    answer = ps.prompt(
                        f"Permitir comando '[bold]{req.tool}[/bold]' da LLM? [y/n/a: permitir / negar / "
                        f"permitir sempre na sessão] ",
                        style=approval_style(),
                    )
                except (KeyboardInterrupt, EOFError):
                    answer = "n"
                req.finish(answer.strip().lower() or "n")
                self.event(f"aprovação '{req.tool}': {answer or 'n'}")

    # -- saída ---------------------------------------------------------------
    def _drain_events(self) -> None:
        """Limpa a fila de eventos (já impressos por event()); evita backlog."""
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break

    def _toolbar(self) -> str:
        with self._approval_lock:
            pend = len(self._approvals)
        return (f"[bold]{self.config.host.model}[/bold] · "
                f"policy={self.permissions.mode} · "
                f"session={self.session.session_name} · pendentes={pend}")

    # -- loop principal ------------------------------------------------------
    def run(self) -> None:
        completer = WordCompleter(self.registry.names(), ignore_case=False)
        self.event(f"CapoeiraAgent — host em {self.config.host.base_url}")
        self.event(f"Política: {self.permissions.mode} · modelo: {self.config.host.model} · "
                   f"new_chat={self.config.host.new_chat}")
        self.event("Comandos: /help · /init · /inject-environment · /exec · /status · /quit · "
                   "use /exec para colar a resposta da LLM e executar os [TOOL_CALL].")

        ps = PromptSession()

        def _prompt() -> str:
            try:
                with patch_stdout():
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
            self.console.print("[dim]A TUI não envia prompts ao LLM — converse na interface web e "
                               "use /exec para executar a resposta; /... para comandos locais.[/dim]")
            return
        cmd = self.registry.get(name)
        if cmd is None:
            self.console.print(f"[red]comando desconhecido: {name}[/red] (use /help)")
            return
        # /exec recebe o texto após o comando, preservando espaços/quebras do colado.
        cmd.raw_args = line[len(name):].lstrip()
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
        self.session.save_state()