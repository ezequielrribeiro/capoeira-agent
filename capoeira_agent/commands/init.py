from capoeira_agent.core.command import Command
from capoeira_agent.init_project import init_project


class InitCommand(Command):
    name = "init"
    description = "Cria os artefatos iniciais do projeto (specs/skills/commands/README)"

    def execute(self, args):
        created = init_project(self.context.project_root)
        print(f"/init: {len(created)} artefato(s) criado(s) em {self.context.project_root}")
        for path in created:
            print(f"  + {path.relative_to(self.context.project_root)}")