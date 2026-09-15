# CapoeiraAgent

Agente Python que executa **localmente** comandos emitidos por uma LLM Web (Gemini, Claude,
Microsoft 365 Copilot, ChatGPT) via **CapoeiraHost** — sem substituir a interface web: o
usuário continua conversando normalmente na aba do navegador e a LLM pode invocar comandos
locais quando necessário.

- Base: [CapoeiraCode](https://github.com/ezequielrribeiro/capoeira-code)
- Comunicação: [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host) (**>= 2.1.0**,
  protocolo textual; endpoints `/api/chat`, `/api/chat/read`, `/api/chat/watch`)
- Extensibilidade: [Cli-Crivonansky](https://github.com/ezequielrribeiro/cli-crivonansky)
  (plugins de comando descobertos dinamicamente)

Spec: [`specs/capoeira-agent-spec.md`](specs/capoeira-agent-spec.md)

## Como funciona

1. Suba o CapoeiraHost (v2.1.0+) com a extensão carregada e uma aba autenticada do provedor aberta.
2. `capoeira-agent "<pasta raiz do projeto>"` abre a TUI de monitoramento.
3. `/init` — cria os artefatos iniciais do projeto (specs/skills/commands com exemplos).
4. `/inject-environment` — envia ao chat ativo o ambiente do projeto + o dicionário de
   comandos que a LLM pode invocar (`[TOOL_CALL]`).
5. `/listen` — o agente fica "na escuta" via `/api/chat/watch`: quando a LLM, respondendo
   normalmente no chat web, emitir um `[TOOL_CALL]`, o agente pede aprovação (conforme a
   política) e executa localmente, devolvendo o resultado ao chat.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Windows
.venv/bin/python -m pip install -r requirements-dev.txt       # Linux/macOS
.venv\Scripts\python -m pip install -e .                      # cria o entry `capoeira-agent`
```

Docker:

```bash
docker build -t capoeira-agent .
docker run -it -v "C:\projeto:/workspace" -p 127.0.0.1:8765:8765 capoeira-agent /workspace
```

## Configuração

Diretório de config: `CAPOEIRA_AGENT_CONFIG_DIR` → `%APPDATA%\CapoeiraAgent` → `~/.capoeira-agent`.
Veja `examples/config.yaml` e `examples/projects/sample.yaml`. Premissas por projeto em
`projects/<slug>.yaml`.

Variáveis de ambiente (overlay): `CAPOEIRA_AGENT_CONFIG_DIR`, `CAPOEIRA_AGENT_BASE_URL`,
`CAPOEIRA_AGENT_MODEL`, `CAPOEIRA_AGENT_NEW_CHAT`, `CAPOEIRA_AGENT_POLICY`,
`CAPOEIRA_AGENT_WATCH_TIMEOUT`.

## Comandos da TUI

`/help` · `/init` · `/inject-environment` · `/listen [stop]` · `/status` · `/read` ·
`/permissions [auto|ask|readonly]` · `/model` · `/base-url` · `/timeout` · `/new-chat` ·
`/sessions` · `/use` · `/reset` · `/generate-plugin` · `/quit`

## Testes

```bash
.venv\Scripts\python -m pytest -q
```

A suíte usa um fake CapoeiraHost (ThreadingHTTPServer) e não depende de navegador/serviços externos.