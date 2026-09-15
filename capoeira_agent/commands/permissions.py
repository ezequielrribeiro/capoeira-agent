from capoeira_agent.core.command import Command
from capoeira_agent.config import VALID_POLICIES


class PermissionsCommand(Command):
    name = "permissions"
    description = "Mostra/define a política de permissão (auto | ask | readonly)"

    def execute(self, args):
        if args:
            mode = args[0]
            if mode not in VALID_POLICIES:
                print(f"política inválida: {mode} (use {', '.join(VALID_POLICIES)})")
                return
            self.context.permissions.set_mode(mode)
        print(f"política: {self.context.permissions.mode}")
        if self.context.permissions.session_allow:
            print("aprovados para esta sessão: " + ", ".join(sorted(self.context.permissions.session_allow)))