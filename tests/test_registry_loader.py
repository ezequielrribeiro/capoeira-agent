from pathlib import Path

from capoeira_agent.core.command import Command, ToolDef
from capoeira_agent.core.loader import load_all, load_directory
from capoeira_agent.core.registry import CommandRegistry


def test_core_tool_definitions_present():
    reg = CommandRegistry()
    tools = reg.tool_definitions()
    names = {t["name"] for t in tools}
    assert {"read_file", "list_dir", "run_shell", "run_python", "write_file", "ask_user", "done"} <= names
    assert reg.get_tool("write_file") is not None


def test_loader_discovers_plugin_from_directory(tmp_path):
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "mycmd.py").write_text(
        "from capoeira_agent.core.command import Command, ToolDef\n"
        "class MycmdCommand(Command):\n"
        "    name='mycmd'\n"
        "    description='x'\n"
        "    tool_def=ToolDef(name='mycmd', desc='x', args={'a':'string'})\n"
        "    def execute(self, args): print('oi')\n"
    )
    reg = CommandRegistry()
    n = load_directory(reg, tmp_path / "commands")
    assert n == 1
    assert reg.get("/mycmd") is not None
    tools = [t for t in reg.tool_definitions() if t["name"] == "mycmd"]
    assert tools == [{"name": "mycmd", "desc": "x", "args": {"a": "string"}}]


def test_load_all_loads_package_commands(tmp_path):
    reg = CommandRegistry()
    load_all(reg, tmp_path / "commands", None)
    assert reg.get("/help") is not None
    assert reg.get("/init") is not None
    assert reg.get("/exec") is not None


def test_plugin_execute_remote(tmp_path):
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "deploy.py").write_text(
        'from capoeira_agent.core.command import Command, ToolDef\n'
        'class DeployCommand(Command):\n'
        '    name = "deploy"\n'
        '    tool_def = ToolDef(name="deploy", desc="deploy", args={"env": "string"})\n'
        '    def execute(self, args):\n'
        '        print("local")\n'
        '    def execute_remote(self, params):\n'
        '        return "deployado em " + str(params.get("env"))\n'
    )
    reg = CommandRegistry()
    load_directory(reg, tmp_path / "commands")
    cmd = reg.get("/deploy")
    assert cmd.tool_def is not None
    assert cmd.execute_remote({"env": "prod"}) == "deployado em prod"