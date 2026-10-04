from capoeira_agent import toolsdef
from capoeira_agent.core.command import Command
from capoeira_agent.init_project import init_project
from capoeira_agent.tools_config import ensure_tools_config


class InitCommand(Command):
    name = "init"
    description = "Cria os artefatos iniciais do projeto (specs/skills/commands/README)"

    def execute(self, args):
        created = init_project(self.context.project_root)
        print(f"/init: {len(created)} artefato(s) criado(s) em {self.context.project_root}")
        for path in created:
            print(f"  + {path.relative_to(self.context.project_root)}")
        names = [t["name"] for t in toolsdef.CORE_TOOL_DEFS]
        for cmd in self.context.registry.all().values():
            if cmd.tool_def is not None:
                names.append(cmd.tool_def.name)
        tools_yaml = ensure_tools_config(self.context.session.config_dir, names)
        if tools_yaml is not None:
            print(f"  + {tools_yaml} (comandos injetáveis editáveis)")