from capoeira_agent.core.command import Command
from capoeira_agent.tui.monitor import status_block


class StatusCommand(Command):
    name = "status"
    description = "Mostra estado do host, modelo, política, sessão e tools"

    def execute(self, args):
        print(status_block(
            self.context.config,
            self.context.session,
            self.context.registry,
            self.context.permissions,
            self.context.client,
            self.context.runner,
        ))