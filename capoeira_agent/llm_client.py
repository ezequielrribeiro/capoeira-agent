"""Cliente HTTP textual para o CapoeiraHost (v2.1.0): /api/chat, /api/chat/read, /api/chat/watch."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class LLMRequestError(Exception):
    pass


@dataclass
class ChatReply:
    content: str  # prosa final e/ou linhas [TOOL_CALL]
    revisions: str | None = None


def serialize_tools(tools: list[dict]) -> str:
    """tools textual: 'name=X | desc=... | arg:type' — uma linha por ferramenta."""
    from .prompts import build_tools_declaration

    return build_tools_declaration(tools)


def _build_form(pairs: list[tuple[str, str]]) -> bytes:
    return urllib.parse.urlencode(pairs).encode("utf-8")


class LLMClient:
    def __init__(self, base_url: str, model: str, timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # -- baixo nível ---------------------------------------------------------
    def _post(self, path: str, pairs: list[tuple[str, str]] | None = None) -> tuple[str, dict]:
        data = _build_form(pairs or [])
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return body, dict(resp.headers)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(f"HTTP {exc.code}: {detail}".strip()) from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(f"falha de rede: {exc.reason}") from exc

    # -- /api/chat -----------------------------------------------------------
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        on_chunk: callable | None = None,
        new_chat: bool | None = None,
    ) -> ChatReply:
        pairs: list[tuple[str, str]] = [("model", self.model)]
        for msg in messages:
            role = msg.get("role", "user")
            pairs.append(("role", role))
            pairs.append(("content", msg.get("content", "")))
            if role == "tool" and msg.get("tool_call_id"):
                pairs.append(("tool_call_id", msg["tool_call_id"]))
        if tools:
            pairs.append(("tools", serialize_tools(tools)))
        if stream:
            pairs.append(("stream", "true"))
        if new_chat is not None:
            pairs.append(("new_chat", "true" if new_chat else "false"))

        if stream and on_chunk is not None:
            content = self._stream_chat(pairs, on_chunk)
            return ChatReply(content=content)
        body, headers = self._post("/api/chat", pairs)
        return ChatReply(content=body, revisions=headers.get("X-Capoeira-Revision"))

    def _stream_chat(self, pairs: list[tuple[str, str]], on_chunk) -> str:
        data = _build_form(pairs)
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain"},
            method="POST",
        )
        chunks: list[str] = []
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                while True:
                    raw = resp.read(512)
                    if not raw:
                        break
                    piece = raw.decode("utf-8", errors="replace")
                    chunks.append(piece)
                    on_chunk(piece)
            return "".join(chunks)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(f"HTTP {exc.code}: {detail}".strip()) from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(f"falha de rede: {exc.reason}") from exc

    # -- /api/chat/read ------------------------------------------------------
    def read_chat(self) -> tuple[str, int]:
        """Devolve (transcript, revision) do chat ativo."""
        body, headers = self._post("/api/chat/read", [("model", self.model)])
        revision = int(headers.get("X-Capoeira-Revision") or "0")
        return body, revision

    # -- /api/chat/watch -----------------------------------------------------
    def watch(self, revision: int = 0, timeout: int = 30) -> tuple[str, int]:
        """Long-poll: devolve (delta, nova_revision). Delta vazio = sem mudança."""
        pairs = [("model", self.model), ("revision", str(revision)), ("timeout", str(timeout))]
        body, headers = self._post("/api/chat/watch", pairs)
        new_revision = int(headers.get("X-Capoeira-Revision") or str(revision))
        return body, new_revision

    # -- utilidades ----------------------------------------------------------
    def providers(self) -> list[str]:
        """GET /api/ps — lista de perfis online (best-effort)."""
        req = urllib.request.Request(f"{self.base_url}/api/ps")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return [ln.strip() for ln in resp.read().decode("utf-8", errors="replace").splitlines() if ln.strip()]
        except urllib.error.URLError:
            return []
        except urllib.error.HTTPError:
            return []

    def tags(self) -> list[str]:
        """GET /api/tags — lista de perfis cadastrados (best-effort)."""
        req = urllib.request.Request(f"{self.base_url}/api/tags")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return [ln.strip() for ln in resp.read().decode("utf-8", errors="replace").splitlines() if ln.strip()]
        except urllib.error.URLError:
            return []
        except urllib.error.HTTPError:
            return []


def parse_delta_lines(delta: str) -> list[tuple[str, str]]:
    """Converte linhas '[USER] ...' / '[ASSISTANT] ...' do delta em turnos."""
    turns: list[tuple[str, str]] = []
    for line in delta.splitlines():
        line = line.strip()
        if line.startswith("[USER] "):
            turns.append(("user", line[len("[USER] "):]))
        elif line.startswith("[ASSISTANT] "):
            turns.append(("assistant", line[len("[ASSISTANT] "):]))
        elif line.startswith("[USER]") or line.startswith("[ASSISTANT]"):
            turns.append(("user" if line[1:5] == "USER" else "assistant", line.split("]", 1)[1].lstrip()))
    return turns