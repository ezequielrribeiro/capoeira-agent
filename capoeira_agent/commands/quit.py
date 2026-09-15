from capoeira_agent.core.command import Command


class QuitCommand(Command):
    name = "quit"
    description = "Encerra o CapoeiraAgent"

    def execute(self, args):
        if self.context.tui is not None:
            self.context.tui.quit()
        print("encerrando...")