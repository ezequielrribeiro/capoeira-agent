"""Leitura da área de transferência do SO (clipboard → resposta do LLM).

O agente não recebe mais push do host: o usuário copia a resposta do chat web
(Ctrl+C) e o agente monitora o clipboard, detecta mudanças e faz o parse dos
``[TOOL_CALL]``. Este módulo isola o acesso ao clipboard por plataforma.
"""
from __future__ import annotations

import shutil
import subprocess


def read_clipboard() -> str | None:
    """Lê o clipboard do SO. Retorna None se indisponível/vazio."""
    import sys

    if sys.platform == "win32":
        return _read_windows()
    if sys.platform == "darwin":
        return _read_command(["pbpaste"])
    return _read_linux()


def _read_windows() -> str | None:
    """Windows: tentativa via Win32 (ctypes) e fallback para PowerShell."""
    text = _read_windows_ctypes()
    if text is not None:
        return text
    return _read_command(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"])


def _read_windows_ctypes() -> str | None:
    import ctypes

    try:
        user32 = ctypes.windll.user32
        CF_UNICODETEXT = 13
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        if not user32.OpenClipboard(0):
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            pointer = ctypes.windll.kernel32.GlobalLock(handle)
            if not pointer:
                return None
            try:
                return ctypes.c_wchar_p(pointer).value or ""
            finally:
                ctypes.windll.kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def _read_linux() -> str | None:
    for command in (
        ["wl-paste", "--no-newline"],
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
    ):
        text = _read_command(command)
        if text is not None:
            return text
    return None


def _read_command(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout
