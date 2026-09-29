"""Resolução do diretório de configuração e carregamento de config.yaml + premises."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8765

VALID_POLICIES = ("auto", "ask", "readonly")


def resolve_config_dir() -> Path:
    """CAPOEIRA_AGENT_CONFIG_DIR -> %APPDATA%\\CapoeiraAgent -> ~/.capoeira-agent"""
    env = os.environ.get("CAPOEIRA_AGENT_CONFIG_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "CapoeiraAgent"
    return Path.home() / ".capoeira-agent"


@dataclass
class HostConfig:
    base_url: str = f"http://{DEFAULT_HOST}:{DEFAULT_HTTP_PORT}"
    model: str = "gemini-pro"
    timeout: int = 180
    new_chat: bool = False
    app_host: str = "127.0.0.1"
    app_port: int = 8767
    app_path: str = "/api/capoeira/response"


@dataclass
class PolicyConfig:
    mode: str = "ask"
    auto_plugins: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.mode not in VALID_POLICIES:
            self.mode = "ask"


@dataclass
class AgentConfig:
    host: HostConfig = field(default_factory=HostConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    python: str = "python3"

    @classmethod
    def load(cls, config_dir: Path | None = None) -> "AgentConfig":
        config_dir = config_dir or resolve_config_dir()
        cfg = cls()
        cfg._apply_file(config_dir / "config.yaml")
        cfg._apply_env()
        return cfg

    def _apply_file(self, path: Path) -> None:
        if not path.exists():
            return
        import yaml

        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        host = data.get("host") or {}
        policy = data.get("policy") or {}
        if host.get("base_url"):
            self.host.base_url = str(host["base_url"]).rstrip("/")
        if host.get("model"):
            self.host.model = str(host["model"])
        if host.get("timeout") is not None:
            self.host.timeout = int(host["timeout"])
        if host.get("new_chat") is not None:
            self.host.new_chat = bool(host["new_chat"])
        if host.get("app_host"):
            self.host.app_host = str(host["app_host"])
        if host.get("app_port") is not None:
            self.host.app_port = int(host["app_port"])
        if host.get("app_path"):
            self.host.app_path = str(host["app_path"])
        if policy.get("mode"):
            self.policy.mode = str(policy["mode"])
        if policy.get("auto_plugins"):
            self.policy.auto_plugins = list(policy["auto_plugins"])
        if data.get("python"):
            self.python = str(data["python"])

    def _apply_env(self) -> None:
        env = os.environ
        if env.get("CAPOEIRA_AGENT_BASE_URL"):
            self.host.base_url = env["CAPOEIRA_AGENT_BASE_URL"].rstrip("/")
        if env.get("CAPOEIRA_AGENT_MODEL"):
            self.host.model = env["CAPOEIRA_AGENT_MODEL"]
        if env.get("CAPOEIRA_AGENT_NEW_CHAT") is not None:
            self.host.new_chat = env["CAPOEIRA_AGENT_NEW_CHAT"].lower() in ("1", "true", "yes")
        if env.get("CAPOEIRA_AGENT_POLICY"):
            self.policy.mode = env["CAPOEIRA_AGENT_POLICY"]
        if env.get("CAPOEIRA_AGENT_APP_PORT"):
            self.host.app_port = int(env["CAPOEIRA_AGENT_APP_PORT"])

    def applies_new_chat(self) -> str:
        return "true" if self.host.new_chat else "false"


@dataclass
class Premises:
    """Premissas por projeto (projects/<slug>.yaml) — modelo simplificado estilo CapoeiraCode."""

    name: str = ""
    description: str = ""
    stack: dict = field(default_factory=dict)
    structure: dict = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    specs: list[str] | None = None
    skills: list[str] | None = None

    @classmethod
    def load(cls, config_dir: Path, slug: str) -> "Premises":
        path = config_dir / "projects" / f"{slug}.yaml"
        if not path.exists():
            return cls(name=slug)
        import yaml

        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(
            name=str(data.get("name") or slug),
            description=str(data.get("description") or ""),
            stack=data.get("stack") or {},
            structure=data.get("structure") or {},
            commands=list(data.get("commands") or []),
            specs=data.get("specs"),
            skills=data.get("skills"),
        )


def slugify(text: str) -> str:
    """Converte um nome em slug simples para pastas de workspace."""
    out = []
    for ch in text.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "/", "\\", ".", "_"):
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "default"