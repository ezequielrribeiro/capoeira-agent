# Projeto: CapoeiraAgent (Python)

## Comandos
- Instalar dev + entry point:
  - Windows: `.venv\Scripts\python -m pip install -r requirements-dev.txt -e .`
  - Linux/macOS: `.venv/bin/python -m pip install -r requirements-dev.txt -e .`
- Testes: `.venv\Scripts\python -m pytest -q` (ou `.venv/bin/python -m pytest -q`)
- Executar: `capoeira-agent "<pasta raiz>"` (ou `python -m capoeira_agent.entry "<pasta raiz>"`)

## Estrutura
- `capoeira_agent/` — package principal
  - `core/` — framework de comandos/plugins (Command, Registry, Loader, Parser, Context)
  - `commands/` — plugins core descobertos automaticamente (cada um herda de Command)
  - `tui/` — TUI de monitor/aprovação (prompt_toolkit + rich)
- `tests/` — pytest (fake CapoeiraHost via ThreadingHTTPServer; sem serviços externos)

## Convenções
- Protocolo textual do CapoeiraHost (form-urlencoded → text/plain); jamais JSON no fio.
- **Pass-through verbatim** (host pós-21/09/2026): `/api/chat` **não** aceita `tools`, `role=tool` nem `tool_call_id`. O agente formata o contrato de tools (linhas `[TOOL] ...` + instrução `[TOOL_CALL] nome | chave=valor`) **no texto** da própria mensagem `role=system` (`injector`/`prompts.build_tools_block`). Resultados de tool voltam ao modelo como turno `assistant` com `[TOOL_RESULT] (id) conteúdo` (ver `llm_client.chat`).
- `new_chat=false` por padrão (reuso do chat aberto na aba).
- **Host só injeta** (host pós-01/10/2026): `/api/chat` é síncrono e o host não faz push nem registro de app. A **entrada dos comandos é a TUI**: o usuário cola a resposta da LLM (com `[TOOL_CALL]`) em `/exec <texto|--file CAMINHO>`; `runner.Runner` faz o parse (tolerante a markdown/bullet/negrito, ver `steps.parse_tool_calls`), aplica o permission gate, executa e faz o round-trip (`[TOOL_RESULT]`, `new_chat=false`). Sem listener de clipboard e sem API local no agente.
- Conteúdo de arquivo/código em tools viaja em base64 estrito (`_decode_b64` valida; inválido => não grava).
- Escrita é atômica (tmp + os.replace); lote multi-arquivo all-or-nothing (`ChangeApplier`).
- Novo comando: criar arquivo em `commands/` subclasses de Command; `tool_def` expõe à LLM.
- Sempre rode `pytest` após alterações.