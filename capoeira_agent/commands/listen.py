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
            return
        if args and args[0] == "debug":
            listener.debug = not listener.debug
            print(f"debug do monitor: {'on' if listener.debug else 'off'}")
            return
        if args:
            print("uso: /listen [stop|debug]")
            return
        if not self.context.session.injected:
            print("ambiente ainda não injetado — rode /inject-environment para expor os comandos.")
        print(listener.start())
