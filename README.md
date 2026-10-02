# CapoeiraAgent

Agente Python que executa **localmente** comandos emitidos por uma LLM Web (Gemini, Claude,
Microsoft 365 Copilot, ChatGPT) via **CapoeiraHost** — sem substituir a interface web: o
usuário continua conversando normalmente na aba do navegador e a LLM pode invocar comandos
locais quando necessário.

- Base: [CapoeiraCode](https://github.com/ezequielrribeiro/capoeira-code)
- Comunicação: [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host)
  (**protocolo textual pass-through verbatim**; endpoint `/api/chat` — o host não processa
  mais `tools`/`role=tool`: o agente formata o contrato de ferramentas no texto do próprio
  system e interpreta a resposta verbatim). A comunicação com o host é **unidirecional**
  (só injeção); o **retorno é obtido pelo agente via área de transferência**: o usuário copia
  a resposta da LLM no chat web (Ctrl+C) e o agente detecta a mudança, faz o parse e executa.
- Extensibilidade: [Cli-Crivonansky](https://github.com/ezequielrribeiro/cli-crivonansky)
  (plugins de comando descobertos dinamicamente)

Spec: [`specs/capoeira-agent-spec.md`](specs/capoeira-agent-spec.md)

## Como funciona

1. Suba o CapoeiraHost com a extensão carregada e uma aba autenticada do provedor aberta.
2. `capoeira-agent "<pasta raiz do projeto>"` abre a TUI de monitoramento.
3. `/init` — cria os artefatos iniciais do projeto (specs/skills/commands com exemplos).
4. `/inject-environment` — envia ao chat ativo o ambiente do projeto + o dicionário de
   comandos que a LLM pode invocar (`[TOOL_CALL]`).
5. `/listen` — inicia o monitor de clipboard. Quando a LLM emitir um `[TOOL_CALL]`, copie a
   resposta no chat web (Ctrl+C): o agente detecta a mudança no clipboard, pede aprovação
   (conforme a política), executa localmente e devolve o resultado ao chat via `/api/chat`.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Windows
.venv/bin/python -m pip install -r requirements-dev.txt       # Linux/macOS
.venv\Scripts\python -m pip install -e .                      # cria o entry `capoeira-agent`
```

## Configuração

Diretório de config: `CAPOEIRA_AGENT_CONFIG_DIR` → `%APPDATA%\CapoeiraAgent` → `~/.capoeira-agent`.
Veja `examples/config.yaml` e `examples/projects/sample.yaml`. Premissas por projeto em
`projects/<slug>.yaml`.

Variáveis de ambiente (overlay): `CAPOEIRA_AGENT_CONFIG_DIR`, `CAPOEIRA_AGENT_BASE_URL`,
`CAPOEIRA_AGENT_MODEL`, `CAPOEIRA_AGENT_NEW_CHAT`, `CAPOEIRA_AGENT_POLICY`,
`CAPOEIRA_AGENT_CLIPBOARD_POLL`.

Porta: o CapoeiraHost expõe a API em `127.0.0.1:8765` (só injeção). O agente não sobe
API local — o retorno vem da área de transferência (opção `clipboard_poll`, em segundos).

## Comandos da TUI

`/help` · `/init` · `/inject-environment` · `/listen [stop]` · `/status` ·
`/permissions [auto|ask|readonly]` · `/model` · `/base-url` · `/timeout` · `/new-chat` ·
`/sessions` · `/use` · `/reset` · `/generate-plugin` · `/quit`

## Testes

```bash
.venv\Scripts\python -m pytest -q
```

A suíte usa um fake CapoeiraHost (ThreadingHTTPServer) e não depende de navegador/serviços
externos; o clipboard é injetado via monkeypatch.