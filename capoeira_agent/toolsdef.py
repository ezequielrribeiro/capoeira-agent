"""Definições das tools core (herdadas do CapoeiraCode) expostas à LLM."""
from __future__ import annotations

CORE_TOOL_DEFS: list[dict] = [
    {"name": "read_file", "desc": "Lê o conteúdo de um arquivo do projeto.", "args": {"path": "string"}},
    {"name": "list_dir", "desc": "Lista o conteúdo de um diretório do projeto.", "args": {"path": "string"}},
    {"name": "run_shell", "desc": "Executa um comando de shell no diretório do projeto.", "args": {"cmd": "string"}},
    {"name": "run_python", "desc": "Executa código Python no diretório do projeto (code em base64).",
     "args": {"code": "string"}},
    {"name": "write_file", "desc": "Cria/edita arquivo do projeto (code_content em base64; "
                                   "action=create_file|replace|replace_symbol|patch_diff).",
     "args": {"file_path": "string", "action": "string", "code_content": "string"}},
    {"name": "ask_user", "desc": "Faz uma pergunta ao usuário na TUI e devolve a resposta.", "args": {"message": "string"}},
    {"name": "done", "desc": "Encerra o turno de execução de comandos.", "args": {}},
]

REMOTE_ONLY_TOOL = "done"