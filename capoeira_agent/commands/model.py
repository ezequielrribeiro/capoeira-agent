from capoeira_agent.core.command import Command


class ModelCommand(Command):
    name = "model"
    description = "Configura parâmetros de comunicação: /model M, /base-url URL, /timeout SEG, /new-chat [true|false]"

    def execute(self, args):
        sub = args[0] if args else ""
        param = args[1] if len(args) > 1 else ""
        h = self.context.config.host
        if sub == "model" and param:
            h.model = param
            print(f"modelo: {h.model}")
        elif sub == "base-url" and param:
            h.base_url = param.rstrip("/")
            print(f"base_url: {h.base_url}")
        elif sub == "timeout" and param:
            h.timeout = int(param)
            print(f"timeout: {h.timeout}s")
        elif sub == "new-chat":
            h.new_chat = param.lower() in ("true", "1") if param else not h.new_chat
            print(f"new_chat: {h.new_chat}")
        else:
            print(f"uso: /model <nome> | /base-url <url> | /timeout <seg> | /new-chat [true|false]")
            print(f"atual: model={h.model} base_url={h.base_url} timeout={h.timeout} new_chat={h.new_chat}")