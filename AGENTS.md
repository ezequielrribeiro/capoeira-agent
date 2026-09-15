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
- Protocolo textual do CapoeiraHost v2.1.0 (form-urlencoded → text/plain); jamais JSON no fio.
- `new_chat=false` por padrão (reuso do chat aberto na aba). `[/api/chat/read|watch]` usados pela escuta.
- Conteúdo de arquivo/código em tools viaja em base64 estrito (`_decode_b64` valida; inválido => não grava).
- Escrita é atômica (tmp + os.replace); lote multi-arquivo all-or-nothing (`ChangeApplier`).
- Novo comando: criar arquivo em `commands/` subclasses de Command; `tool_def` expõe à LLM.
- Sempre rode `pytest` após alterações.