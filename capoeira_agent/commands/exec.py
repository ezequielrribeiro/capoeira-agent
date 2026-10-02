from pathlib import Path

from capoeira_agent.core.command import Command
from capoeira_agent.core.parser import parse_flags


class ExecCommand(Command):
    name = "exec"
    description = "Executa [TOOL_CALL] de um texto colado (ou --file CAMINHO) e devolve o resultado à LLM"

    def execute(self, args):
        # O TUI preenche `raw_args` com o texto após "/exec" (preserva colado).
        raw = getattr(self, "raw_args", None)
        self.raw_args = None  # evita reuso do texto anterior
        if not raw:
            raw = " ".join(args)

        parsed = parse_flags(raw.split()) if raw else {}
        file_arg = parsed.get("file")
        if isinstance(file_arg, str):
            try:
                text = Path(file_arg).read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"não foi possível ler '{file_arg}': {exc}")
                return
            self._process(text)
            return

        if not raw.strip():
            print("uso: /exec <texto com [TOOL_CALL] ...>  |  /exec --file CAMINHO")
            print("dica: cole a resposta da LLM (com as linhas [TOOL_CALL]) após /exec")
            return
        self._process(raw)

    def _process(self, text: str) -> None:
        runner = getattr(self.context, "runner", None)
        if runner is None:
            print("runner não configurado")
            return
        try:
            outcome = runner.run_text(text, send_roundtrip=False)
        except Exception as exc:
            print(f"falha na execução: {exc}")
            return
        if not outcome.steps:
            print("nenhum [TOOL_CALL] encontrado no texto.")
            return
        for tool, allowed, result in outcome.executed:
            veredito = "ok" if allowed else "negado"
            detail = result.output.strip().splitlines()[0] if (result.ok and result.output) else (result.error or "")
            print(f"  {tool}: {veredito} — {detail[:100]}")
        for tool in outcome.unknown:
            print(f"  {tool}: não reconhecido (não executado)")
        if not outcome.messages:
            return
        try:
            runner.send_roundtrip(outcome)
        except Exception as exc:
            print(f"executado, mas o envio do resultado à LLM falhou: {exc}")
            return
        print("resultado enviado à LLM (round-trip); aguarde a próxima resposta no chat web.")
