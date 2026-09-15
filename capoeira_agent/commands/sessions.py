import os

from capoeira_agent.core.command import Command


class SessionsCommand(Command):
    name = "sessions"
    description = "Lista as sessões salvas do projeto"

    def execute(self, args):
        sdir = self.context.session.workspace_dir / "sessions"
        if not sdir.is_dir():
            print("nenhuma sessão salva")
            return
        current = self.context.session.session_name
        for name in sorted(p.name for p in sdir.iterdir() if p.is_dir()):
            mark = " *" if name == current else ""
            print(f"  {name}{mark}")


class UseCommand(Command):
    name = "use"
    description = "Troca para a sessão NOME (históricos independentes)"

    def execute(self, args):
        if not args:
            print("uso: /use <nome>")
            return
        self.context.session.switch(args[0])
        print(f"sessão ativa: {args[0]}")


class ResetCommand(Command):
    name = "reset"
    description = "Apaga o histórico da sessão atual e zera a revision"

    def execute(self, args):
        self.context.session.clear()
        self.context.permissions.reset_session()
        print("sessão atual limpa (histórico e revision zerados)")