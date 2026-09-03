# Spec — Pauta (v1)

> Documento de especificação para implementação assistida. Escrito em português;
> **todo identificador de código (classe, função, variável, tabela, coluna, rota) é
> em inglês.**
>
> Revisão 2 — incorpora as decisões tomadas na análise de 02/09/2026, e as três
> confirmações de D15–D17 recebidas na mesma data. As mudanças estruturais em relação
> à revisão 1 estão listadas no §15; o que segue em aberto está no §16.

---

## 1. Contexto e objetivo

Sistema local de uso individual que substitui a aba `Planejamento` de uma planilha
(um Gantt desenhado à mão) e o controle mental de fila de frentes de trabalho de um
time de engenharia de dados e produto.

A pergunta que o sistema responde: **quais frentes de trabalho o time toca, em quais
sprints, com quais squads e com quais pessoas — e onde isso está inconsistente.**

Não é um gerenciador de tarefas. Uma "iniciativa" aqui é uma frente de trabalho que
ocupa capacidade por uma ou mais sprints, não uma demanda.

### O que a v1 substitui
- A aba `Planejamento` da planilha (a grade iniciativa × sprint).
- A conferência manual de sobreposição de squad e de pessoa.

### O que a v1 não toca
`Sprints.md`, `Sprint_XX.md`, dailies e biblioteca de prompts continuam como arquivos
soltos. A v1 apenas garante IDs estáveis para que eles possam ser vinculados depois
sem migração.

---

## 2. Escopo

### Dentro (v1)
1. CRUD de projetos, iniciativas, membros, squads e sprints.
2. Composição de squad por sprint (quem está em qual squad em qual sprint).
3. Alocação de iniciativa → (squad ou membro) → intervalo de sprints.
4. Tela de backlog (iniciativas com status `BACKLOG`).
5. Tela de planejados, com alternância entre grade (Gantt) e lista.
6. Quatro alertas calculados, com silenciamento.
7. Snapshot em texto (JSON + Markdown) para a pasta sincronizada, e reimportação.

### Fora (v1, mas o modelo não fecha a porta)
- Dailies, reportes por pessoa, itens de acompanhamento (bloqueios, decisões, riscos).
- Planejamento semanal com Big Bets e Quick Wins.
- Demandas/tarefas dentro da iniciativa e board kanban.
- Capacidade em horas, férias, ausências.
- Calendário de feriados e cálculo de dias úteis.
- Dependência entre iniciativas.
- Integrações com LLM (Claude, Gemini, read.ai) para transformar relatório de reunião
  em tarefas.
- **Importação de planilha ou CSV, e comando `seed`.** Todo dado entra pela interface.

**Regra de ouro para o agente:** não implemente nada da lista "fora". Se um item de
escopo parecer exigir isso, pare e pergunte.

---

## 3. Decisões já tomadas

Estas decisões estão fechadas. Não reabra.

| # | Decisão | Razão |
|---|---|---|
| D1 | Backend e frontend em pastas separadas, dentro de um monorepo simples (`backend/`, `frontend/`) | Deploy local, mas evolução independente |
| D2 | Backend: Python + FastAPI, arquitetura hexagonal (ports & adapters) | Domínio testável sem banco nem HTTP; é a arquitetura que o time já pratica |
| D3 | Frontend: Astro com ilhas React + Tailwind | Astro dá o shell estático e o roteamento; ilhas React deixam o output de ferramentas de prototipação (Lovable/v0) portável quase direto |
| D4 | Persistência: SQLite local, arquivo único, **fora** da pasta sincronizada | `.sqlite` em pasta sincronizada corrompe com conflito binário |
| D5 | Banco é a fonte da verdade; Markdown e JSON são **saída** | A v1 só tem dado estruturado, sem conteúdo narrativo |
| D6 | Runtimes e tasks via `mise`; dependências Python via `uv`; Node via `pnpm` | Um único `mise install && mise run setup` prepara a máquina inteira |
| D7 | Sem autenticação, sem multiusuário, sem rede externa | Uso individual, offline |
| D8 | Identificadores de código em inglês, documentação e UI em português | Convenção existente do time |
| D9 | O venv é de propriedade do `uv`, em `backend/.venv`; o `mise` apenas o ativa | Ver §4.3 — as duas ferramentas criando venv geram dois ambientes |
| D10 | Projeto é agrupador; **iniciativa** é a unidade de trabalho alocável | Ver §6.1 |
| D11 | Composição de squad é **por sprint**, não uma lista estática | Ver §6.5 |
| D12 | Alocação tem um responsável só por sprint: uma squad **ou** um membro | Ver §6.7 |
| D13 | Sprint nunca é excluída | Ver §7.2 |
| D14 | Nenhum dado é importado nem semeado; tudo é cadastrado na UI | Ver §9 |
| D15 | Alocação é na **iniciativa**, nunca no projeto; o enum `Product` não existe | Confirmado em 02/09/2026. Ver §6.1, §6.2 |
| D16 | O terceiro alerta é `MEMBER_IDLE` (pessoa sem frente), não `SQUAD_IDLE` | Confirmado em 02/09/2026. Squad é agrupamento temporário — squad sem alocação não é problema; pessoa sem frente é. Ver §7.3 |
| D17 | Unicidade da alocação é `(initiative_id, sprint_id)` | Confirmado em 02/09/2026. Duas squads na mesma **iniciativa** ao mesmo tempo deveriam ser uma squad só; duas squads em iniciativas diferentes do mesmo projeto são normais. Ver RN8 |

### Decisões que esta revisão fecha

**Projeto ≠ iniciativa.** Um projeto grande se divide em frentes com prioridade e
cronograma próprios. O Aurora tem o Catálogo V1, o Serviço de Envio (serviço
unificado de disparo de mensagens) e o backlog da V2. Quem ocupa
sprint é a **iniciativa**; o **projeto** só agrupa e dá a cor. O enum `Product` da
revisão 1 foi removido — o projeto passou a ser esse agrupamento, e é cadastrado, não
fixo no código.

**Reserva de capacidade é configuração, não caso especial.** `Project` recebe a flag
`is_capacity_reserve`, ligável e desligável no cadastro. O Plantão é sustentação sob
demanda: quem está nele **não fica travado**. Quando a flag é `true`, as iniciativas
daquele projeto:
- aparecem na grade com faixa hachurada, não bloco sólido;
- **não** contam para `SQUAD_OVERLOADED` nem para `MEMBER_CONFLICT`;
- não aparecem no backlog nem em contagem de capacidade.

**Squad é agrupamento com prazo.** Squad existe para não alocar pessoa por pessoa.
Quem está nela muda por sprint (`SquadMembership`). A Carla no Boreal até a 19 e no
Aurora a partir da 20 não é conflito. Squad tem representante opcional. Trabalho pequeno
pode ser alocado direto a um membro, sem squad.

**Alertas podem ser silenciados.** Sem isso, o conflito conhecido e intencional da
Ana grita em toda sprint e o painel perde valor em uma semana. Silenciar exige um
motivo em texto e é reversível. O `fingerprint` é ancorado no **sujeito** do alerta
(a squad ou o membro) e na sprint, nunca nas iniciativas envolvidas — assim entrar um
terceiro projeto não desfaz o silenciamento. Ver §7.3.

---

## 4. Stack e tooling

### 4.1 Versões (verificadas em 02/09/2026)

Pinar exatamente estas faixas. Não usar `latest` em lugar nenhum.

```
Python          3.14            (estável desde out/2025)
FastAPI         ~=0.141.1
Uvicorn         ~=0.52.4        [standard]
SQLAlchemy      >=2.0.52,<2.1   Core/ORM, apenas na camada de adapter
Alembic         ~=1.19.1        migrations
Pydantic        ~=2.13.5        apenas nos schemas de borda HTTP, não no domínio
pydantic-settings ~=2.15.0      config/settings.py
Typer           ~=0.27.2        CLI
pytest          ~=9.1.1  + pytest-asyncio ~=1.4.0 + httpx ~=0.28.1
ruff            ~=0.16.5        lint + format
mypy            ~=2.3.1         --strict em domain/ e application/

Node            24 (Active LTS)
pnpm            11.25.x
uv              0.12.x
Astro           ~7.2.10
@astrojs/react  ~6.0.5
React           19.2.x + react-dom 19.2.x + @types/react 19.2.x
Tailwind        4.3.x via @tailwindcss/vite 4.3.x
TypeScript      ~6.0.3          strict
Vitest          ~4.1.11
@tanstack/react-query   ~5.102.8
openapi-typescript      ~7.13.0   (devDependency)
@fontsource-variable/inter ~5.3.0  (fonte self-hosted; nenhuma chamada externa)
```

Notas que custaram tempo para descobrir e que não devem ser reaprendidas:

- **Tailwind v4 no Astro é `@tailwindcss/vite`**, nunca a integração
  `@astrojs/tailwind` (que é v3-only e falha ou produz saída errada em silêncio).
  Desde o Astro 5.2, `astro add tailwind` já faz esse wiring — não escreva à mão.
- **Tailwind v4 não tem `tailwind.config.js`.** A configuração vive no CSS. Os tokens
  do §10.2 são declarados dentro de `@theme` em `tokens.css`, e é isso que faz
  `bg-surface`, `text-subtle`, `rounded-sm` existirem como utilitários. Declarar como
  `:root { --c-bg: … }` puro **não** gera utilitário nenhum.
- **SQLAlchemy 2.1 ainda é beta** (2.1.0b2, abr/2026) e traz quebras (refactor de
  `ColumnCollection`, remoção do mapper *non primary*). O teto `<2.1` é intencional.
  Cuidado: `docs.sqlalchemy.org` serve a doc da 2.1 por padrão — não copie API que
  não existe na 2.0.
- **mypy está no major 2**, cujos defaults de `--strict` diferem da era 1.x. Pinar.
- **TypeScript**: o npm serve 7.0.2 como `latest`, mas o Astro 7.2.10 é desenvolvido
  contra `typescript ^6.0.3`. Pinar `~6.0.3`.
- **Node 22 está em Maintenance** (EOL 30/04/2027). O Astro 7 exige `>=22.12.0`, mas
  o pin correto hoje é 24.

### 4.2 Nenhuma dependência além destas

§14 vale: perguntar antes de adicionar qualquer coisa que não esteja em §4.1. As
quatro que a revisão 1 citava no corpo do texto sem listar aqui foram resolvidas e
estão acima: `typer`, `pydantic-settings`, `openapi-typescript` e
`@tanstack/react-query`. A fonte Inter entra como pacote self-hosted
(`@fontsource-variable/inter`), não via Google Fonts — RNF6 proíbe chamada externa.

Estado de servidor no front: **TanStack Query**, em todas as ilhas. Não misturar com
`useState` + revalidação manual.

### 4.3 `mise.toml` (raiz)

```toml
[tools]
python = "3.14"
node   = "24"
uv     = "0.12.9"
pnpm   = "11.25.0"

[env]
# O uv é o dono do venv (D9). O mise apenas ativa se já existir — quem cria é
# `mise run setup`. Na primeira entrada no diretório o mise avisa que não existe;
# é esperado.
_.python.venv = { path = "{{config_root}}/backend/.venv", create = false }

# Faz o uv usar o Python que o mise instalou, em vez de baixar outro.
UV_PYTHON_PREFERENCE = "only-system"

DATABASE_URL = "sqlite+pysqlite:///{{config_root}}/data/pauta.sqlite"
SNAPSHOT_DIR = "{{config_root}}/snapshots"
PUBLIC_API_URL = "http://127.0.0.1:8000"

[tasks."setup:dirs"]
run = "mkdir -p {{config_root}}/data {{config_root}}/snapshots"

[tasks."setup:py"]
dir = "{{config_root}}/backend"
run = "uv sync"

[tasks."setup:web"]
dir = "{{config_root}}/frontend"
run = "pnpm install"

[tasks."setup:db"]
description = "Aplica as migrations"
dir = "{{config_root}}/backend"
depends = ["setup:dirs", "setup:py"]
run = "uv run alembic upgrade head"

[tasks.setup]
description = "Prepara a máquina do zero"
depends = ["setup:db", "setup:web"]

[tasks."dev:api"]
description = "API em :8000"
dir = "{{config_root}}/backend"
run = "uv run uvicorn app.adapters.inbound.http.main:app --reload --port 8000"

[tasks."dev:web"]
description = "Front em :4321"
dir = "{{config_root}}/frontend"
run = "pnpm dev"

[tasks.dev]
description = "Sobe API e front juntos"
depends = ["dev:api", "dev:web"]

[tasks."test:py"]
dir = "{{config_root}}/backend"
run = "uv run pytest"

[tasks."test:web"]
dir = "{{config_root}}/frontend"
run = "pnpm vitest run"

[tasks.test]
description = "pytest + vitest"
depends = ["test:py", "test:web"]

[tasks.lint]
description = "ruff + mypy --strict no domínio e aplicação"
dir = "{{config_root}}/backend"
run = [
  "uv run ruff check .",
  "uv run ruff format --check .",
  "uv run mypy --strict app/domain app/application",
]

[tasks.fmt]
dir = "{{config_root}}/backend"
run = "uv run ruff format ."

[tasks.types]
description = "Regenera frontend/src/lib/types.ts do OpenAPI"
dir = "{{config_root}}/frontend"
run = "pnpm openapi-typescript http://127.0.0.1:8000/api/v1/openapi.json -o src/lib/types.ts"

[tasks.snapshot]
description = "Exporta snapshot para a pasta sincronizada"
dir = "{{config_root}}/backend"
run = "uv run python -m app.adapters.inbound.cli snapshot export"
```

Detalhes que a revisão 1 errava:

- **Caminhos de lint.** `uv run --project backend mypy backend/app/domain` procurava
  `backend/backend/app/domain`. Resolvido com `dir` na task e caminhos relativos.
  Também faltava o `--strict` que §4.1 e §11 exigem, e `ruff check .` na raiz varria
  o `frontend/`.
- **`data/` fica dentro do repositório** (irmão de `snapshots/`), não em `../data`.
  Os dois são ignorados pelo Git.
- **As três barras do `DATABASE_URL` estão certas.** `{{config_root}}` já começa com
  `/`, então `sqlite+pysqlite:///` + `/Users/...` resolve para as quatro barras que o
  SQLAlchemy exige em caminho absoluto. Não "conserte" isso.
- **Toda task roda com `dir`** e comandos relativos, em vez de `--project backend` /
  `--dir frontend`. Um estilo só, e o `dir` é o que faz `alembic`, `ruff` e `pytest`
  acharem seus arquivos de configuração.
- **`setup` foi quebrada em sub-tasks** porque cada passo precisa de um `dir`
  diferente, e o `alembic` tem de rodar depois do `uv sync` — `depends` garante a
  ordem. Rodar `alembic -c backend/alembic.ini` da raiz quebraria o
  `script_location` relativo do `alembic.ini`.
- **Se o `mise` recusar `create = false`** (ele foi pensado para criar o venv, não só
  para anexar), remova o bloco `_.python.venv` inteiro. Nada depende dele: toda
  invocação de Python no projeto passa por `uv run`, que resolve o ambiente sozinho. A
  ativação existe só pela conveniência de digitar `pytest` direto no shell.
- **`[tasks.dev]`** roda as duas dependências em paralelo e **não** as mata juntas —
  isso é aceito. Se um dos dois cair, o mise reporta a falha no log ao final; quem
  quer o outro de volta reinicia. Não vale complexidade para acoplar os ciclos de
  vida.

### 4.4 `.gitignore`

O arquivo já existe no repositório. A revisão 2 acrescentou:

```
snapshots/
```

Confirmar também que `backend/uv.lock` e `frontend/pnpm-lock.yaml` **não** estão
ignorados: os dois são versionados, é o que trava as versões do §4.1 na prática.

---

## 5. Estrutura de diretórios

```
pauta/
├── mise.toml
├── .gitignore                  # data/, snapshots/, .venv/, node_modules/, *.sqlite
├── README.md                   # como rodar, em português
├── CLAUDE.md
├── docs/
│   ├── spec.md                 # este arquivo
│   └── requisitos-v1.md
├── data/                       # ignorado — banco SQLite
├── snapshots/                  # ignorado — pasta sincronizada (Drive)
│
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock                 # versionado
│   ├── alembic.ini
│   ├── migrations/
│   ├── app/
│   │   ├── domain/                     # ZERO imports de fora do domínio
│   │   │   ├── entities/               # project.py, initiative.py, member.py,
│   │   │   │                           # squad.py, squad_membership.py, sprint.py,
│   │   │   │                           # allocation.py, muted_alert.py
│   │   │   ├── value_objects/          # priority.py, initiative_status.py,
│   │   │   │                           # sprint_range.py, assignee.py, color.py
│   │   │   ├── services/               # alert_service.py, planning_rules.py,
│   │   │   │                           # bar_consolidation.py, fingerprint.py
│   │   │   ├── errors.py               # DomainError e subclasses
│   │   │   └── ports/
│   │   │       ├── repositories.py     # Protocol: ProjectRepository, ...
│   │   │       ├── snapshot.py         # Protocol: SnapshotWriter, SnapshotReader
│   │   │       ├── clock.py            # Protocol: Clock — para is_current testável
│   │   │       └── task_suggester.py   # v2 — porta declarada, sem implementação
│   │   ├── application/
│   │   │   ├── dto/                    # dataclasses de entrada/saída dos use cases
│   │   │   └── use_cases/
│   │   │       ├── projects/            create, update, list, get, archive
│   │   │       ├── initiatives/         create, update, list, get, change_status
│   │   │       ├── members/             create, update, list, deactivate
│   │   │       ├── squads/              create, update, list, set_memberships
│   │   │       ├── sprints/             create, create_next, list
│   │   │       ├── planning/            allocate_range, deallocate, get_grid,
│   │   │       │                        get_backlog
│   │   │       ├── alerts/              list_alerts, mute_alert, unmute_alert
│   │   │       └── snapshots/           export, import
│   │   ├── adapters/
│   │   │   ├── inbound/
│   │   │   │   ├── http/
│   │   │   │   │   ├── main.py          # app factory, CORS, error handlers
│   │   │   │   │   ├── deps.py          # wiring dos use cases
│   │   │   │   │   ├── schemas/         # Pydantic, um módulo por recurso
│   │   │   │   │   └── routers/         # projects.py, initiatives.py, ...
│   │   │   │   └── cli/                 # typer: snapshot export/import
│   │   │   └── outbound/
│   │   │       ├── persistence/
│   │   │       │   ├── models.py        # SQLAlchemy — mapeamento explícito
│   │   │       │   ├── mappers.py       # model <-> entity
│   │   │       │   ├── session.py
│   │   │       │   └── repositories/    # implementações dos Protocols
│   │   │       ├── snapshot/            # json_writer.py, markdown_writer.py,
│   │   │       │                        # reader.py, debounce.py
│   │   │       └── system_clock.py
│   │   └── config/
│   │       └── settings.py              # pydantic-settings
│   └── tests/
│       ├── domain/                      # puro, sem fixtures de banco
│       ├── application/                 # use cases com repositórios fake in-memory
│       └── http/                        # TestClient
│
└── frontend/
    ├── package.json
    ├── pnpm-lock.yaml                   # versionado
    ├── astro.config.mjs
    ├── tsconfig.json
    └── src/
        ├── layouts/AppShell.astro       # sidebar + topbar
        ├── pages/
        │   ├── index.astro              # redireciona para /planning
        │   ├── planning.astro           # grade + lista
        │   ├── backlog.astro
        │   ├── projects.astro           # projetos e iniciativas
        │   ├── team.astro               # membros, squads e composição por sprint
        │   └── sprints.astro
        ├── components/
        │   ├── ui/                      # Button, Lozenge, Avatar, Modal, Select,
        │   │                            # Table, Toast
        │   ├── layout/                  # Sidebar, TopBar, PageHeader
        │   └── islands/                 # React: PlanningGrid, AllocationDialog,
        │                                # BacklogTable, ProjectDrawer,
        │                                # InitiativeDrawer, SquadEditor,
        │                                # SquadMembershipMatrix, AlertPanel
        ├── lib/
        │   ├── api.ts                   # cliente tipado, um método por endpoint
        │   ├── types.ts                 # gerado do OpenAPI (mise run types)
        │   ├── query.ts                 # QueryClient do TanStack
        │   └── format.ts
        └── styles/
            ├── tokens.css               # @theme do Tailwind (§10.2)
            └── global.css
```

### Regras de dependência (hexagonal, sem negociação)

- `domain/` não importa nada de `application/`, `adapters/`, SQLAlchemy, Pydantic ou
  FastAPI. Só stdlib.
- `application/` importa `domain/`. Nunca `adapters/`.
- `adapters/` importa `application/` e `domain/`.
- Entidades de domínio são `@dataclass` com invariantes validadas no `__post_init__`
  ou em construtores nomeados (`Initiative.create(...)`).
- Repositórios são `typing.Protocol` declarados no domínio e implementados no adapter.
- Nenhum use case recebe `Session`, `Request` ou modelo SQLAlchemy. Só portas e DTOs.
- Nada no domínio chama `date.today()`. A data corrente entra pela porta `Clock`, ou
  o `is_current` fica intestável.
- Adicione um teste que falhe se a regra for violada (varredura de imports em
  `tests/domain/test_dependency_rule.py`).

---

## 6. Modelo de domínio

### Glossário PT → código

| Termo de negócio | Código |
|---|---|
| Projeto | `Project` |
| Iniciativa / frente | `Initiative` |
| Camada | `Initiative.layer` |
| Liderado / membro | `Member` |
| Squad | `Squad` |
| Composição da squad na sprint | `SquadMembership` |
| Representante | `Squad.representative_member_id` |
| Sprint | `Sprint` |
| Alocação | `Allocation` |
| Grade / Gantt | `PlanningGrid` |
| Alerta | `Alert` |

> A entidade de pessoa é `Member`, não `User` — não há login no sistema, e `User`
> sugeriria autenticação.

### 6.1 `Project`

Agrupador. **Não** tem status, prioridade nem alocação.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | estável para sempre; v2 vai referenciar |
| `name` | str | obrigatório, único |
| `description` | str | default `""` |
| `color` | str? | hex `#RRGGBB`; nulo usa `DEFAULT_PROJECT_COLOR` (§10.2) |
| `is_capacity_reserve` | bool | default `false`; `true` para sustentação sob demanda |
| `is_active` | bool | default `true` |

### 6.2 `Initiative`

A unidade de trabalho. É a linha do Gantt e o que recebe alocação.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | estável para sempre |
| `project_id` | UUID | obrigatório |
| `name` | str | obrigatório, único **dentro do projeto** |
| `layer` | str? | texto livre. Ex.: "Serviço de Envio", "Dados", "Backend" |
| `description` | str | default `""` |
| `priority` | `Priority` | `HIGH`, `MEDIUM`, `LOW` |
| `estimated_sprints` | int? | > 0 quando presente |
| `status` | `InitiativeStatus` | ver §6.3 |
| `entered_at` | date | default hoje (via `Clock`) |

`is_capacity_reserve` **não** existe aqui: é herdado do projeto. Onde a regra precisar
do valor, o use case resolve o projeto e passa o booleano ao domínio.

**RN-I1.** Criar um `Project` cria automaticamente sua primeira `Initiative`, com o
mesmo `name`, `priority = MEDIUM` e `status = BACKLOG`. O nome é editável em seguida.
Um projeto com uma iniciativa só se comporta exatamente como o "projeto" da revisão 1;
quem tem uma frente única nunca precisa pensar em iniciativa.

**RN-I2.** Um `Project` não pode ficar sem iniciativa. Excluir a última é 409.

### 6.3 `InitiativeStatus` e transições

Valores: `BACKLOG`, `PLANNED`, `IN_PROGRESS`, `DEPRIORITIZED`, `DONE`, `CANCELLED`.

`BACKLOG` significa: trabalho que em algum momento será executado, não priorizado,
não iniciado, **e que não entra em nenhuma conta de capacidade**.

| De | Para | Como |
|---|---|---|
| `BACKLOG` | `PLANNED` | automático, na primeira alocação |
| `BACKLOG` | `CANCELLED` | manual |
| `PLANNED` | `BACKLOG` | automático, ao perder todas as alocações |
| `PLANNED` | `IN_PROGRESS` | manual |
| `PLANNED` | `CANCELLED` | manual |
| `IN_PROGRESS` | `DEPRIORITIZED`, `DONE`, `CANCELLED` | manual |
| `DEPRIORITIZED` | `PLANNED`, `IN_PROGRESS`, `CANCELLED` | manual |
| `DONE`, `CANCELLED` | — | terminais |

**Nada volta para `BACKLOG` depois de ter começado.** Uma iniciativa `IN_PROGRESS`
que perde todas as alocações **continua** `IN_PROGRESS`; se é para parar, o caminho é
`DEPRIORITIZED`, à mão. Qualquer outra transição é `InvalidStatusTransition` (422).

Isso é dois métodos distintos e explícitos no código, e não devem se contaminar:

```python
def recalculate_status(self, has_allocations: bool) -> None:
    """Só BACKLOG <-> PLANNED. Nenhum outro status é tocado."""

def change_status(self, new_status: InitiativeStatus) -> None:
    """Transições manuais, validadas contra a tabela acima."""
```

### 6.4 `Member`

`id` (UUID), `name`, `short_name`, `role` (str livre), `is_active` (bool, default
`true`).

Inativo desaparece dos seletores e continua no histórico. **Nunca deletar
fisicamente** — apagar reescreveria alocações passadas. `DELETE /members/{id}` faz
`is_active = false`.

### 6.5 `Squad` e `SquadMembership`

`Squad`: `id` (UUID), `name` (único), `representative_member_id` (UUID?, o membro que
faz a ponte), `is_active` (bool).

A squad **não carrega lista de membros**. Quem está nela é `SquadMembership`:

`SquadMembership`: `id` (UUID), `squad_id`, `member_id`, `sprint_id`.

Uma linha por sprint, no mesmo idioma de `Allocation`. Unicidade:
`(squad_id, member_id, sprint_id)`.

Isso é o que resolve o caso real:

> Carla ∈ squad Boreal nas sprints 18 e 19. Carla ∈ squad Aurora da sprint 20 em diante.

Nenhuma sprint tem a Carla nas duas squads, então não há conflito — e a squad do Aurora
"ganha um membro novo a partir da 20" sem que isso vaze para as sprints anteriores.

**RN-S1.** `representative_member_id`, quando presente, precisa apenas referenciar um
`Member` existente e ativo. **Não** é validado contra a composição da squad: no
momento em que a squad é criada ela ainda não tem membership nenhuma, e o
representante é uma ponte, não necessariamente alguém que executa. Se o representante
não estiver na squad na sprint atual, a UI mostra um aviso discreto — não um erro.

**RN-S2.** Squad sem nenhum `SquadMembership` em uma sprint na qual tem alocação
dispara `EMPTY_SQUAD` (informativo, nunca bloqueio) — planejar antes de contratar é
legítimo.

### 6.6 `Sprint`

`id` (UUID), `number` (int, único), `start_date`, `end_date`.

Invariantes:
- `end_date > start_date`;
- sem sobreposição com outra sprint;
- `number` sequencial sem buraco;
- `start_date` da sprint `N+1` > `end_date` da sprint `N`.

Padrão: começa numa segunda e termina na sexta da semana seguinte — `end_date =
start_date + 11 dias`, duas semanas de calendário. Confere com o dado real: a
Sprint 18 vai de segunda 31/08/2026 a sexta 11/09/2026, e a 19 começa na segunda
14/09.

Os dias úteis dentro do intervalo **variam** (feriado). O sistema não modela feriado e
não calcula dias úteis; `start_date` e `end_date` são a referência e ponto.

**Sprint nunca é excluída** (D13). Não existe `DELETE /sprints/{id}`.

### 6.7 `Allocation`

`id` (UUID), `initiative_id`, `sprint_id`, `squad_id` (UUID?), `member_id` (UUID?).

Uma linha por sprint ocupada. O Catálogo do Aurora da Sprint 18 à 22 = cinco
linhas. Isso torna a grade trivial de renderizar e permite pausar uma frente no meio
sem gambiarra.

Invariantes:
- **exatamente um** de `squad_id` / `member_id` preenchido (`AssigneeRequired` se
  nenhum, `AmbiguousAssignee` se ambos);
- unicidade `(initiative_id, sprint_id)` — uma iniciativa tem **um** responsável por
  sprint.

Frente grande vai para uma squad. Trabalho pequeno vai direto para uma pessoa, sem
criar squad de um membro só.

> Duas squads na mesma iniciativa na mesma sprint **não** é permitido: se duas squads
> estão na mesma frente ao mesmo tempo, elas deveriam ser uma squad só. Isso também
> elimina o empilhamento de barras na grade — cada linha nunca tem duas barras
> sobrepostas.

### 6.8 Alocação efetiva de um membro

Conceito derivado, central para `MEMBER_CONFLICT` e `MEMBER_IDLE`. Não é tabela.

O conjunto de iniciativas de um membro `m` na sprint `s` é a união de:

1. alocações diretas — `Allocation(member_id=m, sprint_id=s)`;
2. alocações das squads a que `m` pertence naquela sprint —
   `Allocation(squad_id=q, sprint_id=s)` para todo `q` com
   `SquadMembership(q, m, s)`.

Iniciativas de projetos com `is_capacity_reserve = true` são removidas desse conjunto
antes de qualquer verificação de conflito.

**A regra de ouro:** um membro tem no máximo **uma** iniciativa efetiva não-reserva
por sprint. Ultrapassar é `MEMBER_CONFLICT` — aviso, não bloqueio.

### 6.9 `MutedAlert`

`id` (UUID), `alert_type`, `fingerprint` (str determinística), `reason` (obrigatória,
não vazia), `created_at` (datetime UTC).

Unicidade: `fingerprint`.

### 6.10 `ExternalRef` (pavimento v2, tabela vazia na v1)

`id`, `entity_type` (`project`, `initiative`, `sprint`), `entity_id`, `system`
(`read_ai`, `notion`, …), `external_id`.

Existe para que um relatório de reunião importado no futuro possa apontar para
iniciativa ou sprint sem migração. **Sem endpoint, sem UI, sem uso na v1.**

---

## 7. Regras de negócio

### 7.1 Alocação

- **RN1.** Alocar exige `initiative_id`, um responsável (`squad_id` **ou**
  `member_id`) e o intervalo `[from_sprint_number, to_sprint_number]`. O sistema cria
  uma `Allocation` por sprint do intervalo, ignorando as que já existem (idempotente).
- **RN2.** Ao receber a primeira alocação, iniciativa em `BACKLOG` passa a `PLANNED`.
  Ao perder todas, `PLANNED` volta a `BACKLOG`. Os outros quatro status não são
  alterados por alocação (§6.3).
- **RN3.** Uma iniciativa pode ter responsáveis diferentes em sprints diferentes.
- **RN4.** Alocar a mesma squad a mais de uma iniciativa na mesma sprint é permitido,
  com aviso (`SQUAD_OVERLOADED`). **Nunca bloqueio.**
- **RN5.** Alocar em sprint inexistente **não** derruba a operação: o sistema cria as
  alocações das sprints que existem e devolve, em `missing_sprint_numbers`, a lista do
  que falta cadastrar. A UI mostra o aviso com atalho para "criar próxima sprint".
- **RN6.** Desalocar aceita o intervalo inteiro (`from`/`to`) ou uma célula única
  (`DELETE /allocations/{id}`).
- **RN7.** Iniciativa `DONE` ou `CANCELLED` não aceita nova alocação (422). As
  existentes permanecem, como histórico. `DEPRIORITIZED` **aceita** alocação e
  **continua** `DEPRIORITIZED` — `recalculate_status` só mexe em `BACKLOG` ⇄
  `PLANNED` (§6.3). Retomar é uma decisão manual, via
  `POST /initiatives/{id}/status`, não um efeito colateral de arrastar uma barra.
- **RN8.** Unicidade `(initiative_id, sprint_id)`: tentar um segundo responsável para
  a mesma célula é 409, com a mensagem apontando quem já está lá.
- **RN9.** Um membro em duas squads na mesma sprint é **aceito no dado** e sinalizado
  com `MEMBER_CONFLICT`. Não é bloqueio.

### 7.2 Sprints

- **RN10.** `create_next_sprint` propõe a sprint seguinte: `number` incrementado,
  `start_date` = próxima segunda-feira após o `end_date` da última,
  `end_date` = `start_date + 11 dias`. As duas datas vêm no payload de resposta e são
  editáveis antes de confirmar; `POST /sprints` aceita datas arbitrárias que respeitem
  as invariantes do §6.6.
- **RN11.** Sprint não é excluída (D13). Não há endpoint de exclusão. A invariante de
  numeração sem buraco, portanto, nunca pode ser violada por remoção.
- **RN12.** `is_current`: a sprint atual é a de **maior `start_date` que já passou**
  (`start_date <= hoje`), independentemente do `end_date`. Uma sprint só termina de
  verdade quando a próxima começa, então uma folga de calendário entre duas sprints
  não deixa o sistema sem sprint atual. Se nenhuma sprint começou ainda,
  `is_current` é `false` em todas.
- **RN13.** A janela padrão da grade é o **trimestre corrente**: as sprints cujo
  intervalo intersecta o trimestre que contém a data de hoje. `sprint_from` e
  `sprint_to` explícitos sobrepõem o default.

### 7.3 Alertas

Calculados sob demanda, nunca persistidos (só o silenciamento é). Todos são aviso
visual, **jamais bloqueio**.

| Tipo | Severidade | Condição |
|---|---|---|
| `SQUAD_OVERLOADED` | `WARNING` | Squad com alocação em mais de uma iniciativa na mesma sprint, desconsiderando iniciativas de projetos com `is_capacity_reserve` |
| `MEMBER_CONFLICT` | `WARNING` | Membro ativo com mais de uma iniciativa **efetiva** (§6.8) não-reserva na mesma sprint — tipicamente por estar em duas squads naquela sprint |
| `MEMBER_IDLE` | `INFO` | Membro ativo sem nenhuma iniciativa efetiva numa sprint atual ou futura |
| `EMPTY_SQUAD` | `INFO` | Squad ativa com alocação numa sprint, mas sem nenhum `SquadMembership` naquela sprint |

`Severity` é enum em inglês (`WARNING`, `INFO`) e o valor viaja assim até a UI, que
faz o mapa para o rótulo em português no `Lozenge`.

Cada alerta carrega:

```
type              str        (o enum acima)
severity          str        WARNING | INFO
sprint_number     int
entity_refs       list[{ type, id, name }]   objetos tipados, não UUID cru
message           str        português, frase única, específica
fingerprint       str
is_muted          bool
mute_id           UUID?      presente quando is_muted; é o que o botão "reativar" usa
mute_reason       str?       presente quando is_muted
```

`message` é específica, não genérica. Exemplo: *"Ana está nas squads Alfa e
Beta, alocadas na Sprint 19 em Boreal / Catálogo e Aurora / Serviço de Envio."*

#### `fingerprint` — ancorado no sujeito

```
fingerprint = sha256(f"{type}|{subject_id}|{sprint_number}").hexdigest()[:32]
```

Onde `subject_id` é **só** o sujeito do alerta:

| Tipo | `subject_id` |
|---|---|
| `SQUAD_OVERLOADED` | `squad_id` |
| `MEMBER_CONFLICT` | `member_id` |
| `MEMBER_IDLE` | `member_id` |
| `EMPTY_SQUAD` | `squad_id` |

As iniciativas envolvidas **não** entram no hash. Era o erro da revisão 1: se elas
entrassem, um terceiro projeto caindo na mesma sprint mudaria o hash e desfaria o
silenciamento — exatamente o que o silenciamento existe para evitar. O preço é que
silenciar "Ana na Sprint 19" silencia o conflito dela naquela sprint mesmo se os
projetos mudarem; isso é o comportamento desejado.

O painel mostra os não silenciados; os silenciados ficam atrás de um contador
expansível, com o motivo visível e o botão de reativar.

---

## 8. Contrato da API

Prefixo `/api/v1`. JSON, `snake_case`. Erros no formato:

```json
{ "error": { "code": "SPRINT_NOT_FOUND", "message": "Sprint 25 não existe.", "details": {} } }
```

`DomainError` → 422 com `code`; não encontrado → 404; conflito de unicidade → 409. Um
único exception handler no `main.py` traduz — nenhum router monta erro à mão.

OpenAPI exposto em `/api/v1/openapi.json`, doc navegável em `/docs`.

```
GET    /api/v1/projects                  ?active=&q=
POST   /api/v1/projects                  cria também a 1ª initiative (RN-I1)
GET    /api/v1/projects/{id}             inclui initiatives
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}             409 se alguma initiative tiver alocação

GET    /api/v1/initiatives               ?project_id=&status=&priority=&layer=&q=
POST   /api/v1/initiatives
GET    /api/v1/initiatives/{id}
PATCH  /api/v1/initiatives/{id}
POST   /api/v1/initiatives/{id}/status   { status } — transições manuais (§6.3)
DELETE /api/v1/initiatives/{id}          409 se houver alocação, ou se for a última
                                         do projeto; sugerir CANCELLED

GET    /api/v1/members                   ?active=true
POST   /api/v1/members
PATCH  /api/v1/members/{id}
DELETE /api/v1/members/{id}              soft delete: is_active = false

GET    /api/v1/squads                    ?active=&sprint_number=  (expande a
                                         composição da sprint pedida)
POST   /api/v1/squads
GET    /api/v1/squads/{id}               inclui memberships por sprint
PATCH  /api/v1/squads/{id}               name, representative_member_id, is_active
DELETE /api/v1/squads/{id}               soft delete: is_active = false

GET    /api/v1/squads/{id}/memberships   ?sprint_from=&sprint_to=
PUT    /api/v1/squads/{id}/memberships   { sprint_from, sprint_to, member_ids }
                                         substitui a composição no intervalo
DELETE /api/v1/squads/{id}/memberships   { sprint_from, sprint_to, member_ids? }

GET    /api/v1/sprints                   ?from=&to=
POST   /api/v1/sprints                   { number?, start_date, end_date }
GET    /api/v1/sprints/next/preview      sem body — propõe number/start/end (RN10)
POST   /api/v1/sprints/next              sem body — cria a proposta
                                         (sem DELETE — D13)

GET    /api/v1/allocations               ?sprint_from=&sprint_to=&squad_id=
                                         &member_id=&initiative_id=&project_id=
POST   /api/v1/allocations               alocação em intervalo
DELETE /api/v1/allocations               body com o intervalo
DELETE /api/v1/allocations/{id}          uma célula

GET    /api/v1/planning/grid             ?sprint_from=&sprint_to=&squad_id=
                                         &member_id=&project_id=
                                         default: trimestre corrente (RN13)
GET    /api/v1/planning/backlog          ?order_by=priority|size|entered_at

GET    /api/v1/alerts                    ?sprint_from=&sprint_to=&include_muted=false
                                         default: da sprint atual (RN12) até a última
                                         sprint cadastrada
POST   /api/v1/alerts/mute               { fingerprint, alert_type, reason }
DELETE /api/v1/alerts/mute/{mute_id}

POST   /api/v1/snapshots/export          → caminhos gerados
POST   /api/v1/snapshots/import?confirm=true   { path, mode: "replace" }  destrutivo
```

### `POST /api/v1/allocations`

```json
{
  "initiative_id": "uuid",
  "squad_id": "uuid",
  "member_id": null,
  "from_sprint_number": 18,
  "to_sprint_number": 22
}
```

Resposta:

```json
{
  "created": [{ "id": "uuid", "sprint_number": 18 }],
  "already_existed": [{ "id": "uuid", "sprint_number": 19 }],
  "missing_sprint_numbers": [23, 24],
  "initiative_status": "PLANNED",
  "alerts": [ /* Alert, como em §7.3 */ ]
}
```

`alerts` é o **estado atual** dos alertas das sprints tocadas pela operação — não um
diff entre antes e depois. É o que a UI precisa para mostrar o aviso no mesmo
instante, sem uma segunda chamada, e é trivial de especificar e testar. Inclui os
silenciados, com `is_muted: true`, para que a UI possa dizer "já silenciado" em vez de
gritar de novo.

### `GET /api/v1/planning/grid`

Formato pensado para renderizar direto, sem o front recalcular nada:

```json
{
  "sprints": [
    { "id": "uuid", "number": 18, "start_date": "2026-08-31",
      "end_date": "2026-09-11", "is_current": true }
  ],
  "groups": [
    {
      "project": { "id": "uuid", "name": "Aurora", "color": "#0052CC",
                   "is_capacity_reserve": false },
      "rows": [
        {
          "initiative": { "id": "uuid", "name": "Catálogo V1",
                          "layer": null, "status": "IN_PROGRESS",
                          "priority": "HIGH" },
          "bars": [
            { "assignee": { "kind": "squad", "id": "uuid", "name": "Alfa" },
              "from_sprint_number": 18, "to_sprint_number": 22,
              "allocation_ids": ["uuid"] }
          ]
        }
      ]
    }
  ],
  "alerts_by_sprint": { "19": ["SQUAD_OVERLOADED", "MEMBER_CONFLICT"] }
}
```

- As linhas vêm **agrupadas por projeto**, e o projeto é quem carrega a cor — é o que
  faz a leitura vertical agrupar.
- O backend consolida sprints contíguas do mesmo responsável em uma `bar`. Uma pausa
  no meio gera duas barras. O front desenha barras, não células — é o que dá a cara de
  Gantt.
- `assignee.kind` é `"squad"` ou `"member"`.
- Por RN8, as barras de uma linha nunca se sobrepõem.
- `alerts_by_sprint` **não** é afetado pelos filtros de `squad_id` / `member_id` /
  `project_id`: o ícone no cabeçalho da coluna reporta a sprint inteira, senão filtrar
  esconderia justamente o conflito que se quer ver.

### `GET /api/v1/planning/backlog`

Retorna `items` — iniciativas com `status = BACKLOG`, excluindo as de projetos com
`is_capacity_reserve` — e `summary`:

```json
{ "count": 7, "estimated_sprints_total": 19, "items_without_estimate": 2 }
```

`estimated_sprints_total` soma só quem tem estimativa. Ordenação `size` usa
`estimated_sprints` com nulos **por último** em qualquer direção.

`DEPRIORITIZED` **não** aparece aqui. É outro lugar (filtro na tela de projetos), e
não se mistura com backlog.

---

## 9. Persistência e snapshot

- **RNF1.** SQLite, arquivo único, caminho por env (`DATABASE_URL`), em `data/`, fora
  da pasta sincronizada. Ligar `PRAGMA foreign_keys=ON` em cada conexão.
- **RNF2.** Migrations com Alembic desde a primeira tabela. Sem `create_all` no
  caminho de produção. Nos testes de HTTP, o schema em memória é criado rodando as
  migrations do Alembic contra a conexão in-memory — não `metadata.create_all()` —
  para que as migrations sejam de fato exercitadas.
- **RNF3.** A cada mutação bem-sucedida, exportar snapshot para `SNAPSHOT_DIR`.
  Implementação: `BackgroundTasks` do FastAPI agenda um export com **debounce** de 5
  segundos, coalescendo as chamadas de uma edição em sequência. O debounce vive em
  `adapters/outbound/snapshot/debounce.py` e é um detalhe de adapter — nem o domínio
  nem o use case sabem dele. A importação `replace` **não** dispara export automático.

Conteúdo do snapshot:

```
snapshots/
├── projects.json
├── initiatives.json
├── members.json
├── squads.json
├── squad_memberships.json
├── sprints.json
├── allocations.json
├── muted_alerts.json
├── meta.json               # única coisa com timestamp de geração
├── plan-sprint-18.md       # um por sprint: quem está em quê
└── plan-grid.md            # a grade inteira em tabela Markdown
```

JSON com chaves ordenadas, indentação de 2 e listas ordenadas por `id`, para o diff no
Git/Drive ficar legível. **Nada de timestamp de geração dentro dos arquivos de
entidade** — muda o arquivo inteiro a cada export sem mudança real de dado. O registro
da geração fica em `meta.json`.

- **RNF4.** Importação do snapshot reconstrói o banco em outra máquina ou após perda.
  Modo `replace` apenas: apaga e recria, dentro de uma transação única. Sem merge —
  merge exige resolução de conflito, que é escopo de outra versão. A importação
  **preserva verbatim** todos os UUIDs e o `created_at` de `MutedAlert`; é isso que
  faz o roundtrip export → import → export produzir arquivos byte-a-byte idênticos,
  que é o critério de aceite da Fase 5.
- **RNF5.** **Sem importação de planilha, CSV ou qualquer outra fonte externa, e sem
  comando `seed`.** Todo dado do sistema entra pela interface. Não existe
  `adapters/outbound/spreadsheet/`, não existe `app.cli seed`. O único import é o de
  snapshot da RNF4, que é restauração, não integração.
- **RNF6.** Offline, sem autenticação, sem chamada externa. Nenhuma dependência que
  faça telemetria. A fonte Inter é self-hosted (§4.2).

---

## 10. Frontend

### 10.1 Direção visual

O pedido é explícito: **parecido com o Jira.** Isso significa a densidade de
informação e as convenções de interação do Jira, não os assets da Atlassian. Não use
logotipos, ícones nem as fontes proprietárias (Charlie Display/Text) da Atlassian.

Concretamente, o que copiar do padrão:

- Sidebar esquerda fixa de 240px, colapsável para 64px, com a navegação por seção.
- Topbar de 56px com busca e o sino de alertas.
- Tabelas densas: linha de 40px, cabeçalho fixo (`sticky`), zebra desligada, hover
  sutil.
- **Lozenges** (as pílulas de status): retângulo de raio pequeno, texto em peso 600,
  tamanho 11px, fundo tonal. Um por status, um por prioridade.
- Avatares circulares de 24px com iniciais, empilhados com sobreposição negativa
  quando forem vários.
- Raio de borda pequeno e consistente: 3px em controles, 4px em cartões. Não arredonde
  tudo em 12px.
- Sombra apenas em elementos que flutuam (modal, dropdown, popover). Nada de sombra em
  cartão estático.
- Ação primária sempre azul e sempre uma por tela.

### 10.2 Tokens (`tokens.css`)

Tailwind v4: a configuração é o CSS. Declarar dentro de `@theme` é o que faz os
utilitários existirem.

```css
@import "tailwindcss";
@import "@fontsource-variable/inter";

@theme {
  /* neutros — a base cinza-azulada é o que faz "parecer Jira" */
  --color-bg:            #F7F8F9;
  --color-surface:       #FFFFFF;
  --color-border:        #DFE1E6;
  --color-border-strong: #C1C7D0;
  --color-text:          #172B4D;
  --color-text-subtle:   #626F86;
  --color-text-disabled: #A5ADBA;

  /* ação */
  --color-primary:       #0052CC;
  --color-primary-hover: #0065FF;
  --color-primary-soft:  #DEEBFF;

  /* semânticos, usados nos lozenges e alertas */
  --color-success:       #216E4E;
  --color-success-soft:  #DCFFF1;
  --color-warning:       #974F0C;
  --color-warning-soft:  #FFF7D6;
  --color-danger:        #AE2E24;
  --color-danger-soft:   #FFECEB;
  --color-neutral-soft:  #F1F2F4;

  /* cor default de projeto sem cor definida (DEFAULT_PROJECT_COLOR) */
  --color-project-default: #7A869A;

  /* tipografia */
  --font-sans: "Inter Variable", ui-sans-serif, -apple-system, "Segoe UI", Roboto,
               sans-serif;
  --text-11: 0.6875rem;
  --text-12: 0.75rem;
  --text-14: 0.875rem;
  --text-16: 1rem;
  --text-20: 1.25rem;
  --text-24: 1.5rem;

  /* espaço — grade de 4px */
  --spacing-1: 4px;
  --spacing-2: 8px;
  --spacing-3: 12px;
  --spacing-4: 16px;
  --spacing-5: 24px;
  --spacing-6: 32px;

  --radius-sm: 3px;
  --radius-md: 4px;
  --radius-lg: 8px;

  --shadow-overlay: 0 4px 8px -2px rgba(9,30,66,.25), 0 0 1px rgba(9,30,66,.31);
}
```

Corpo de texto em 14px, rótulos em 12px, título de página em 20px semibold. Sem
`text-transform: uppercase` em rótulos. Sem gradiente em nenhum lugar.

Paleta das barras da grade: **uma cor por projeto**, definida no cadastro do projeto,
para que a leitura vertical agrupe. Projeto sem cor usa
`--color-project-default`. `is_capacity_reserve` desenha listras diagonais em cima da
cor.

### 10.3 Telas

**`/planning` — a tela principal.** Alternador Grade | Lista no cabeçalho. Janela
default: trimestre corrente (RN13).

*Grade.* Linhas = iniciativas, agrupadas por projeto (cabeçalho de grupo com o nome e
a cor do projeto). Colunas = sprints. Coluna da esquerda congelada; sprints com scroll
horizontal; a sprint atual (RN12) com marcação de coluna. Barra colorida cobre o
intervalo, com o nome da squad ou da pessoa dentro (elidido se não couber, título
completo no `title`). Célula vazia mostra um `+` no hover que abre o diálogo de
alocação já com iniciativa e sprint preenchidos. Ícone de alerta no cabeçalho da
coluna quando aquela sprint tem alerta.

```
┌──────────────────────────┬──────┬──────┬──────┬──────┬──────┐
│ Iniciativa               │  18  │  19  │  20  │  21  │  22  │
│                          │      │  ⚠   │      │      │      │
├──────────────────────────┼──────┴──────┴──────┴──────┴──────┤
│ ▸ Aurora                 │                                  │
│   Catálogo V1        Alta│ ███ Alfa █████████████████████   │
│   Serviço de Envio  Média│      │ ██ Bruno ████│     +      │
├──────────────────────────┼──────┴──────────────┴────────────┤
│ ▸ Boreal                 │                                  │
│   Portal Externo     Alta│      │ ██ Beta █████│     +      │
├──────────────────────────┼──────┴──────────────┴────────────┤
│ ▸ Plantão  (reserva)     │ ╱╱╱╱╱╱ Alfa ╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱   │
└──────────────────────────┴──────────────────────────────────┘
```

Arrastar para mover ou redimensionar a barra é desejável, não obrigatório. Se sair
frágil, entregue o diálogo e pare — clicar na barra abre um popover com "Mover",
"Estender até", "Remover". A grade legível e confiável vale mais que a grade
arrastável e instável.

*Lista.* Tabela: projeto, iniciativa, camada, prioridade, responsável, sprint inicial,
sprint final, status. Ordenável, filtro por squad, membro e sprint em ambas as visões,
com o filtro persistido na URL.

**`/backlog`.** Tabela das iniciativas com status `BACKLOG`. Contador no topo: quantas
iniciativas e quantas sprints de trabalho elas somam (com aviso de quantas estão sem
estimativa). Ordenação por prioridade, tamanho ou data de entrada. Botão "Alocar" em
cada linha, abrindo o mesmo diálogo.

**`/projects`.** CRUD de projeto e de iniciativa. Painel lateral (drawer) para criar e
editar, não página nova. O drawer de projeto lista as iniciativas dele e permite
adicionar. Filtro de status inclui `DEPRIORITIZED` — é aqui que o trabalho parado é
revisitado.

**`/team`.** Três blocos na mesma página:
1. membros (tabela + drawer);
2. squads (tabela + drawer com nome, representante, ativo);
3. **composição por sprint** — a matriz membro × sprint de uma squad, que é o que
   torna o caso da Carla editável e mostra, para cada membro, em qual outra squad ele
   já está naquela sprint. É onde o conflito Ana/Carla/Bruno fica visível antes
   de virar alerta.

**`/sprints`.** Lista com datas, marcação da sprint atual, e o botão "Criar próxima
sprint" que mostra a proposta (RN10) antes de confirmar. Sem ação de excluir.

**Painel de alertas.** Sino na topbar com contador (só `WARNING` não silenciado
alimenta o contador), abrindo um painel lateral agrupado por sprint. Cada alerta com a
frase específica, link para o contexto e ação "Silenciar" que pede o motivo.
Silenciados atrás de um contador expansível, com motivo visível e botão "Reativar"
(usa `mute_id`).

### 10.4 Configuração do Astro e CORS

Decisões pequenas, mas necessárias já na Fase 0, para não ficarem em aberto:

- **`output: 'static'`**, sem adapter. Não há SSR, não há rota de servidor no front:
  o Astro entrega o shell e as ilhas React buscam tudo do backend. Isso também é o que
  mantém RNF6 (nada roda em servidor além da API local).
- **Redirect de `/`**: `redirects: { '/': '/planning' }` no `astro.config.mjs`. Não
  use `<meta http-equiv="refresh">`.
- **Porta do dev server**: 4321 (default do Astro). A da API é 8000.
- **CORS** no `main.py`: `allow_origins = ["http://localhost:4321",
  "http://127.0.0.1:4321"]`, `allow_credentials = False`, todos os métodos e headers.
  Vem de `settings.py`, não hardcoded no router.

### 10.5 Regras do front

- Um cliente de API só (`lib/api.ts`). Nenhum `fetch` solto em componente. Base URL
  vem de `import.meta.env.PUBLIC_API_URL`.
- Tipos derivados do OpenAPI do backend (`mise run types`), não redigitados à mão.
- Estado de servidor com **TanStack Query** nas ilhas. Uma escolha, sem mistura.
- Toda tela tem os quatro estados desenhados: carregando (skeleton, não spinner
  centralizado), vazio (com a ação que resolve), erro (o que falhou e como tentar de
  novo), sucesso.
- Estado vazio é convite: "Nenhuma iniciativa no backlog. Cadastre um projeto para
  começar a planejar."
- Erro não pede desculpa e não é vago. Diz o que aconteceu.
- Acessibilidade de base: foco visível, navegação por teclado no diálogo de alocação,
  `prefers-reduced-motion` respeitado, contraste AA.
- Animação só como resposta a ação do usuário. Nada de entrada com fade-and-slide em
  cada seção.

### 10.6 Se o front travar

Está autorizado prototipar a tela no Lovable e trazer o resultado. O caminho: gerar o
layout lá em React + Tailwind, extrair o **markup e as classes**, e reescrever contra
os tokens de §10.2 antes de integrar. Não cole componente que traga `shadcn`,
biblioteca de ícone nova ou paleta própria sem substituir os tokens — três paletas
concorrentes no mesmo app é pior que uma tela feia.

---

## 11. Qualidade

- Testes de domínio sem nenhum mock e sem banco: os quatro alertas, estabilidade do
  `fingerprint`, alocação efetiva do membro (§6.8), tabela de transição de status
  (§6.3, inclusive as transições proibidas), invariantes de sprint, `is_current` com
  folga entre sprints, consolidação de barras.
- Testes de use case com repositórios fake in-memory que implementem os `Protocol`.
- Testes de HTTP com `TestClient` e SQLite em memória, cobrindo os códigos de erro.
- Teste da regra de dependência (§5).
- Teste de roundtrip de snapshot: export → import `replace` → export produz arquivos
  idênticos.
- `ruff` e `mypy --strict` em `domain/` e `application/` limpos. Adapters podem ser
  menos rígidos.
- Cobertura não é meta. Alertas, alocação em intervalo, transição de status e
  composição de squad por sprint cobertos de verdade são.

---

## 12. Pavimento para a v2

A v2 quer: ler relatório de reunião (read.ai) via LLM (Claude, Gemini) e propor tarefas
em um board kanban.

Na v1, isso significa **exatamente três coisas** e nada mais:

1. `domain/ports/task_suggester.py` com um `Protocol` declarado e não implementado:
   ```python
   class TaskSuggester(Protocol):
       def suggest(self, transcript: str, context: PlanningContext) -> list[SuggestedTask]: ...
   ```
   Sem provider, sem SDK, sem chave de API, sem dependência nova no `pyproject.toml`.
2. A tabela `external_refs` (§6.10), vazia.
3. IDs estáveis (UUID) em `Project`, `Initiative` e `Sprint`, e API versionada.

Não crie pasta de integração, não crie configuração de modelo, não escreva prompt.
Quando a v2 chegar, a orquestração multi-provedor com fallback entra como um adapter
`outbound/llm/` implementando essa porta — que é o padrão que o time já usa.

---

## 13. Plano de execução

Cada fase termina com commit, testes passando e uma demonstração possível. **Pare no
fim de cada fase e reporte antes de seguir.**

| Fase | Entrega | Critério de aceite |
|---|---|---|
| 0 | Scaffold: `mise.toml`, `pyproject.toml`, `package.json`, `.gitignore`, README, lint configurado, um teste-fumaça de cada lado | `mise install && mise run setup` funciona em máquina limpa; `mise run lint` passa; `mise run test` verde. O teste-fumaça não é zelo: `pytest` sem nenhum teste sai com código 5 e a task falharia |
| 1 | Domínio completo: entidades, value objects, portas, `alert_service`, `fingerprint`, `planning_rules`, erros | `pytest tests/domain` verde, sem SQLAlchemy nem FastAPI importados; teste da regra de dependência passa; os quatro alertas e a tabela de transição cobertos |
| 2 | Use cases com repositórios fake | `pytest tests/application` verde; nenhum use case conhece banco |
| 3 | Persistência: models, mappers, repositórios, migration inicial | Migration sobe e desce; repositórios passam a mesma suíte dos fakes |
| 4 | API HTTP: routers, schemas, wiring, handler de erro, OpenAPI | `pytest tests/http` verde; `/docs` navegável; todos os endpoints de §8 existem |
| 5 | CLI + snapshot: `snapshot export/import`, debounce na mutação | Roundtrip export → import → export produz arquivos idênticos; um banco apagado é reconstruído do snapshot |
| 6 | Shell do front: layout, tokens, sidebar, topbar, componentes de UI, cliente de API tipado | Navegação entre as cinco rotas com dados vindos da API |
| 7 | Telas de planejamento (grade + lista) e backlog | Uma iniciativa cadastrada à mão aparece na grade no intervalo correto, agrupada pelo projeto |
| 8 | Telas de projetos, time (com composição por sprint), sprints e painel de alertas | Os quatro alertas aparecem nos cenários do §13.1; silenciar e reativar funcionam |
| 9 | Acabamento: estados vazio/erro/carregando, atalhos de teclado, README de uso | Uma sprint inteira planejada do zero sem tocar na planilha |

Fases 1 e 2 antes de qualquer linha de SQLAlchemy ou FastAPI. Se o domínio precisar do
banco para ser testado, a arquitetura está errada e é mais barato consertar na fase 1.

### 13.1 Cenários de aceite dos alertas

Não existe `seed` (RNF5). Estes cenários são **fixtures de teste** em
`tests/domain/` e `tests/application/`, e o roteiro manual da Fase 8. Não são dados
pré-cadastrados no banco.

| # | Cenário | Alerta esperado |
|---|---|---|
| A | Squad `Alfa` alocada em `Aurora / Catálogo` e `Boreal / Portal Externo` na Sprint 19 | `SQUAD_OVERLOADED` na 19 |
| B | Mesma coisa, mas a segunda iniciativa é de um projeto com `is_capacity_reserve` | nenhum |
| C | Ana em `Alfa` e `Beta` na Sprint 19; as duas squads em iniciativas diferentes | `MEMBER_CONFLICT` na 19 |
| D | Carla em `Beta` nas sprints 18–19 e em `Alfa` da 20 em diante | nenhum em nenhuma sprint |
| E | Diana ativa, sem membership nem alocação direta na Sprint 20 (futura) | `MEMBER_IDLE` na 20 |
| F | `Gama` alocada em `API de Cobrança` na Sprint 21, sem membership na 21 | `EMPTY_SQUAD` na 21 |
| G | Silenciar o cenário C com motivo; depois alocar uma terceira iniciativa à `Alfa` na 19 | o silenciamento de C **continua** valendo (fingerprint estável) |

Os nomes acima são só rótulos de fixture. Nada deles é hardcoded no sistema.

---

## 14. Restrições para quem implementa

- Pergunte antes de adicionar qualquer dependência que não esteja em §4.1.
- Não invente campo, tela ou endpoint que não esteja aqui. Se faltar algo, aponte e
  espere.
- Não implemente nada da lista de §2 "Fora".
- Documentação, comentários, mensagens de erro e UI em português. Código em inglês.
- Commits pequenos, um por unidade coerente, mensagem em português no imperativo.
- Não escreva `# TODO` sem um item correspondente no relatório de fim de fase.

---

## 15. O que mudou da revisão 1

Registro das mudanças estruturais, para quem tiver lido a versão anterior.

**Modelo**
- `Product` (enum fixo) **removido**. `Project` assumiu o papel de agrupamento e é
  cadastrado.
- `Initiative` **criada** entre `Project` e `Allocation` (D15, confirmado). É ela que
  tem prioridade, status, estimativa e alocação. É a linha do Gantt. `Project` ficou
  como agrupamento puro — sem status, sem prioridade, sem alocação.
- `Squad.member_ids` **removido**, substituído por `SquadMembership` (por sprint).
- `Squad.representative_member_id` **adicionado**.
- `Allocation.project_id` → `initiative_id`; `member_id` **adicionado** como
  alternativa a `squad_id`.
- `InitiativeStatus` ganhou `DEPRIORITIZED`; as transições viraram uma tabela
  explícita, com o caminho de volta ao `BACKLOG` fechado para quem já começou.
- `is_capacity_reserve` continua em `Project`, mas passou a ser configuração explícita
  no cadastro (ligável e desligável) e agora neutraliza **também** `MEMBER_CONFLICT`,
  não só `SQUAD_OVERLOADED`. Era o ponto que fazia o Plantão travar a pessoa.
- `Project.color` substituiu a derivação de cor por produto. Sem cor → cor neutra
  padrão.
- Porta `Clock` **adicionada**, para `entered_at` e `is_current` serem testáveis.

**Regras**
- `SQUAD_IDLE` **substituído** por `MEMBER_IDLE` (D16, confirmado). Squad é
  agrupamento temporário: uma squad sem alocação não é um problema, mas uma **pessoa**
  sem frente numa sprint futura é exatamente a pergunta de capacidade que interessa.
- `fingerprint` ancorado no sujeito (squad ou membro) + sprint. Antes incluía as
  iniciativas, o que quebrava o silenciamento.
- Alerta agora devolve `mute_id` e `mute_reason`, sem os quais não havia como
  reativar.
- Unicidade da alocação passou a `(initiative_id, sprint_id)` (D17, confirmado): um
  responsável por célula. Duas squads na mesma frente ao mesmo tempo deveriam ser uma
  squad só — mas duas squads em iniciativas diferentes do mesmo projeto são normais, e
  é por isso que a chave é a iniciativa e não o projeto.
- `DELETE /sprints/{id}` **removido**. Sprint é marcação de tempo.
- `is_current` definido como "maior `start_date` que já passou", o que resolve as
  folgas de calendário entre sprints.
- `create_next_sprint` definido: próxima segunda após o fim da anterior,
  `start + 11 dias`, editável.
- Sprint inexistente no intervalo: alocação **parcial** com relatório, não erro total.
- Backlog voltou a ser **por status**, não por ausência de alocação — o que elimina a
  contradição da revisão 1.
- `alerts` na resposta de `POST /allocations` é o estado atual das sprints tocadas, não
  um diff.
- Janela default da grade: trimestre corrente.

**Escopo**
- Importação de planilha/CSV (`RNF5` antiga) e comando `seed` **removidos do escopo**.
  Com eles saem `adapters/outbound/spreadsheet/` e o teste de CSV bagunçado; entram os
  cenários de fixture do §13.1.

**Tooling**
- Versões todas verificadas e pinadas (§4.1). Python 3.12 → 3.14, Node 22 → 24,
  Astro → 7.2.x, TypeScript → 6.0.x, SQLAlchemy com teto `<2.1`, mypy 2.x.
- Conflito mise × uv resolvido: o venv é do uv, em `backend/.venv` (D9).
- Caminhos de `lint` corrigidos; `data/` movido para dentro do repositório;
  `snapshots/` passa a ser ignorado pelo Git.
- `typer`, `pydantic-settings`, `openapi-typescript`, `@tanstack/react-query` e
  `@fontsource-variable/inter` agora estão declarados em §4.1, em vez de citados no
  corpo do texto sem constar da lista.
- Tokens do §10.2 migrados para `@theme` do Tailwind v4 (antes eram `:root` puro, o
  que não gera utilitário).

---

## 16. Pontos abertos

Três itens ainda não decididos. Nenhum bloqueia implementação: cada um tem uma
premissa em vigor, que é o que o código deve seguir até haver decisão em contrário.
Quando decidir, mova o item para §3 ou §7 e apague daqui.

| # | Pergunta | Premissa em vigor | Quando dói |
|---|---|---|---|
| A1 | "Trimestre corrente" (janela default da grade, RN13) é o trimestre **civil** (jan–mar, abr–jun, jul–set, out–dez) ou um trimestre fiscal deslocado? | Trimestre civil, derivado da data do `Clock` | Fase 7, ao abrir a grade. Trocar é uma função de domínio de três linhas |
| A2 | `MEMBER_IDLE` precisa de teto? Nove membros × sete sprints futuras podem virar dezenas de itens informativos | Sem teto: toda sprint da atual em diante entra | Fase 8, quando o volume real aparece no painel. Candidato natural: limitar à sprint atual + as duas seguintes |
| A3 | Membro inativado que ainda tem `SquadMembership` em sprint futura — a UI avisa, ou ele só desaparece? | Só desaparece: os alertas ignoram inativos e a membership fica no dado, como histórico | Fase 8. É um aviso a mais, não uma mudança de modelo |
