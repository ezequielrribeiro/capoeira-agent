"""Parse de entrada da TUI (/comando --flag valor) e de argumentos."""
from __future__ import annotations


def parse_line(line: str) -> tuple[str, list[str]]:
    """Divide '/comando arg1 --flag valor' em (nome, [args...])."""
    stripped = line.strip()
    if not stripped:
        return "", []
    parts = stripped.split()
    name = parts[0]
    if not name.startswith("/"):
        return "", parts
    return name, parts[1:]


def parse_flags(args: list[str]) -> dict:
    """Transforma args em flags: '--flag valor' -> {'flag': 'valor'}; flag booleana -> True."""
    result: dict = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                result[key] = args[i + 1]
                i += 2
            else:
                result[key] = True
                i += 1
        else:
            i += 1
    return result