"""Contrato textual de tool calling e builders de prompt.

O CapoeiraHost é pass-through verbatim: quem formatar o tool calling (lista de
ferramentas + como emitir [TOOL_CALL]) é a ferramenta que consome o host — aqui,
o CapoeiraAgent — injetando o contrato no conteúdo da própria mensagem de sistema.
"""

TOOLS_HEADER = "Ferramentas disponíveis (uma por linha, formato chave=valor, sem JSON):"

TOOL_CALL_CONTRACT = (
    "Se for necessário chamar uma ferramenta, emita EXATAMENTE uma linha por chamada neste formato"
    "(sem blocos de código, sem JSON e sem marcação markdown):\n"
    "\n"
    "[TOOL_CALL] nome_da_ferramenta | chave1=valor1 | chave2=valor2\n"
    "\n"
    "- Valores: números e booleanos vão diretos; strings com espaço usam aspas simples ('...').\n"
    "- O separador '|' fora de aspas separa argumentos; dentro de aspas simples é literal.\n"
    "- Várias linhas [TOOL_CALL] em uma resposta viram chamadas paralelas.\n"
    "- Conteúdo de arquivo/código (write_file.code_content, run_python.code) viaja em base64 estrito.\n"
    "- Quando não for necessário chamar ferramenta, responda em prosa simples."
)

ENV_HEADER = (
    "Você é o assistente de um projeto local assistido pelo CapoeiraAgent. "
    "O usuário conversa com você normalmente nesta interface web; quando precisar atuar no "
    "computador do usuário, invoque os comandos abaixo em vez de apenas ''imaginar'' a ação.\n"
)


def build_environment_message(premises_name: str, description: str, blocks: list[str]) -> str:
    """Monta a mensagem de sistema/ambiente injetada pelo /inject-environment."""
    parts = [ENV_HEADER]
    if premises_name:
        parts.append(f"Projeto: {premises_name}")
    if description:
        parts.append(f"Descrição: {description}")
    if blocks:
        parts.append("\n".join(blocks))
    return "\n".join(parts)


def build_tools_block(tools: list[dict]) -> str:
    """Contrato completo do dicionário de comandos (linhas [TOOL] + instruções de
    emissão [TOOL_CALL]) — texto que vai no conteúdo da mensagem de sistema. Cada
    tool dict: {'name': str, 'desc': str, 'args': {nome: tipo}}."""
    if not tools:
        return "Nenhum comando remoto disponível neste momento."
    lines = [TOOLS_HEADER]
    for tool in tools:
        parts = [f"name={tool['name']}", f"desc={tool.get('desc', '')}"]
        for arg, typ in (tool.get("args") or {}).items():
            parts.append(f"{arg}:{typ}")
        lines.append("[TOOL] " + " | ".join(parts))
    lines.append(TOOL_CALL_CONTRACT)
    return "\n".join(lines)