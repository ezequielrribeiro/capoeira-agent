# 📜 Software Specification — CapoeiraAgent

**Projeto:** CapoeiraAgent
**Versão:** `0.1.0` — Draft
**Status:** `Proposta para revisão`
**Data:** 15 de Setembro de 2026

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
| **CapoeiraHost (v2.1.0+)** | Único backend de comunicação; `/api/chat` (textual) responde `accepted: {request_id}` (fire-and-forget) e entrega a resposta do LLM via **push** (`POST /api/capoeira/response`) na aplicação registrada em `/api/app/register` — habilita o modo "na escuta" sem substituir a interface web. |
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
│  │ TUI          │    │ LISTENER          │    │ PERMISSION GATE               │   │
│  │  · monitor   │◀──▶│  · receiver (push)│───▶│  · auto | ask | readonly      │   │
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
                                 │ 127.0.0.1:8765
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                              CAPOEIRAHOST (v2.1.0+)                           │
│      /api/chat · /api/app/register · /api/ps · /api/tags                       │
└────────────────────────────────┬───────────────────────────────────────────────┘
                                 │ WS 127.0.0.1:8766 (JSON, nosso)
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                    EXTENSÃO MV3 (watcher de DOM + bridge)                     │
│        CHAT_UPDATE (delta) · READ_CHAT · SEND_PROMPT (sem eco do agente)      │
└────────────────────────────────┬───────────────────────────────────────────────┘
                                 │ DOM (texto puro)
┌────────────────────────────────▼───────────────────────────────────────────────┐
│                       WEB LLM INTERFACE (aba autenticada)                     │
│                usuário continua conversando NORMALMENTE aqui                  │
└────────────────────────────────────────────────────────────────────────────────┘

O host entrega a resposta do LLM à API local do agente (receiver) via
`POST http://127.0.0.1:8767/api/capoeira/response` (JSON) — porta distinta da API do host.
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
| **Escuta (listening)** | API local do agente (receiver) na escuta do push do host, aguardando a resposta do LLM. |
| **Permission gate** | Política que decide se um comando remoto é executado, questionado ou negado. |
| **Comando (tool)** | Operação executável localmente (core tool ou comando-plugin). Invocável pela LLM via `[TOOL_CALL]` e/ou via TUI (`/...`). |

---

## 4. Requisitos de Ambiente

- Python **3.10+** (multiplataforma).
- [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host) **>= 2.1.0** rodando
  em loopback (API `127.0.0.1:8765`, WS `127.0.0.1:8766`) com a extensão carregada e uma
  aba autenticada do provedor **aberta**. A API local do agente (receiver do push) escuta em
  `127.0.0.1:8767` (porta distinta da API do host).
- Chrome/Edge para a extensão MV3.
- ⚠️ Respeitar o **disclaimer do CapoeiraHost**: ferramenta de baixo volume (fila FIFO, um
  turno por vez; risco de rate-limit). O agente deve ser **conservador no volume**.

---

## 5. Comunicação com o CapoeiraHost (textual)

Protocolo único: **`application/x-www-form-urlencoded`** nas requisições e **`text/plain`**
nas respostas. Sem JSON no fio (exceto `models.json` do host e o bridge WS host⇄extensão).

> **Atualização pós-v2.1.0 (pass-through verbatim — host 21/09/2026):** o CapoeiraHost
> **não processa mais tool calling**. `/api/chat` não aceita `tools` nem `role=tool`
> (somente `user|assistant|system`; `role=tool` é descartado → se não sobrar mensagem,
> `400`). O host devolve a resposta **verbatim** (sem extrair/limpar `[TOOL_CALL]`), o
> system segue **sem tags próprias** e `options` é aceito, porém ignorado. Todo o contrato
> de ferramentas (linhas `[TOOL] ...` + instrução `[TOOL_CALL] nome | chave=valor`) e a
> devolução de resultados são responsabilidade **exclusiva do CapoeiraAgent**, embutidos
> no texto das mensagens. `new_chat` default do host agora é `true`, mas o agente continua
> mandando `new_chat=false` por requisição.

### 5.1. `POST /api/chat` — conversa / round-trip de tools

Campos: `model`*, pares repetidos `role`/`content`, `stream`, `new_chat`, `option.<chave>`.

- **`new_chat`** — default **`false`** no agente (configurável). Com `false`: a extensão
  injeta no chat aberto; o system do perfil só é emitido **na primeira interação da
  sessão**; nas iterações seguintes vai só o transcript (sem repetir o system) até um
  `new_chat=true` reiniciar.
- **Roles aceitos:** `user|assistant|system` (qualquer outro, inclusive `tool`, é
  descartado pelo host → `400` se não sobrar mensagem).
- **Contrato de tools:** o agente embute o dicionário de comandos **no conteúdo da
  própria mensagem `role=system`** — `[TOOL] name=X | desc=... | arg:type` (uma por
  linha) + a instrução de emissão `[TOOL_CALL] nome | chave=valor` (`injector`/
  `prompts.build_tools_block`). Não há campo `tools` no form.
- **Round-trip:** o resultado de cada execução volta ao modelo como **turno `assistant`**
  com conteúdo `[TOOL_RESULT] (id) resultado` — `llm_client.chat` faz essa serialização
  quando uma mensagem interna tem `role=tool`/`tool_call_id`.
- Resposta: `text/plain` **verbatim** (prosa + linhas `[TOOL_CALL]` juntas, sem parse pelo
  host); o agente extrai as chamadas com `parse_tool_calls`.
- **Valores** `[TOOL_CALL]`: números/booleans diretos; strings com espaço entre `'...'`;
  `|` fora de aspas separa argumentos; múltiplas linhas = chamadas paralelas.

### 5.2. Push da resposta — `POST /api/capoeira/response` (host → agente)

O host entrega a resposta do LLM à aplicação registrada (a API local do agente) via
`POST http://<host>:<port>/api/capoeira/response` com corpo **JSON** contendo `request_id`,
`model`, `provider`, `endpoint` (`chat`/`generate`), `stream`, `text`, `timestamp` e, em
falha de geração, `error`. O agente **não faz polling** — apenas registra-se e processa as
respostas conforme chegam.

- Registro: `POST /api/app/register` (form `port`/`host`/`name`) vincula o destino do push;
  `POST /api/app/unregister` desfaz. Sem app registrada, o host tenta a porta padrão
  (`8767`) em best-effort.
- O agente sobe a API local (`receiver.py`, FastAPI/uvicorn) em `127.0.0.1:8767` e despacha
  cada payload para `listener.handle_response`.

### 5.3. Conteúdo binário/arquivos — base64 estrito

Para robustez de transporte (o fio é texto puro), **todo conteúdo de arquivo/código/diff**
que viaja em `[TOOL_CALL]` (ex.: `write_file.code_content`, `run_python.code`) é **base64
estrito** (bloco contínuo `A-Za-z0-9+/=`, sem quebras de linha; charset UTF-8). Base64
inválido/truncado ⇒ o agente **não executa/grava** e devolve `role:"tool"` com erro
instruindo o reenvio em uma única linha. (Contrato herdado do CapoeiraCode §5.1.)

---

## 6. Modo Escuta (Listener) — fluxo de funcionamento

### 6.1. Ciclo nominal

1. **Preparação** — `capoeira-agent "<pasta raiz>"` abre a TUI; cria/recarrega a sessão do
   projeto; resolve configuração (host, modelo, política). O listener está **parado** até
   iniciado (ver `/listen`).
2. **Injeção de ambiente** — `/inject-environment` (ou primeiro `/listen` sem injetar) envia
   `POST /api/chat` com `new_chat=false` + mensagem `role=system` contendo o perfil do
   projeto e o **contrato completo de tools embutido no texto** (linhas `[TOOL] ...` +
   instrução `[TOOL_CALL] nome | chave=valor` — `prompts.build_tools_block`). O host responde
   `accepted: {request_id}` (fire-and-forget); a resposta do modelo chega via push. Como é a
   **primeira interação da sessão**, o system do perfil é emitido na aba aberta. A partir
   daí a LLM **conhece os comandos disponíveis**.
3. **Escuta** — `/listen` sobe a API local (receiver) e registra o agente no host
   (`/api/app/register`). A partir daí o agente **não faz polling**: cada resposta do LLM
   chega via `POST /api/capoeira/response` e é processada por `listener.handle_response`.
4. **Processamento do push** — o texto da resposta é espelhado no monitor; se contiver
   `[TOOL_CALL] nome | chave=valor` (1+ linhas), os comandos são executados:
   - **Sem** `[TOOL_CALL]` ⇒ turno de prosa (a LLM respondeu normalmente); nada a executar.
   - **Com** `[TOOL_CALL]` ⇒ comandos a executar.
5. **Permission gate** — para cada chamada: leitura automática; escrita/execução conforme
   política (`auto`/`ask`) e modo (`readonly`) — ver §9. Em `ask`, a TUI notifica e aguarda
   `y`/`n`/`a`.
6. **Execução** — roda cada passo no diretório do projeto (subprocess/timeout/saída truncada),
   aplica `write_file` via applier atômico (RNF-04), executa comandos-plugin.
7. **Round-trip** — o host é pass-through e não aceita `role=tool`; portanto o resultado é
   serializado **no texto do próprio transcript** como turno `assistant` com
   `[TOOL_RESULT] (call_N) ...` via `POST /api/chat` (`new_chat=false`; fire-and-forget). A
   próxima resposta do modelo chega por um novo push; o ciclo se repete até a resposta ser
   **prosa final** (sem `[TOOL_CALL]`), com proteção de limite de rounds. A resposta final da
   LLM já aparece na aba, visível ao usuário.

### 6.2. Controle

| Ação | Descrição |
|---|---|
| `/listen` | sobe a API local (receiver) e registra o agente no host como destino do push. Se for a primeira interação da sessão e ainda não houve injeção, injeta ambiente automaticamente. |
| `/listen stop` | desregistra o agente do host e derruba a API local. |
| `Ctrl+C` | interrompe o round-trip em andamento (também sai de aprovação pendente). |

### 6.3. Robustez

- O agente **não faz polling**: respostas chegam via push; falha de entrega do host é
  best-effort (logada e ignorada pelo host, sem retry).
- Falha de transiente (`503` offline) na injeção/round-trip ⇒ log + retomada; não desliga o
  listener.
- Proteção contra loop de tool calls: limite de rounds consecutivos (máx. 12).

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
| `/inject-environment` | envia ao chat ativo o prompt com o ambiente do projeto + **dicionário de comandos** (`tools`), via `POST /api/chat` (`new_chat=false`, 1ª interação ⇒ headers `[TOOLS]`). Idempotente; re-emite (a pedido) para atualizar o dicionário. |
| `/listen` · `/listen stop` | sobe/derruba a API local (receiver) e registra/desregistra o agente no host (push). |
| `/status` | provider/modelo online, sessão, política, fila, estado do receiver. |
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
├── config.yaml               # host, modelo, política, new_chat, app_host/app_port/app_path, python
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
  app_host: 127.0.0.1      # API local do agente (receiver do push) — porta distinta do host
  app_port: 8767
  app_path: /api/capoeira/response
policy:
  mode: ask                # auto | ask | readonly
  auto_plugins: []         # nomes de comandos sempre autorizados (modo ask)
python: python3            # intérprete para run_python/subprocess
projects:
  default: ""              # slug padrão (inferido do PATH)
```

### 12.2. Env (overlay)

`CAPOEIRA_AGENT_CONFIG_DIR`, `CAPOEIRA_AGENT_BASE_URL`, `CAPOEIRA_AGENT_MODEL`,
`CAPOEIRA_AGENT_NEW_CHAT`, `CAPOEIRA_AGENT_POLICY`, `CAPOEIRA_AGENT_APP_PORT`.

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
dependência nativa compilada (apenas stdlib + `prompt_toolkit` + `rich` + `PyYAML` +
`fastapi` + `uvicorn`). A API local do agente (`receiver.py`) usa FastAPI/uvicorn — Python
puro, **independente de sistema operacional** — e escuta em `127.0.0.1:8767`, porta distinta
da API do host (`8765`).

---

## 14. Requisitos Não-Funcionais (RNF)

- **RNF-01 (Segurança Local):** comunicação só com loopback (`127.0.0.1`); comandos executam
  no diretório do projeto com timeout e sem env de segredos; nada é gravado sem validação/aprovação.
- **RNF-04 (Atomicidade):** `write_file` e lotes multi-arquivo aplicados via
  tmp + `os.replace` all-or-nothing (herdado do CapoeiraCode); sem escrita parcial.
- **RNF-05 (Não-interferência):** o agente nunca dispara geração por conta própria; só reage
  a respostas **externas** (push) — a interface web continua sendo a experiência primária.
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
│   ├── llm_client.py        # /api/chat (urllib; text) + /api/app/register|unregister
│   ├── prompts.py           # contrato TOOLS_CONTRACT; builder do /inject-environment
│   ├── config.py            # resolve config dir; config.yaml + env overlay; premises
│   ├── session.py           # configs/<slug>/ + session.jsonl
│   ├── receiver.py          # API local (FastAPI/uvicorn) na escuta do push do host
│   ├── listener.py          # handle_response (push) + round-trip de tools
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
├── tests/                   # pytest (client fake do host; receiver; policies; tools)
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
class ChatReply: content: str  # "accepted: {request_id}" (fire-and-forget)
class LLMClient(base_url, model, timeout):
    chat(messages, stream=False, new_chat=False) -> ChatReply
    register_app(port, host, name) -> str
    unregister_app() -> str
class LLMRequestError(Exception)
serialize_tools(tools: list[dict]) -> str

# listener.py
class Listener(client, session, permissions, tui):
    start() / stop()
    @property listening: bool
    handle_response(payload: dict) -> None   # parse [TOOL_CALL] → gate → exec → round-trip

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
| **I1 — Esqueleto e host** | entry + TUI mínima + `config.py` + `llm_client` (`/api/chat` + registro de app) + teste com host fake. |
| **I2 — Framework de comandos** | `core/*` (Crivonansky) + `commands/` core + `/init` + `/generate-plugin`. |
| **I3 — Listener + permissions** | receiver (push) + `handle_response`, permission gate (auto/ask/readonly, y/n/a), executor core + applier atômico. |
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
3. **`/listen` público** (comando da TUI inicia a escuta) vs escuta automática ao abrir.
4. **Hierarquia de plugins** — projeto → config → package (ordem de precedência).
5. **Política default** — `ask` para escrita/execução (sugerido), leitura automática.
6. **Versionamento mínimo** do CapoeiraHost: `>= 2.1.0` (por push `/api/capoeira/response`).

---

## 19. Registro de Alterações

| Versão | Data | Descrição |
| --- | --- | --- |
| `0.1.0` | 15/09/2026 | Draft inicial da spec baseado em CapoeiraCode v6.0.0, CapoeiraHost **v2.1.0** (novos `/api/chat/read` e `/api/chat/watch` para o modo escuta) e Cli-Crivonansky (framework de plugins). |
| `0.1.1` | 21/09/2026 | Adequação ao CapoeiraHost **pass-through verbatim** (commit `d1d00ab`): sem `tools`/`role=tool`/`tool_call_id` na API; contrato de tools embutido no texto da mensagem de sistema (`prompts.build_tools_block`); round-trip de resultados via turno `assistant` com `[TOOL_RESULT] (id) ...` (`llm_client.chat`). |
| `0.1.2` | 28/09/2026 | Adequação ao CapoeiraHost **push** (commit `fb55cbb`): `/api/chat` responde `accepted: {request_id}` (fire-and-forget) e entrega a resposta via `POST /api/capoeira/response` na app registrada em `/api/app/register`. O agente sobe a API local (`receiver.py`, FastAPI/uvicorn) e processa respostas via `listener.handle_response` — sem polling (`/api/chat/read`/`watch` removidos). Removido o `Dockerfile`; a API do agente escuta em `127.0.0.1:8767`, porta distinta da API do host. |