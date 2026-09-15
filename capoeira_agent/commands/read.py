from capoeira_agent.core.command import Command
from capoeira_agent.llm_client import LLMRequestError


class ReadChatCommand(Command):
    name = "read"
    description = "Re-sincroniza o transcript e a revision via /api/chat/read"

    def execute(self, args):
        try:
            transcript, revision = self.context.client.read_chat()
        except LLMRequestError as exc:
            print(f"falha no /read: {exc}")
            return
        self.context.session.revision = revision
        self.context.session.save_state()
        if transcript.strip():
            self.context.session.append_message("system", f"[transcript sincronizado (rev {revision})]\n{transcript}")
        print(f"revision: {revision} · turnos no chat ativo: {len([l for l in transcript.splitlines() if l.strip()])}")
        if transcript.strip():
            print(transcript[:1200])