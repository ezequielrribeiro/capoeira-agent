"""Representação de steps ([TOOL_CALL]) e helpers de parsing/base64."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any

TOOL_CALL_LINE = re.compile(r"^\s*\[TOOL_CALL\]\s+(.{1,512})\s*$", re.MULTILINE)
_OMISSION = "// ... [Omitted by CapoeiraAgent] ..."


@dataclass
class Step:
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    line: str = ""  # linha textual original (round-trip no transcript)


def _split_pipe_fields(text: str) -> list[str]:
    """Divide por '|' fora de aspas simples; '|' entre '...' é literal."""
    fields: list[str] = []
    buf: list[str] = []
    in_quote = False
    for ch in text:
        if ch == "'":
            in_quote = not in_quote
            buf.append(ch)
        elif ch == "|" and not in_quote:
            fields.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    fields.append("".join(buf).strip())
    return fields


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1]
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if raw == "null":
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(part) for part in _split_pipe_fields(inner)]
    return raw


def _truncated(raw: str) -> bool:
    """Aspa simples aberta (valor cortado em quebra de linha)."""
    return raw.count("'") % 2 == 1


def parse_tool_calls(content: str) -> list[Step]:
    """Extrai linhas '[TOOL_CALL] nome | chave=valor' do conteúdo."""
    steps: list[Step] = []
    for match in TOOL_CALL_LINE.finditer(content):
        line = match.group(1).strip()
        if _truncated(line):
            continue  # linha cortada => não executar
        fields = _split_pipe_fields(line)
        if not fields:
            continue
        name = fields[0].strip()
        if not name:
            continue
        params: dict[str, Any] = {}
        for f in fields[1:]:
            if "=" not in f:
                continue
            key, _, val = f.partition("=")
            key = key.strip()
            if not key:
                continue
            params[key] = _parse_value(val)
        steps.append(Step(tool=name, params=params, line=line))
    return steps


def _encode_b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _decode_b64(payload: str) -> str:
    """Decodifica base64 estrito; lança ValueError em conteúdo inválido/truncado."""
    compact = payload.strip()
    if not compact:
        raise ValueError("base64 vazio")
    if len(compact) % 4 != 0:
        raise ValueError("base64 com tamanho inválido")
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
        raise ValueError("charset inválido em base64")
    try:
        raw = base64.b64decode(compact, validate=True)
    except Exception as exc:  # binascii.Error
        raise ValueError("base64 inválido") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("base64 não é UTF-8 válido") from exc