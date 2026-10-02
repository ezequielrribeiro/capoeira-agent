"""Fake CapoeiraHost (ThreadingHTTPServer) para testes — protocolo textual de injeção."""
from __future__ import annotations

import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


class HostControl:
    """Comportamento programável do fake host."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.chat_requests: list[tuple[str, list[tuple[str, str]]]] = []
        self.fail_chat: str | None = None  # status code como str p/ 503 etc.
        self._request_counter = 0


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencia log
        pass

    def _read_form(self) -> list[tuple[str, str]]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        return urllib.parse.parse_qsl(raw.decode("utf-8"), keep_blank_values=True)

    def _send(self, status: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        ctrl = self.server.control  # type: ignore[attr-defined]
        form = self._read_form()
        if self.path == "/api/chat":
            ctrl.chat_requests.append((self.path, list(form)))
            if ctrl.fail_chat:
                code = int(ctrl.fail_chat)
                self._send(code, f"error {code}")
                return
            ctrl._request_counter += 1
            self._send(200, f"accepted: req-{ctrl._request_counter}")
        elif self.path == "/api/tags":
            self._send(200, "gemini-pro | provider=gemini | streaming=false\n")
        elif self.path == "/api/ps":
            self._send(200, "gemini-pro | provider=gemini | status=idle\n")
        else:
            self._send(404, "not found")

    def do_GET(self):
        ctrl = self.server.control  # type: ignore[attr-defined]
        if self.path == "/api/tags":
            self._send(200, "gemini-pro | provider=gemini | streaming=false\n")
        elif self.path == "/api/ps":
            self._send(200, "gemini-pro | provider=gemini | status=idle\n")
        else:
            self._send(404, "not found")


@pytest.fixture()
def fake_host():
    ctrl = HostControl()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.control = ctrl  # type: ignore[attr-defined]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"server": server, "ctrl": ctrl, "base": f"http://127.0.0.1:{server.server_port}"}
    finally:
        server.shutdown()
        server.server_close()
