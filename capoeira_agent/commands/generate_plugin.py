from pathlib import Path

from capoeira_agent.core.command import Command
from capoeira_agent.core.parser import parse_flags


class GeneratePluginCommand(Command):
    name = "generate-plugin"
    description = "Gera um novo plug-in de comando (/generate-plugin --name x [--tool \"n:desc\"])"

    def execute(self, args):
        parsed = parse_flags(args)
        plugin_name = parsed.get("name")
        if not plugin_name or isinstance(plugin_name, bool):
            print("uso: /generate-plugin --name <nome> [--tool \"nome:descricao\"]")
            return
        if "_" in plugin_name or any(ch.isspace() for ch in plugin_name):
            print("nome não pode conter sublinhados ou espaços.")
            return

        file_name = f"{plugin_name.replace('-', '_').lower()}.py"
        class_name = "".join(w.capitalize() for w in plugin_name.replace("-", " ").split()) + "Command"

        target_dir = Path(self.context.project_root) / "commands"
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / file_name
        if path.exists():
            print(f"plug-in já existe: {path}")
            return

        tool = parsed.get("tool") if not isinstance(parsed.get("tool"), bool) else None
        path.write_text(self._template(plugin_name.lower(), class_name, tool), encoding="utf-8")
        print(f"plug-in criado: {path}")
        print("(recarregue via /reload se disponível ou reinicie para carregar)")

    def _template(self, name: str, class_name: str, tool: str | None) -> str:
        tool_attr = "None"
        if tool:
            parts = tool.split(":", 1)
            tool_name = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else f"Comando remoto {name}"
            tool_attr = f'ToolDef(name="{tool_name}", desc="{desc}", args={{}})'
        return f"""from capoeira_agent.core.command import Command, ToolDef

class {class_name}(Command):
    name = "{name}"
    description = "Descreva o que este comando faz"
    tool_def = {tool_attr}

    def execute(self, args):
        print("Executando {name}:", args)

    def execute_remote(self, params):
        return f"ok: {name} recebeu {{params}}"
"""