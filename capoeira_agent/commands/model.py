from capoeira_agent.core.command import Command
from capoeira_agent.core.parser import parse_flags


class ModelCommand(Command):
    name = "model"
    description = "Altera o modelo ativo: /model <nome> [--base-url URL] [--timeout SEG] [--new-chat true|false]"

    def execute(self, args):
        h = self.context.config.host
        flags = parse_flags(args)

        if not args or args[0].startswith("--"):
            print("uso: /model <nome> [--base-url <url>] [--timeout <seg>] [--new-chat true|false]")
            print(f"atual: model={h.model} base_url={h.base_url} timeout={h.timeout} new_chat={h.new_chat}")
            return

        h.model = args[0]
        self.context.client.model = args[0]
        print(f"modelo: {h.model}")

        if flags.get("base-url"):
            h.base_url = str(flags["base-url"]).rstrip("/")
            print(f"base_url: {h.base_url}")
        if flags.get("timeout"):
            h.timeout = int(flags["timeout"])
            self.context.client.timeout = h.timeout
            print(f"timeout: {h.timeout}s")
        if "new-chat" in flags:
            nc = flags["new-chat"]
            h.new_chat = (str(nc).lower() in ("true", "1")) if isinstance(nc, str) else True
            print(f"new_chat: {h.new_chat}")