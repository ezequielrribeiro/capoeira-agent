from capoeira_agent.core.command import Command


class ListenCommand(Command):
    name = "listen"
    description = "Inicia (ou para, com 'stop') o monitor de clipboard das respostas do chat"

    def execute(self, args):
        listener = self.context.listener
        if listener is None:
            print("monitor não configurado")
            return
        if args and args[0] == "stop":
            print(listener.stop())
        elif args:
            print("uso: /listen [stop]")
        else:
            if not self.context.session.injected:
                print("ambiente ainda não injetado — executando /inject-environment antes do monitor...")
            print(listener.start())
