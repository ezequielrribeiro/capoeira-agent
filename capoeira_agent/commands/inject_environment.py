from capoeira_agent.core.command import Command
from capoeira_agent.injector import inject_environment
from capoeira_agent import llm_client


class InjectEnvironmentCommand(Command):
    name = "inject-environment"
    description = "Envia ao chat ativo o ambiente do projeto + dicionário de comandos (tools)"

    def execute(self, args):
        premises = self.context.session.premises if hasattr(self.context.session, "premises") else None
        try:
            reply = inject_environment(
                self.context.client,
                self.context.session,
                self.context.registry,
                premises,
                new_chat=self.context.config.host.new_chat,
            )
        except llm_client.LLMRequestError as exc:
            print(f"falha ao injetar ambiente: {exc}")
            return
        summary = reply.strip()
        print(f"ambiente injetado no chat ativo (new_chat={self.context.config.host.new_chat}). "
              f"{len(self.context.registry.tool_definitions())} commandos expostos.")
        if summary:
            print(f"resposta do modelo: {summary[:200]}{'...' if len(summary) > 200 else ''}")