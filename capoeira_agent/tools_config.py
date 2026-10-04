"""Configuração editável dos comandos injetados pelo /inject-environment.

O arquivo ``tools.yaml`` (no config dir global) lista todos os comandos que podem
aparecer no dicionário de tools enviado à LLM, com ``enabled: true|false`` por
comando. Tools ausentes do arquivo permanecem habilitadas por padrão
(compatibilidade com instalações sem o arquivo).
"""
from __future__ import annotations

from pathlib import Path

TOOLS_CONFIG_NAME = "tools.yaml"


def tools_config_path(config_dir: Path) -> Path:
    return Path(config_dir) / TOOLS_CONFIG_NAME


def disabled_tools(config_dir: Path) -> set[str]:
    """Nomes de tools explicitamente desabilitadas no tools.yaml.

    Arquivo ausente/inválido => conjunto vazio (todas habilitadas).
    """
    path = tools_config_path(config_dir)
    if not path.exists():
        return set()
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    disabled: set[str] = set()
    for entry in data.get("tools") or []:
        if isinstance(entry, dict):
            name = entry.get("name")
            if name and entry.get("enabled") is False:
                disabled.add(str(name))
        elif isinstance(entry, str):
            # entrada "name: false" simplificada não se aplica; strings = habilitadas
            continue
    return disabled


def render_tools_yaml(names: list[str]) -> str:
    lines = [
        "# Comandos expostos à LLM via /inject-environment (editável).",
        "# enabled: false remove o comando do dicionário injetado no chat.",
        "tools:",
    ]
    for name in names:
        lines.append(f"  - name: {name}")
        lines.append("    enabled: true")
    return "\n".join(lines) + "\n"


def ensure_tools_config(config_dir: Path, names: list[str]) -> Path | None:
    """Cria tools.yaml padrão (todas habilitadas) se ainda não existir."""
    path = tools_config_path(config_dir)
    if path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_tools_yaml(names), encoding="utf-8")
    return path
