"""Sessão do agente: workspace por projeto + session.jsonl (histórico/mirror) + revision."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import resolve_config_dir, slugify


class Session:
    def __init__(self, project_path: Path | str, config_dir: Path | None = None,
                 session_name: str = "default") -> None:
        self.project_path = Path(project_path)
        self.slug = slugify(self.project_path.name or "default")
        self.config_dir = config_dir or resolve_config_dir()
        self.session_name = session_name

        self.workspace_dir = self.config_dir / "configs" / self.slug / "workspace"
        self.session_dir = self.workspace_dir / "sessions" / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.session_dir / "state.json"
        self.history_file = self.session_dir / "session.jsonl"

        self.state: dict[str, Any] = {"revision": 0, "injected": False}
        self._records: list[dict] = []
        self.premises = None  # definido no bootstrap (Premises por projeto)
        self._load_state()
        self._load_history()

    # -- estado --------------------------------------------------------------
    def _load_state(self) -> None:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.state.update(data)
            except (ValueError, OSError):
                pass

    def save_state(self) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    @property
    def revision(self) -> int:
        return int(self.state.get("revision", 0))

    @revision.setter
    def revision(self, value: int) -> None:
        self.state["revision"] = value

    @property
    def injected(self) -> bool:
        return bool(self.state.get("injected", False))

    @injected.setter
    def injected(self, value: bool) -> None:
        self.state["injected"] = value

    def set_state(self, **kwargs) -> None:
        self.state.update(kwargs)

    # -- histórico -----------------------------------------------------------
    def _load_history(self) -> None:
        self._records = []
        if not self.history_file.exists():
            return
        for line in self.history_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                self._records.append(json.loads(line))
            except ValueError:
                continue

    def _append(self, record: dict) -> None:
        record.setdefault("id", uuid.uuid4().hex)
        record.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
        self._records.append(record)
        with self.history_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def append_outcome(self, kind: str, content: str, *, revision: int | None = None, **meta) -> dict:
        rec = {"kind": kind, "content": content, "meta": meta}
        if revision is not None:
            rec["revision"] = revision
        self._append(rec)
        return rec

    def append_message(self, role: str, content: str, *, revision: int | None = None,
                       tool_call_id: str | None = None) -> dict:
        """Turno de conversa (user/assistant/tool) — espelha o transcript do chat ativo."""
        rec: dict = {"kind": "chat", "role": role, "content": content}
        if revision is not None:
            rec["revision"] = revision
        if tool_call_id is not None:
            rec["tool_call_id"] = tool_call_id
        self._append(rec)
        return rec

    def approval(self, tool: str, allowed: bool, mode: str = "") -> None:
        self._append({"kind": "approval", "tool": tool, "allowed": allowed, "mode": mode})

    def messages(self) -> list[dict]:
        """Mensagens para os pares role/content do /api/chat (rebuild do transcript)."""
        msgs: list[dict] = []
        for rec in self._records:
            if rec.get("kind") != "chat":
                continue
            msg: dict = {"role": rec["role"], "content": rec["content"]}
            if rec.get("tool_call_id"):
                msg["tool_call_id"] = rec["tool_call_id"]
            msgs.append(msg)
        return msgs

    def records(self) -> list[dict]:
        return list(self._records)

    def clear(self) -> None:
        self._records = []
        self.state["revision"] = 0
        self.state["injected"] = False
        self.history_file.write_text("", encoding="utf-8")
        self.save_state()

    def switch(self, session_name: str) -> None:
        self.session_name = session_name
        self.session_dir = self.workspace_dir / "sessions" / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.session_dir / "state.json"
        self.history_file = self.session_dir / "session.jsonl"
        self.state = {"revision": 0, "injected": False}
        self._load_state()
        self._load_history()

    def reset_revision(self) -> None:
        self.state["revision"] = 0