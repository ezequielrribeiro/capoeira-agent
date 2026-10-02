"""Cliente HTTP textual para o CapoeiraHost (pass-through verbatim): /api/chat.

O host é usado apenas para injetar texto no LLM web; o retorno é obtido pela
interface do agente (``/exec`` cola a resposta com os ``[TOOL_CALL]``).
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class LLMRequestError(Exception):
    pass


@dataclass
class ChatReply:
    content: str  # "accepted: {request_id}" (fire-and-forget)
    request_id: str | None = None


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
        stream: bool = False,
        new_chat: bool | None = None,
    ) -> ChatReply:
        """Chama /api/chat (pass-through verbatim no host): sem campo `tools` e
        sem `role=tool`. Resultados de ferramenta (role=tool) são serializados
        como turno assistant com `[TOOL_RESULT] (id) conteúdo`. O host responde
        `accepted: {request_id}` (fire-and-forget) — a resposta do modelo NÃO
        volta pelo host: o usuário cola o texto do chat web em `/exec` e o agente
        o processa (parse dos [TOOL_CALL] + execução)."""
        pairs: list[tuple[str, str]] = [("model", self.model)]
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "tool":
                tid = msg.get("tool_call_id")
                prefix = f"[TOOL_RESULT] ({tid}) " if tid else "[TOOL_RESULT] "
                role, content = "assistant", f"{prefix}{content}".strip()
            pairs.append(("role", role))
            pairs.append(("content", content))
        if stream:
            pairs.append(("stream", "true"))
        if new_chat is not None:
            pairs.append(("new_chat", "true" if new_chat else "false"))

        body, _ = self._post("/api/chat", pairs)
        return ChatReply(content=body, request_id=_parse_request_id(body))

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


def _parse_request_id(body: str) -> str | None:
    """Extrai o request_id de um corpo 'accepted: {uuid}'."""
    marker = "accepted: "
    if body.startswith(marker):
        return body[len(marker):].strip() or None
    return None
