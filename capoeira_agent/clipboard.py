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
    """Lê CF_UNICODETEXT com assinaturas explícitas.

    Em 64 bits, sem ``restype``/``argtypes`` os handles são truncados para 32
    bits, o que corrompe o ponteiro e derruba o processo com access violation
    (0xC0000005). Por isso as funções do Win32 são declaradas explicitamente."""
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13

    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE

        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
    except (AttributeError, OSError):
        return None

    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    except OSError:
        return None
    finally:
        user32.CloseClipboard()


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
