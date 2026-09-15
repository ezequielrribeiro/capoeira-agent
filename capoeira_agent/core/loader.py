"""Descoberta dinâmica de plugins/commands (importlib) com precedência projeto->config->package."""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

from .command import Command, AgentContext
from .registry import CommandRegistry


def _norm_name(name: str) -> str:
    return f"/{name}" if not name.startswith("/") else name


def load_module_commands(registry: CommandRegistry, module) -> int:
    """Registra classes Command encontradas em um módulo já importado."""
    count = 0
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, Command) and obj is not Command:
            cmd = obj()
            registry.register(_norm_name(cmd.name), cmd)
            count += 1
    return count


def load_package(registry: CommandRegistry, package_name: str) -> int:
    """Carrega comandos de um pacote instalado (ex.: capoeira_agent.commands)."""
    import importlib

    mod = importlib.import_module(package_name)
    count = 0
    pkg_path = Path(getattr(mod, "__path__")[0])
    for file in sorted(pkg_path.iterdir()):
        if file.suffix == ".py" and not file.name.startswith("__"):
            submod = importlib.import_module(f"{package_name}.{file.stem}")
            count += load_module_commands(registry, submod)
    return count


def load_directory(registry: CommandRegistry, directory: Path, package: str = "_user_commands") -> int:
    """Carrega commands de um diretório de arquivos .py (projeto/config)."""
    if not directory.is_dir():
        return 0
    count = 0
    for file in sorted(directory.iterdir()):
        if file.suffix == ".py" and not file.name.startswith("__"):
            mod_name = f"{package}.{file.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, file)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            try:
                spec.loader.exec_module(mod)
            except Exception:
                continue
            count += load_module_commands(registry, mod)
    return count


def apply_context(registry: CommandRegistry, context: AgentContext) -> None:
    for cmd in registry.all().values():
        cmd.context = context


def load_all(registry: CommandRegistry, project_commands_dir: Path | None, config_commands_dir: Path | None) -> int:
    """Ordem de precedência: pacote (core) -> config -> projeto (projeto sobrescreve)."""
    total = 0
    total += load_package(registry, "capoeira_agent.commands")
    if config_commands_dir is not None:
        total += load_directory(registry, Path(config_commands_dir), "_config_commands")
    if project_commands_dir is not None:
        total += load_directory(registry, Path(project_commands_dir), "_project_commands")
    return total