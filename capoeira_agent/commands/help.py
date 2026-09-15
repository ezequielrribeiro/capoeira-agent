from capoeira_agent.core.command import Command


class HelpCommand(Command):
    name = "help"
    description = "Lista todos os comandos disponíveis"

    def execute(self, args):
        print("Comandos disponíveis:")
        for name, cmd in sorted(self.context.registry.all().items()):
            remote = " [LLM]" if cmd.tool_def is not None else ""
            print(f"  {name:<22} {cmd.description}{remote}")