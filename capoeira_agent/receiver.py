"""Receiver — API local (FastAPI/uvicorn) que fica na escuta do push do CapoeiraHost.

O host entrega a resposta do LLM via ``POST /api/capoeira/response`` (JSON) na
aplicação registrada. Este módulo sobe essa API em uma thread daemon e despacha
cada payload para um handler (o Listener), sem qualquer polling por parte do agente.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

DEFAULT_PATH = "/api/capoeira/response"

Handler = Callable[[dict[str, Any]], None]


def build_app(handler: Handler) -> FastAPI:
    """Monta a aplicação FastAPI com o endpoint de resposta do host."""
    app = FastAPI(title="CapoeiraAgent Receiver")

    @app.post(DEFAULT_PATH)
    async def response(request: Request) -> PlainTextResponse:
        payload = await request.json()
        if not isinstance(payload, dict):
            return PlainTextResponse("ok")
        handler(payload)
        return PlainTextResponse("ok")

    return app


class PushReceiver:
    """Servidor uvicorn em thread daemon que recebe os pushes do host."""

    def __init__(self, handler: Handler, host: str = "127.0.0.1", port: int = 8767) -> None:
        self.handler = handler
        self.host = host
        self.port = port
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def listening(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.listening:
            return
        import uvicorn

        app = build_app(self.handler)
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="capoeira-receiver", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._server = None
