# 📜 Software Specification — CapoeiraAgent

**Projeto:** CapoeiraAgent
**Versão:** `0.1.3` — Draft
**Status:** `Proposta para revisão`
**Data:** 1 de Outubro de 2026

---

## 1. Visão Geral e Objetivos

### 1.1. Propósito

O **CapoeiraAgent** é um agente **Python** que executa **localmente** os comandos
emitidos por uma LLM Web (Gemini, Claude, Microsoft 365 Copilot, ChatGPT) através do
gateway [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host) (**v2.1.0**,
protocolo **textual** — form-urlencoded → `text/plain`).

Ao contrário do
[CapoeiraCode](https://github.com/ezequielrribeiro/capoeira-code), a TUI do CapoeiraAgent
**não serve para digitar prompts ao LLM**. Ela serve para:

- **monitorar** o chat ativo na interface Web (transcript, eventos, resultados);
- **aceitar/rejeitar** a execução de comandos emitidos pela LLM (permission gate);
- executar **comandos da ferramenta** ligados ao escopo do projeto (ex.: `/init`,
  `/inject-environment`) e demais comandos/plugins.

A comunicação com a LLM ocorre **exclusivamente** via CapoeiraHost. Por padrão o agente
opera com **`new_chat=false`**: o objetivo é **expandir as capacidades da LLM na interface
web e não substituir essa interface** — o usuário continua conversando na aba do navegador
normalmente, com o adendo de que essa conversa pode fazer a LLM **invocar comandos que
serão executados localmente pelo agente** (leitura/escrita de arquivos, execução de shell,
comandos de projeto/plugins), caso necessário.

### 1.2. Bases do projeto

| Base | Papel |
|---|---|
| **CapoeiraCode** | Arquitetura de agente, contrato de ferramentas ([TOOLS] textual), execução de tools (`read_file`, `list_dir`, `run_shell`, `run_python`, `write_file`, `ask_user`, `done`), aplicador atômico, armazenamento/artefatos, política de permissão. |
| **CapoeiraHost (>= 2.3.0)** | Único backend de comunicação, usado de forma **unidirecional**: `/api/chat` (textual) injeta o texto no LLM web e devolve a resposta **sincronamente**. O agente não mantém API local nem registro — o **retorno** é lido pelo agente da **área de transferência** (o usuário copia a resposta do chat com Ctrl+C). |
| **Cli-Crivonansky** | Framework CLI extensível: `core/command.py`, `registry`, `loader` (descoberta dinâmica de plugins via importlib), `context`, `parser`. |

### 1.3. Problema de Negócio

Usuários acessam LLMs apenas pela interface Web (sem API paga), mas precisam que a LLM
consiga **agir localmente** (ler/alterar arquivos do projeto, rodar comandos). Sem um agente,
conversas na Web são read-only do ponto de vista local. O CapoeiraAgent preenche essa lacuna:
a LLM continua parecendo "apenas um chat web", porém ganha braços locais — sob controle e
permissão do usuário.

### 1.4. Escopo — O QUE NÃO É

- ❌ Substituir a interface Web da LLM (a conversa acontece na aba; o agente não digita prompts em seu lugar).
- ❌ CLI/one-shot de digitação de prompts (o motor de instrução do CapoeiraCode não é replicado).
- ❌ Redução de contexto via AST/Tree-Sitter (fora de escopo nesta versão).
- ❌ Rodada JSON no fio (o CapoeiraHost é textual).

---

## 2. Arquitetura do Sistema

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│                            CAPOEIRA AGENT (Python)                               │
│                                                                                   │
│  ┌──────────────┐    ┌───────────────────┐    ┌───────────────────────────────┐   │
│  │ TUI          │    │ MONITOR           │    │ PERMISSION GATE               │   │
│  │  · monitor   │◀──▶│  · clipboard poll │───▶│  · auto | ask | readonly      │   │
│  │  · aprovação │    │  · handle_response│    │  · y/n/a (sempre na sessão)   │   │
│  │  · /comandos │    │  · round-trip     │    └──────────────┬────────────────┘   │
│  │  · plugins   │    └─────────┬─────────┘                   │ aprovou?           │
│  └──────────────┘              │                             ▼                    │
│                                │                     [TOOL] executores           │
│                                │              (read/list/run_shell/run_python/  │
│                                │               write_file/ask_user/done +plugins)│
│                                │                     + ChangeApplier atômico     │
│                                │                      + framework de comandos    │
└────────────────────────────────┼──────────────────────────────────────────────────┘
                                 │ HTTP (form-urlencoded → text/plain)
                                 │ 127.0.0.1:8765  (só injeção)
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                              CAPOEIRAHOST (>= 2.3.0)                          │
│      /api/chat (síncrono, devolve o texto do LLM) · /api/ps · /api/tags        │
└────────────────────────────────┬───────────────────────────────────────────────┘
                                 │ WS 127.0.0.1:8766 (JSON, nosso)
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                       EXTENSÃO MV3 (bridge + adapters)                        │
│                       SEND_PROMPT (DOM) · READ_CHAT                           │
└────────────────────────────────┬───────────────────────────────────────────────┘
                                 │ DOM (texto puro)
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                       WEB LLM INTERFACE (aba autenticada)                     │
│                usuário continua conversando NORMALMENTE aqui                  │
└────────────────────────────────┬───────────────────────────────────────────────┘
                                 │ Ctrl+C (usuário copia a resposta)
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                 CLIPBOARD DO SO (monitorado pelo agente)                      │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Estado:** proposta (draft). Nenhum módulo implementado ainda.

---

## 3. Conceitos

| Conceito | Definição |
|---|---|
| **Chat ativo** | Conversa aberta na aba autenticada do provedor Web (Gemini/Claude/Copilot 365...), observada pelo agente. |
| **Sessão do agente** | Contexto local por projeto (config + workspace + histórico). Persistente e retomável. |
| **Turno** | Unidade de transcrição do chat: `[USER] ...` ou `[ASSISTANT] ...` (contrato textual do host). |
| **Dicionário de comandos** | Contrato `tools` (textual) enviado ao host; define o que a LLM pode invocar. |
| **Escuta (listening)** | Monitor de **clipboard** do agente: detecta a cópia da resposta do LLM (Ctrl+C) e a processa. |
| **Permission gate** | Política que decide se um comando remoto é executado, questionado ou negado. |
| **Comando (tool)** | Operação executável localmente (core tool ou comando-plugin). Invocável pela LLM via `[TOOL_CALL]` e/ou via TUI (`/...`). |

---

## 4. Requisitos de Ambiente

- Python **3.10+** (multiplataforma).
- [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host) **>= 2.3.0** rodando
  em loopback (API `127.0.0.1:8765`, WS `127.0.0.1:8766`) com a extensão carregada e uma
  aba autenticada do provedor **aberta**. O agente **não** sobe API local: o retorno vem
  da área de transferência do SO.
- Chrome/Edge para a extensão MV3.
- ⚠️ Respeitar o **disclaimer do CapoeiraHost**: ferramenta de baixo volume (fila FIFO, um
  turno por vez; risco de rate-limit). O agente deve ser **conservador no volume**.

---

## 5. Comunicação com o CapoeiraHost (textual)

Protocolo único: **`application/x-www-form-urlencoded`** nas requisições e **`text/plain`**
nas respostas. Sem JSON no fio (exceto `models.json` do host e o bridge WS host⇄extensão).

> **Atualização host >= 2.3.0 (unidirecional + clipboard):** o host passou a ser
> **só injeção**: `/api/chat` e `/api/generate` devolvem a resposta do LLM **síncronamente**
> no corpo (`text/plain`) — não há mais push, `/api/app/*` nem watcher de `CHAT_UPDATE`.
> O agente continua usando o host apenas para injetar (`/inject-environment` e round-trip);
> o **retorno** é obtido do **clipboard** do SO (`clipboard.py` + `listener`): o usuário
> copia a resposta do chat (Ctrl+C) e o agente detecta a mudança, faz o parse e executa.

### 5.1. `POST /api/chat` — conversa / round-trip de tools

Campos: `model`*, pares repetidos `role`/`content`, `stream`, `new_chat`, `option.<chave>`.

- **`new_chat`** — default **`false`** no agente (configurável). Com `false`: a extensão
  injeta no chat aberto; o system do perfil só é emitido **na primeira interação da
  sessão**; nas iterações seguintes vai só o transcript (sem repetir o system) até um
  `new_chat=true` reiniciar. O **round-trip usa sempre `new_chat=false`** (continua o chat).
- **Roles aceitos:** `user|assistant|system` (qualquer outro, inclusive `tool`, é
  descartado pelo host → `400` se não sobrar mensagem).
- **Contrato de tools:** o agente embute o dicionário de comandos **no conteúdo da
  própria mensagem `role=system`** — `[TOOL] name=X | desc=... | arg:type` (uma por
  linha) + a instrução de emissão `[TOOL_CALL] nome | chave=valor` (`injector`/
  `prompts.build_tools_block`). Não há campo `tools` no form.
- **Round-trip:** o resultado de cada execução volta ao modelo como **turno `assistant`**
  com conteúdo `[TOOL_RESULT] (id) resultado` — `llm_client.chat` faz essa serialização
  quando uma mensagem interna tem `role=tool`/`tool_call_id`. Envia-se **apenas o resultado
  do turno**, nunca o histórico/header (evita que o modelo releia `[TOOL_CALL]` antigos).
- Resposta: `text/plain`, devolvida **sincronamente** pelo host. Para o envio de injeção, o
  ack `accepted: {request_id}` de versões anteriores deixou de existir; a leitura da resposta
  do modelo passa a ser via **clipboard**.
- **Valores** `[TOOL_CALL]`: números/booleans diretos; strings com espaço entre `'...'`;
  `|` fora de aspas separa argumentos; múltiplas linhas = chamadas paralelas.

### 5.2. Retorno via clipboard (usuário → agente)

O host **não entrega** a resposta: o usuário copia o texto do LLM no chat web (Ctrl+C) e o
agente monitora a área de transferência do SO (`clipboard.py`, polling configurável via
`host.clipboard_poll`). Ao detectar mudança, o texto é normalizado, os `[TOOL_CALL]` são
extraídos (`parse_tool_calls`) e o turno é processado como em §6.

- Sem API local no agente, sem registro no host, sem polling HTTP.
- Turnos idênticos recentes são ignorados (proteção anti-loop) e há teto de rounds (§6.3).
- Prosa sem `[TOOL_CALL]` é ignorada (a conversa continua na aba Web, visível ao usuário).

### 5.3. Conteúdo binário/arquivos — base64 estrito

Para robustez de transporte (o fio é texto puro), **todo conteúdo de arquivo/código/diff**
que viaja em `[TOOL_CALL]` (ex.: `write_file.code_content`, `run_python.code`) é **base64
estrito** (bloco contínuo `A-Za-z0-9+/=`, sem quebras de linha; charset UTF-8). Base64
inválido/truncado ⇒ o agente **não executa/grava** e devolve `role:"tool"` com erro
instruindo o reenvio em uma única linha. (Contrato herdado do CapoeiraCode §5.1.)

---

## 6. Monitor de Clipboard (Listener) — fluxo de funcionamento

### 6.1. Ciclo nominal

1. **Preparação** — `capoeira-agent "<pasta raiz>"` abre a TUI; cria/recarrega a sessão do
   projeto; resolve configuração (host, modelo, política). O monitor está **parado** até
   iniciado (ver `/listen`).
2. **Injeção de ambiente** — `/inject-environment` envia `POST /api/chat` com
   `new_chat=false` + mensagem `role=system` contendo o perfil do projeto e o **contrato
   completo de tools embutido no texto** (linhas `[TOOL] ...` + instrução
   `[TOOL_CALL] nome | chave=valor` — `prompts.build_tools_block`). Como é a **primeira
   interação da sessão**, o system do perfil é emitido na aba aberta. A partir daí a LLM
   **conhece os comandos disponíveis**.
3. **Monitor** — `/listen` inicia a thread de polling do **clipboard** (`clipboard.py`,
   intervalo `host.clipboard_poll`). Não há API local nem polling HTTP: o retorno vem da
   área de transferência.
4. **Processamento da mudança** — ao detectar mudança no clipboard, o texto é normalizado;
   se contiver `[TOOL_CALL] nome | chave=valor` (1+ linhas), os comandos são executados:
   - **Sem** `[TOOL_CALL]` ⇒ turno de prosa (a LLM respondeu normalmente); nada a executar.
   - **Com** `[TOOL_CALL]` ⇒ comandos a executar.
5. **Permission gate** — para cada chamada: leitura automática; escrita/execução conforme
   política (`auto`/`ask`) e modo (`readonly`) — ver §9. Em `ask`, a TUI notifica e aguarda
   `y`/`n`/`a`.
6. **Execução** — roda cada passo no diretório do projeto (subprocess/timeout/saída truncada),
   aplica `write_file` via applier atômico (RNF-04), executa comandos-plugin.
7. **Round-trip** — o host é pass-through e não aceita `role=tool`; portanto o resultado é
   serializado **no texto do próprio transcript** como turno `assistant` com
   `[TOOL_RESULT] (call_N) ...` via `POST /api/chat` (`new_chat=false`). **Envia-se apenas o
   resultado do turno**, nunca o histórico/header (evita loop). A resposta seguinte aparece na
   aba Web; o usuário copia de novo e o ciclo se repete até a resposta ser **prosa final**
   (sem `[TOOL_CALL]`), com proteção de limite de rounds.

### 6.2. Controle

| Ação | Descrição |
|---|---|
| `/listen` | inicia o monitor de clipboard. Se ainda não houve injeção, recomenda `/inject-environment` antes. |
| `/listen stop` | encerra o monitor de clipboard. |
| `Ctrl+C` (no chat web) | copia a resposta da LLM — é o gatilho do processamento. |

### 6.3. Robustez

- O agente **não faz polling HTTP**: o retorno vem do clipboard; uso de rede só na injeção.
- Falha de transiente (`503` offline) na injeção/round-trip ⇒ log + retomada; não desliga o
  monitor.
- Proteção contra loop/reexecução: turnos idênticos recentes são ignorados (janela de 30s) e
  há limite de rounds consecutivos (máx. 12).

---

## 7. Dicionário de Comandos expostos à LLM

O `tools` enviado ao host = **tools core** + **comandos-plugin** que declararem definição de
tool. Um comando é **invocável pela LLM** apenas se expuser `tool_def` (nome, desc, args).

### 7.1. Tools core (herdados do CapoeiraCode)

| Tool | Args | Permissão |
|---|---|---|
| `read_file` | `path` | automática |
| `list_dir` | `path` | automática |
| `run_shell` | `cmd` | política (ask/auto) |
| `run_python` | `code` (base64) | política (ask/auto) |
| `write_file` | `file_path`, `action` (create_file/replace_symbol/patch_diff), `code_content` (base64) | política (ask/auto) |
| `ask_user` | `message` | bloqueante na TUI |
| `done` | — | encerra o round-trip |

### 7.2. Comandos-plugin

Cada plug-in pode expor uma tool ao declarar `tool_def`. O dicionário completo é montado por
`/inject-environment` e **atualizado a cada injeção**. Comandos de ferramenta da TUI que **não**
expõem `tool_def` ficam fora do dicionário (inacessíveis à LLM — princípio de menor privilégio).

### 7.3. Contrato de tools (bloco embutido no texto — `prompts.build_tools_block`)

Como o host é **pass-through**, o dicionário viaja no conteúdo da mensagem `role=system` do
`/inject-environment`, um tool por linha prefixado com `[TOOL]` + o contrato de emissão
`[TOOL_CALL] nome | chave=valor`:

```text
[TOOL] name=read_file | desc=Lê um arquivo do projeto. | path:string
[TOOL] name=write_file | desc=Escreve/edita arquivo (base64). | file_path:string | action:string | code_content:string
[TOOL] name=deploy | desc=Comando-plugin exemplo: rotina de deploy do projeto. | env:string

Se for necessário chamar uma ferramenta, emita EXATAMENTE uma linha por chamada neste formato:
[TOOL_CALL] nome_da_ferramenta | chave1=valor1 | chave2=valor2
```

---

## 8. Framework de Comandos/Plugins (estilo Crivonansky)

- **Base:** `core/command.py` — `Command` (ABC) com `name`, `description`, `execute(self,
  args)` e `tool_def` opcional + suporte a flags (`--flag valor`).
- **Registro:** `core/registry.py` — `register/get/all`.
- **Descoberta:** `core/loader.py` — importlib em `commands/` (classes que herdam de
  `Command`; nome prefixado com `/` na TUI).
- **Contexto:** `core/context.py` — injeção de dependências (sessão, client, listener,
  permissions, TUI).
- **Parser:** `core/parser.py` — entrada `/comando --flag valor`.
- **Geração:** `/generate-plugin --name <nome>` cria um plug-in novo (estilo Crivonansky),
  opcionalmente `--tool "nome:desc"` para já expor `tool_def`.
- **Escopo:** pastas de plugins descobertas em **hierarquia** (projeto primeiro, depois
  config dir, depois package — a TUI mostra a origem). **A validar.**

---

## 9. Permissões

### 9.1. Modos de política (config)

| Modo | Comportamento |
|---|---|
| `auto` | executa comandos de escrita/execução sem perguntar |
| `ask` | **default**: pergunta a cada comando de escrita/execução |
| `readonly` | nega qualquer escrita/execução (leituras seguem) |

### 9.2. Durante a sessão (na aprovação)

Na TUI, para cada comando pendente: **`y`** (permitir), **`n`** (negar), **`a`** (permitir
**sempre na sessão ativa** — mante-se até encerrar a sessão ou `/reset`).

### 9.3. Regras

- Leitura (`read_file`, `list_dir`) é sempre automática.
- `ask_user` só informa veredito (não é permissionado); vira contexto.
- Quando um comandando-plugin é invocado pela LLM, segue a mesma política (categoria
  configurável por comando).
- Desaprovação ⇒ `role:tool` com "comando negado pelo usuário" (nunca executa).

---

## 10. TUI e Comandos

### 10.1. Entrada

```text
capoeira-agent [PATH] [--config DIR] [--project NOME] [--session NOME] [--model M]
               [--base-url URL] [--timeout SEG]
               [--policy auto|ask|readonly] [--readonly] [--new-chat true|false] [--help]
python -m capoeira_agent [PATH] [...]      # equivalente
```

`PATH` padrão = diretório atual. `--readonly` ⇒ política readonly. `--new-chat` default
**false** (sobrescreve a config global por invocação).

### 10.2. Painel de monitor

Regiões/insights: estado do provider (`/api/ps`), último turno do chat, fila de
aprovações pendentes, histórico de comandos executados/negados compatível com o `session.jsonl`.

### 10.3. Comandos core

| Comando | Descrição |
|---|---|
| `/help` | ajuda |
| `/init` | cria os **artefatos iniciais do projeto** (árvore de arquivos; pastas `specs/` e `skills/` com exemplos; pasta de comandos-plugin com exemplo; `README` de uso). **Local a validar** (§11.2). |
| `/inject-environment` | envia ao chat ativo o prompt com o ambiente do projeto + **dicionário de comandos** (`tools`), via `POST /api/chat` (`new_chat=false`). O host injeta e devolve a resposta sincronamente (descartada); o retorno útil vem pelo clipboard. Idempotente; re-emite (a pedido) para atualizar o dicionário. |
| `/listen` · `/listen stop` | inicia/encerra o **monitor de clipboard** (gatilho do processamento é o Ctrl+C no chat). |
| `/status` | provider/modelo online, sessão, política, estado do monitor (poll do clipboard). |
| `/permissions [auto|ask|readonly]` | ver/trocar política. |
| `/model M` · `/base-url URL` · `/timeout SEG` | parâmetros de comunicação (estilo CapoeiraCode). |
| `/new-chat [true|false]` | alternar reuso do chat na aba. |
| `/sessions` · `/use NOME` · `/reset` | multi-sessões/histórico. |
| `/generate-plugin --name X` | cria plug-in (ver §8). |
| `/quit` · `Ctrl+D` | sair. |

### 10.4. Stack

TUI com `prompt_toolkit` + `rich` (como o CapoeiraCode). Aprovações e eventos aparecem como
notificações; digitação de comandos acontece na linha de prompt.

---

## 11. Armazenamento

### 11.1. Diretório de configuração (global)

Resolução: `CAPOEIRA_AGENT_CONFIG_DIR` → `%APPDATA%\CapoeiraAgent` → `~/.capoeira-agent`.

```
CapoeiraAgent/
├── config.yaml               # host, modelo, política, new_chat, clipboard_poll, python
├── projects/*.yaml           # premissas por projeto (estilo CapoeiraCode: name, desc, stack, comandos-plugin selecionados)
├── commands/                 # plugins compartilhados (opcional)
├── specs/ · skills/ · prompts/  # instruções por projeto (carregadas na injeção de ambiente)
└── configs/<slug>/
    ├── workspace/            # artifacts: tree.txt, session.jsonl, estado
    └── sessions/<nome>/session.jsonl   # histórico de turnos + execuções (retomável; default: default)
```

### 11.2. Artefatos criados por `/init` — **a validar**

Premissa sugerida (híbrida): `/init` escreve **no diretório do projeto**:

```
<pasta raiz do projeto>/
├── specs/                    # exemplos .md
├── skills/                   # exemplos .md
├── commands/                 # exemplo de plug-in (além do core/config)
├── .capoeira-agent/          # estado runtime local do agente (cache)
└── README-agente.md          # instruções de uso
```

Configuração global/per-servidor e workspace de sessão permanecem no diretório de config
(§11.1). *(Alternativa: tudo no config dir, estilo CapoeiraCode — decidir na revisão.)*

### 11.3. Sessão

`session.jsonl` grava: turnos observados (user/assistant), comandos solicitados pela LLM,
veredito de aprovação, resultados (`ok/erro`) e timestamps. Serve de log auditável.

---

## 12. Configuração

### 12.1. `config.yaml` (exemplo)

```yaml
host:
  base_url: http://127.0.0.1:8765
  model: gemini-pro
  timeout: 180
  new_chat: false          # default do agente
  clipboard_poll: 0.5      # intervalo (s) de polling da área de transferência
policy:
  mode: ask                # auto | ask | readonly
  auto_plugins: []         # nomes de comandos sempre autorizados (modo ask)
python: python3            # intérprete para run_python/subprocess
projects:
  default: ""              # slug padrão (inferido do PATH)
```

### 12.2. Env (overlay)

`CAPOEIRA_AGENT_CONFIG_DIR`, `CAPOEIRA_AGENT_BASE_URL`, `CAPOEIRA_AGENT_MODEL`,
`CAPOEIRA_AGENT_NEW_CHAT`, `CAPOEIRA_AGENT_POLICY`, `CAPOEIRA_AGENT_CLIPBOARD_POLL`.

### 12.3. Por projeto

`projects/<slug>.yaml` (estilo CapoeiraCode): `name`, `description`, `stack`, `structure`
(para árvore do `/init`), `commands` (plugins do projeto a carregar e, opcionalmente,
exposição `tool_def`), `specs`/`skills` selecionados (para injeção de ambiente).

---

## 13. Multiplataforma (Windows · Linux · macOS)

### 13.1. Instalação (idêntica via venv + pip)

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Windows
.venv/bin/python -m pip install -r requirements-dev.txt       # Linux/macOS
.venv\Scripts\python -m pip install -e .                      # entry 'capoeira-agent'
```

### 13.2. Reconhecimento

Python CLI + `Path`/`os` (`C:\...` vs `/...`); subprocess sem shell onde possível; nenhuma
dependência nativa compilada (apenas stdlib + `prompt_toolkit` + `rich` + `PyYAML`). A leitura
da área de transferência é feita por plataforma em `clipboard.py` (Windows via Win32/ctypes
com fallback PowerShell; macOS via `pbpaste`; Linux via `wl-paste`/`xclip`/`xsel`) — **sem
dependências externas**.

---

## 14. Requisitos Não-Funcionais (RNF)

- **RNF-01 (Segurança Local):** comunicação só com loopback (`127.0.0.1`); comandos executam
  no diretório do projeto com timeout e sem env de segredos; nada é gravado sem validação/aprovação.
- **RNF-04 (Atomicidade):** `write_file` e lotes multi-arquivo aplicados via
  tmp + `os.replace` all-or-nothing (herdado do CapoeiraCode); sem escrita parcial.
- **RNF-05 (Não-interferência):** o agente nunca dispara geração por conta própria; só reage
  a comandos **copiados pelo usuário** (clipboard) — a interface web continua sendo a
  experiência primária.
- **RNF-06 (Volume conservador):** 1 requisição em andamento por vez; respeito à fila FIFO e
  ao disclaimer do host.
- **RNF-07 (Auditoria):** toda execução remota registrada no `session.jsonl` (comando, veredito,
  resultado).
- **RNF-08 (Multiplataforma):** Windows/Linux/macOS com procedimentos equivalentes.
- **RNF-09 (Textual):** sem JSON no fio; base64 estrito para conteúdo binário/code.

---

## 15. Estrutura de Diretórios do Projeto (prevista)

```text
capoeira-agent/
├── capoeira_agent/
│   ├── __init__.py
│   ├── entry.py             # `capoeira-agent [PATH] [flags]` → TUI (única interface)
│   ├── llm_client.py        # /api/chat (urllib; text) — só injeção
│   ├── prompts.py           # contrato TOOLS_CONTRACT; builder do /inject-environment
│   ├── config.py            # resolve config dir; config.yaml + env overlay; premises
│   ├── session.py           # configs/<slug>/ + session.jsonl
│   ├── clipboard.py         # leitura da área de transferência do SO (multiplataforma)
│   ├── listener.py          # monitor de clipboard + round-trip de tools
│   ├── permissions.py       # PermissionGate (auto/ask/readonly; y/n/a na sessão)
│   ├── executor.py          # apply_step: read/list/run_shell/run_python/write_file/ask_user
│   ├── applier.py           # aplicador atômico multi-arquivo (write_file)
│   ├── init_project.py      # /init: árvore + specs/skills/commands exemplos
│   ├── injector.py          # /inject-environment: prompt de ambiente + dicionário de tools
│   ├── core/                # framework de comandos (estilo Crivonansky)
│   │   ├── command.py       # base Command (+ tool_def)
│   │   ├── registry.py      # registro de comandos + dicionário de tools p/ LLM
│   │   ├── loader.py        # descoberta dinâmica (importlib; projeto → config → package)
│   │   ├── parser.py        # parsing `/comando --flag valor`
│   │   └── context.py       # injeção de dependências
│   ├── commands/            # plugins core (descoberta automática)
│   │   ├── init.py · inject_environment.py · listen.py · status.py
│   │   ├── permissions.py · sessions.py · help.py · generate_plugin.py ...
│   └── tui/
│       ├── app.py           # prompt_toolkit + rich; monitor + input de comandos
│       └── monitor.py       # painel de estado/eventos/aprovações
├── tests/                   # pytest (client fake do host; clipboard monkeypatch; policies; tools)
├── examples/                # config.yaml template + projects/<slug>.yaml
├── pyproject.toml           # entry `capoeira-agent` (pip install -e .)
├── requirements.txt · requirements-dev.txt
├── conftest.py
├── AGENTS.md · README.md
└── specs/capoeira-agent-spec.md   # este arquivo
```

---

## 16. Módulos Principais — Interfaces-chave (proposta)

```python
# llm_client.py
class ChatReply: content: str  # resposta do host (síncrona)
class LLMClient(base_url, model, timeout):
    chat(messages, stream=False, new_chat=False) -> ChatReply
class LLMRequestError(Exception)
serialize_tools(tools: list[dict]) -> str

# clipboard.py
def read_clipboard() -> str | None

# listener.py
class Listener(client, session, permissions, tui):
    start() / stop()
    @property listening: bool
    handle_response(text: str) -> None       # parse [TOOL_CALL] → gate → exec → round-trip

# permissions.py
class PermissionGate(mode):
    can_read() -> True
    ask(step) -> bool            # 'y'/'n'/'a' (a = sempre na sessão)
    resolve(step) -> Decision    # auto | question | deny

# core/command.py
class Command(ABC):
    name: str; description: str; tool_def: ToolDef | None = None
    def execute(self, args: list[str]): ...
    def run_as_tool(self, params: dict[str,str]) -> str: ...   # forma LLM

# injector.py
def build_environment_blocks(session, premises, registry) -> str   # perfil + specs/skills + tools
def inject_environment(client, session, registry, new_chat=False) -> None
```

---

## 17. Roadmap / Iterações (proposta)

| Iteração | Entrega |
|---|---|
| **I1 — Esqueleto e host** | entry + TUI mínima + `config.py` + `llm_client` (`/api/chat`, só injeção) + teste com host fake. |
| **I2 — Framework de comandos** | `core/*` (Crivonansky) + `commands/` core + `/init` + `/generate-plugin`. |
| **I3 — Monitor + permissions** | clipboard (`clipboard.py`) + `handle_response`, permission gate (auto/ask/readonly, y/n/a), executor core + applier atômico. |
| **I4 — Injeção e round-trip** | `/inject-environment` (dicionário), base64 estrito, round-trip `role=tool`. |
| **I5 — Sessões e monitor** | `session.jsonl`, multi-sessões, painel de monitor. |
| **I6 — Premises/artefatos** | `projects/<slug>.yaml`, specs/skills/prompts, árvore do `/init` customizável. |
| **I7 — Distribuição** | docs multiplataforma, testes E2E (host fake + extensão fake). |

---

## 18. Itens "A validar" na revisão

1. **Local do `/init`** — projeto vs config dir (sugestão: híbrido — artefatos no projeto,
   workspace no config).
2. **Base de tools** — manutenção dos 7 tools do CapoeiraCode como core (sugerido) vs
   conjunto enxuto próprio.
3. **`/listen` público** (comando da TUI inicia o monitor de clipboard) vs monitor automático ao abrir.
4. **Hierarquia de plugins** — projeto → config → package (ordem de precedência).
5. **Política default** — `ask` para escrita/execução (sugerido), leitura automática.
6. **Versionamento mínimo** do CapoeiraHost: `>= 2.3.0` (modo síncrono e unidirecional).

---

## 19. Registro de Alterações

| Versão | Data | Descrição |
| --- | --- | --- |
| `0.1.0` | 15/09/2026 | Draft inicial da spec baseado em CapoeiraCode v6.0.0, CapoeiraHost **v2.1.0** (novos `/api/chat/read` e `/api/chat/watch` para o modo escuta) e Cli-Crivonansky (framework de plugins). |
| `0.1.1` | 21/09/2026 | Adequação ao CapoeiraHost **pass-through verbatim** (commit `d1d00ab`): sem `tools`/`role=tool`/`tool_call_id` na API; contrato de tools embutido no texto da mensagem de sistema (`prompts.build_tools_block`); round-trip de resultados via turno `assistant` com `[TOOL_RESULT] (id) ...` (`llm_client.chat`). |
| `0.1.2` | 28/09/2026 | Adequação ao CapoeiraHost **push** (commit `fb55cbb`): `/api/chat` responde `accepted: {request_id}` (fire-and-forget) e entrega a resposta via `POST /api/capoeira/response` na app registrada em `/api/app/register`. O agente sobe a API local (`receiver.py`, FastAPI/uvicorn) e processa respostas via `listener.handle_response` — sem polling (`/api/chat/read`/`watch` removidos). Removido o `Dockerfile`; a API do agente escuta em `127.0.0.1:8767`, porta distinta da API do host. |
| `0.1.3` | 01/10/2026 | Comunicação **unidirecional**: o CapoeiraHost passa a ser só injeção (modo **síncrono**, v2.3.0) e o **retorno é lido da área de transferência** (`clipboard.py` + monitor em `listener`). Removidos o receiver FastAPI/uvicorn do agente, o registro de app e o polling HTTP; o host removeu push, `/api/app/*` e watcher. Round-trip envia apenas o resultado do turno (`new_chat=false`) e há proteções anti-loop. |