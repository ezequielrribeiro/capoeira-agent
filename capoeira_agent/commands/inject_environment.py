from capoeira_agent import llm_client
from capoeira_agent.core.command import Command
from capoeira_agent.injector import inject_environment


class InjectEnvironmentCommand(Command):
    name = "inject-environment"
    description = "Envia ao chat ativo o ambiente do projeto + dicionário de comandos (tools)"

    def execute(self, args):
        premises = self.context.session.premises if hasattr(self.context.session, "premises") else None
        try:
            ack = inject_environment(
                self.context.client,
                self.context.session,
                self.context.registry,
                premises,
                new_chat=self.context.config.host.new_chat,
            )
        except llm_client.LLMRequestError as exc:
            detail = str(exc)
            print(f"falha ao injetar ambiente: {detail}")
            if "503" in detail:
                print("dica: o provedor do modelo está offline — confira se a aba do "
                      f"provedor ({self.context.config.host.model}) está aberta e registrada "
                      "no CapoeiraHost; rode /status para ver os providers online.")
            return
        n_tools = len(self.context.registry.tool_definitions())
        print(f"ambiente injetado no chat ativo (new_chat={self.context.config.host.new_chat}). "
              f"{n_tools} commandos expostos.")
        print(f"host respondeu: {ack.strip()} — a resposta do modelo chegará via push.")
