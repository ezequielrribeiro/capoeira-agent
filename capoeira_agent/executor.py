"""Executores das tools core (read/list/run_shell/run_python/write_file/ask_user) + plugins."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .applier import ChangeApplier
from .steps import Step, _decode_b64

OUTPUT_LIMIT = 8000


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""


class Executor:
    def __init__(self, project_root: Path | str, python: str = "python3", timeout: int = 120,
                 registry=None, ask_user: callable | None = None) -> None:
        self.project_root = Path(project_root)
        self.python = python
        self.timeout = timeout
        self.registry = registry
        self.applier = ChangeApplier(self.project_root)
        self.ask_user = ask_user or (lambda _m: "")

    # -- dispatch ------------------------------------------------------------
    def apply(self, step: Step) -> ToolResult:
        handler = getattr(self, f"_do_{step.tool}", None)
        if handler is not None:
            return handler(step.params)
        tool = self._plugin_tool(step.tool)
        if tool is not None:
            cmd = self.registry.get(tool)
            try:
                out = cmd.execute_remote(dict(step.params))
                return ToolResult(True, output=str(out))
            except Exception as exc:  # plugin falhou => erro ao modelo
                return ToolResult(False, error=f"plugin '{step.tool}': {exc}")
        return ToolResult(False, error=f"tool desconhecida: '{step.tool}'")

    def _plugin_tool(self, name: str) -> str | None:
        if self.registry is None:
            return None
        for cmd_name, cmd in self.registry.all().items():
            if cmd.tool_def is not None and cmd.tool_def.name == name:
                return cmd_name
        return None

    def known_tool(self, tool: str) -> bool:
        """True se a tool tem executor local (core handler ou comando-plugin)."""
        if hasattr(self, f"_do_{tool}"):
            return True
        return self._plugin_tool(tool) is not None

    # -- handlers ------------------------------------------------------------
    def _read_required(self, params: dict) -> str:
        path = params.get("path")
        if not path:
            raise ValueError("parâmetro 'path' obrigatório")
        full = self._resolve(str(path))
        return full.read_text(encoding="utf-8", errors="replace")

    def _do_read_file(self, params: dict) -> ToolResult:
        try:
            return ToolResult(True, output=self._read_required(params))
        except (ValueError, OSError) as exc:
            return ToolResult(False, error=str(exc))

    def _do_list_dir(self, params: dict) -> ToolResult:
        try:
            path = str(params.get("path") or ".")
            full = self._resolve(path)
            if not full.is_dir():
                return ToolResult(False, error=f"não é diretório: {full}")
            entries = []
            for child in sorted(full.iterdir()):
                entries.append(child.name + ("/" if child.is_dir() else ""))
            return ToolResult(True, output="\n".join(entries))
        except (ValueError, OSError) as exc:
            return ToolResult(False, error=str(exc))

    def _do_run_shell(self, params: dict) -> ToolResult:
        cmd = str(params.get("cmd") or "")
        if not cmd:
            return ToolResult(False, error="parâmetro 'cmd' obrigatório")
        return self._run_subprocess(cmd, shell=True)

    def _do_run_python(self, params: dict) -> ToolResult:
        code_b64 = str(params.get("code") or "")
        try:
            code = _decode_b64(code_b64)
        except ValueError as exc:
            return ToolResult(False, error=f"run_python.code inválido: {exc}")
        return self._run_subprocess([self.python, "-c", code], shell=False)

    def _do_write_file(self, params: dict) -> ToolResult:
        file_path = str(params.get("file_path") or "")
        if not file_path:
            return ToolResult(False, error="parâmetro 'file_path' obrigatório")
        code_b64 = str(params.get("code_content") or "")
        try:
            code = _decode_b64(code_b64)
        except ValueError as exc:
            return ToolResult(False, error=f"code_content inválido: {exc}")
        action = str(params.get("action") or "create_file")
        result = self.applier.apply([{
            "file_path": file_path,
            "action": action,
            "code_content": code,
            "target_symbol": params.get("target_symbol"),
        }])
        if result.ok:
            return ToolResult(True, output=f"ok: {result.message}")
        return ToolResult(False, error=result.error)

    def _do_ask_user(self, params: dict) -> ToolResult:
        message = str(params.get("message") or "")
        answer = self.ask_user(message if message else "Pergunta do agente?")
        return ToolResult(True, output=str(answer or ""))

    # -- util ----------------------------------------------------------------
    def _resolve(self, path: str) -> Path:
        target = (self.project_root / path).resolve()
        root = self.project_root.resolve()
        if not (target == root or root in target.parents):
            raise ValueError(f"caminho fora do projeto: {path}")
        return target

    def _run_subprocess(self, command, **kwargs) -> ToolResult:
        shell = kwargs.get("shell", True)
        try:
            if shell:
                proc = subprocess.run(
                    str(command), shell=True, cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=self.timeout, env=self._env(),
                )
            else:
                proc = subprocess.run(
                    list(command), cwd=str(self.project_root),
                    capture_output=True, text=True, timeout=self.timeout, env=self._env(),
                )
            output = proc.stdout
            if proc.stderr:
                output += ("\n" if output else "") + proc.stderr
            if proc.returncode != 0:
                return ToolResult(False, output=_truncate(output) or "", error=f"exit {proc.returncode}")
            return ToolResult(True, output=_truncate(output))
        except subprocess.TimeoutExpired:
            return ToolResult(False, error=f"timeout ({self.timeout}s)")
        except OSError as exc:
            return ToolResult(False, error=str(exc))

    def _env(self) -> dict:
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)  # não expõe segredos a subprocessos
        return env


def _truncate(text: str) -> str:
    if len(text) <= OUTPUT_LIMIT:
        return text
    return text[:OUTPUT_LIMIT] + f"\n... [truncado {len(text) - OUTPUT_LIMIT} chars]"