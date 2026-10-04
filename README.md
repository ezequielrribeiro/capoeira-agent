# CapoeiraAgent

Agente Python que executa **localmente** comandos emitidos por uma LLM Web (Gemini, Claude,
Microsoft 365 Copilot, ChatGPT) via **CapoeiraHost** — sem substituir a interface web: o
usuário continua conversando normalmente na aba do navegador e a LLM pode invocar comandos
locais quando necessário.

- Base: [CapoeiraCode](https://github.com/ezequielrribeiro/capoeira-code)
- Comunicação: [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host)
  (**protocolo textual pass-through verbatim**; endpoint `/api/chat` — o host não processa
  mais `tools`/`role=tool`: o agente formata o contrato de ferramentas no texto do próprio
  system e interpreta a resposta verbatim). O host é usado **só para injeção**; os comandos
  são **parseados e executados pela interface do agente**: você cola a resposta da LLM
  (com as linhas `[TOOL_CALL]`) em `/exec`.
- Extensibilidade: [Cli-Crivonansky](https://github.com/ezequielrribeiro/cli-crivonansky)
  (plugins de comando descobertos dinamicamente)

Spec: [`specs/capoeira-agent-spec.md`](specs/capoeira-agent-spec.md)

## Como funciona

1. Suba o CapoeiraHost com a extensão carregada e uma aba autenticada do provedor aberta.
2. `capoeira-agent "<pasta raiz do projeto>"` abre a TUI.
3. `/init` — cria os artefatos iniciais do projeto (specs/skills/commands com exemplos).
4. `/inject-environment` — envia ao chat ativo o ambiente do projeto + o dicionário de
   comandos que a LLM pode invocar (`[TOOL_CALL]`).
5. Quando a LLM emitir um `[TOOL_CALL]`, **cole a resposta** no agente:
   `/exec <texto colado>` (ou `/exec --file caminho`). O agente faz o parse, pede aprovação
   (conforme a política), executa localmente e devolve o resultado à LLM via `/api/chat`.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Windows
.venv/bin/python -m pip install -r requirements-dev.txt       # Linux/macOS
.venv\Scripts\python -m pip install -e .                      # cria o entry `capoeira-agent`
```

## Configuração

Diretório de config: `CAPOEIRA_AGENT_CONFIG_DIR` → `%APPDATA%\CapoeiraAgent` → `~/.capoeira-agent`.
Veja `examples/config.yaml`, `examples/projects/sample.yaml` e `examples/tools.yaml`. Premissas
por projeto em `projects/<slug>.yaml`.

### `tools.yaml` — comandos injetados (editável)

O dicionário de comandos enviado à LLM pelo `/inject-environment` é controlado por
`<config_dir>/tools.yaml`: cada comando com `enabled: false` é removido do bloco `[TOOL]`.
`/init` cria o arquivo com todos os comandos habilitados; sem o arquivo, todos permanecem
habilitados.

Variáveis de ambiente (overlay): `CAPOEIRA_AGENT_CONFIG_DIR`, `CAPOEIRA_AGENT_BASE_URL`,
`CAPOEIRA_AGENT_MODEL`, `CAPOEIRA_AGENT_NEW_CHAT`, `CAPOEIRA_AGENT_POLICY`.

Porta: o CapoeiraHost expõe a API em `127.0.0.1:8765` (só injeção). O agente não sobe API
local — a entrada dos comandos é a própria TUI (`/exec`).

## Comandos da TUI

`/help` · `/init` · `/inject-environment` · `/exec <texto|--file CAMINHO>` · `/status` ·
`/permissions [auto|ask|readonly]` · `/model` · `/base-url` · `/timeout` · `/new-chat` ·
`/sessions` · `/use` · `/reset` · `/generate-plugin` · `/quit`

### `/exec` — executar os comandos da LLM

Cole a resposta da LLM (com as linhas `[TOOL_CALL]`) após `/exec`:

```text
/exec Claro, vou listar:
[TOOL_CALL] list_dir | path='.'
```

O agente faz o parse (tolerante a marcação de markdown/bullet/negrito), aplica a política
de permissão, executa e envia o resultado de volta à LLM (`[TOOL_RESULT]`, round-trip em
`new_chat=false`). Também é possível ler de um arquivo: `/exec --file resposta.txt`.

## Testes

```bash
.venv\Scripts\python -m pytest -q
```

A suíte usa um fake CapoeiraHost (ThreadingHTTPServer) e não depende de navegador/serviços
externos.