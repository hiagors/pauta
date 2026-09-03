# Pauta

Sistema local de planejamento de sprints do time. A especificação completa
está em `docs/spec.md` (revisão 2) — leia antes de qualquer implementação.
`docs/requisitos-v1.md` é a mesma coisa em linguagem de negócio; onde os dois
divergirem, o spec vence.

## Regras invioláveis

- `backend/app/domain/` importa apenas stdlib. Nada de sqlalchemy,
  pydantic ou fastapi. Nada de `date.today()` — a data entra pela porta `Clock`.
- `application/` importa `domain/`. Nunca `adapters/`.
- Identificadores de código em inglês. Documentação, comentários,
  mensagens de erro e UI em português.
- Nenhuma dependência fora da seção 4.1 do spec sem perguntar antes.
- Não implemente nada da lista "Fora do escopo" (seção 2 do spec).
- Sem `seed`, sem importação de planilha/CSV. Todo dado entra pela UI.
- Sprint nunca é excluída. Membro nunca é apagado (só `is_active = false`).

## Vocabulário que muda o código

- **Projeto** é agrupador (nome, cor, `is_capacity_reserve`). Não tem status
  nem alocação.
- **Iniciativa** é a unidade de trabalho: prioridade, status, estimativa e
  alocação. É a linha do Gantt.
- Composição de squad é **por sprint** (`SquadMembership`), não lista estática.
- Alocação tem **um** responsável por sprint: uma squad **ou** um membro.

## Comandos

- `mise run setup` — prepara a máquina do zero
- `mise run dev` — sobe API (:8000) e front (:4321)
- `mise run test` — pytest + vitest
- `mise run lint` — ruff + mypy --strict (backend) + tsc --noEmit (front)
- `mise run types` — regenera os tipos do front a partir do OpenAPI

## Estado

Spec na revisão 2. D15–D17 confirmados em 02/09/2026: alocação é na iniciativa
(não no projeto), o terceiro alerta é `MEMBER_IDLE` (não `SQUAD_IDLE`), e a
unicidade da alocação é `(initiative_id, sprint_id)`.

Três pontos menores seguem abertos, com premissa em vigor documentada na seção 16
do spec — siga a premissa, não pergunte de novo.

Fases concluídas: **0** (scaffold), **1** (domínio puro), **2** (use cases com
repositórios fake), **3** (persistência em SQLite), **4** (API HTTP), **5**
(CLI + snapshot), **6** (shell do front) e **7** (planejamento e backlog).
Próxima: **Fase 8** (projetos, time, sprints e painel de alertas, seção 10.3).

Todos os endpoints da seção 8 existem, `/snapshots` inclusive. A lista vive em
`tests/http/test_app.py` e é conferida nas duas direções — falta e excesso.

A consulta filtrada dos repositórios se chama `list_all`, não `list`: um método
`list` no corpo da classe sombreia o builtin e quebra as anotações `list[X]` dos
métodos declarados depois dele.

`PATCH` usa o sentinela `UNSET` de `application/dto/common.py`. Campo ausente e
campo nulo são coisas diferentes: `color: null` limpa a cor do projeto, e a
ausência de `color` não mexe no que está gravado.

O `pytest` roda com `--import-mode=importlib` e `consider_namespace_packages`.
No modo `prepend` dois arquivos de teste com o mesmo nome de base em pastas
diferentes (`tests/domain/test_allocation.py` e
`tests/application/test_allocation.py`) colidem na importação.

Repositório faz `flush`, nunca `commit`. Quem abre e fecha a transação é o
adapter de entrada — a requisição HTTP na Fase 4, o comando da CLI na Fase 5.

Mapper reidrata pelo construtor da dataclass, não por `Entity.create()`, que é
para entidade nova (gera `id`, lê `entered_at` do `Clock`).

A busca `?q=` usa a função `pauta_casefold`, registrada em cada conexão SQLite
(`persistence/session.py`), porque o `lower()` nativo só dobra ASCII e os nomes
deste sistema são todos em português. O `PRAGMA foreign_keys=ON` entra pelo
mesmo listener de `connect`, e pelo mesmo motivo: é por conexão, não por banco.

Os 36 testes de contrato de `tests/persistence/` rodam duas vezes, contra os
fakes e contra o SQLAlchemy. Porta nova entra na suíte de contrato, não em
teste separado por implementação.

`deps.py` é onde a transação abre e fecha: `provide_session` faz `commit` no
fim e `rollback` na exceção — inclusive na `DomainError` que vira 4xx. `Ports`
tem os mesmos nomes de campo que os use cases e `use_case()` injeta por nome,
igual ao `Fakes` da suíte de use case; não existe fábrica por use case.

O `Clock` entra pela dependência `provide_clock`, e não dentro de
`Ports.build`, para a suíte de HTTP congelar a data. `is_current` (RN12) e a
janela default da grade (RN13) dependem de hoje.

`PATCH`: `PatchModel` publica todo campo como opcional e **sem `default`**
(`__get_pydantic_json_schema__`). O `openapi-typescript` trata propriedade com
`default` como não-opcional, e o tipo gerado passaria a exigir todos os campos.
Os defaults do Python ficam como placeholder de tipo, nunca lidos: quem decide
é `model_fields_set`.

O 422 documentado no OpenAPI é o `ErrorEnvelope` da seção 8, não o
`HTTPValidationError` que o FastAPI publica sozinho — o handler de `errors.py`
nunca devolve esse formato.

O `uvicorn` sobe por `--factory ...main:create_app`. Não existe
`app = create_app()` no fim do `main.py`: importar o módulo não lê o ambiente
nem abre banco.

Os testes de HTTP usam SQLite `:memory:` com `StaticPool`, e o schema é criado
**rodando as migrations** contra essa conexão, injetada em
`config.attributes["connection"]` (RNF2). Um `:memory:` morre com a conexão;
com pool normal o Alembic migraria um banco descartável.

O `fileConfig` do `migrations/env.py` roda com
`disable_existing_loggers=False`. As migrations rodam dentro do processo de
teste, e o default do `fileConfig` desligaria os loggers da aplicação — o do
export automático entre eles.

Export e import de snapshot passam por uma terceira porta, `SnapshotStore`
(`dump`/`replace`), e não pelos oito repositórios: `replace` precisaria de um
`delete` que membro, squad e sprint não têm por regra (seção 6.4, 6.5, D13).

A tarefa de `BackgroundTasks` que agenda o export roda **antes** do `commit` da
requisição (o teardown das dependências com `yield` vem depois dela) e **não**
roda quando o endpoint levanta exceção. As duas coisas juntas é que fazem a
RNF3 valer: a tarefa só arma o debounce, e o export sai 5 segundos depois, em
sessão própria, com o dado já gravado.

`SNAPSHOT_DIR` é obrigatório no ambiente, como `DATABASE_URL`, e as
dependências o leem de `app.state.settings` (`provide_settings`) — não de
`get_settings()`, senão a suíte escreveria na pasta sincronizada de verdade.

O use case de importação é `use_cases/snapshots/import_.py`, com o sublinhado
final: `import` é palavra reservada e `from ... import import` não existe.

No `.gitignore`, `/data/` e `/snapshots/` são ancorados na raiz. Sem a barra
inicial o padrão casa com qualquer nível, e `snapshots/` escondia do Git o
pacote `application/use_cases/snapshots/`.

## Front (Fase 6)

`lib/api.ts` é o único lugar que chama `fetch`. Os tipos vêm de `lib/types.ts`,
gerado por `mise run types` **com a API no ar** — o comando lê
`http://127.0.0.1:8000/api/v1/openapi.json`, não um arquivo.

`QueryOf<K>` e `BodyOf<K>` do `api.ts` leem `operations[K]` do OpenAPI em vez de
repetir a lista de filtros. Filtro novo no backend chega ao front regerando os
tipos, sem editar o cliente.

Cada ilha do Astro é uma raiz React própria e precisa do seu provider; o
`QueryClient` é um só por página. É o que `withQuery()` (`lib/query.ts`) resolve.
`query.ts` usa `createElement` em vez de JSX porque a estrutura da seção 5 pede
`.ts`, não `.tsx`.

Ícone de sprite: o traço mora na classe `.icon` do `global.css`, não em atributo
no `<symbol>`. `<use>` clona o conteúdo para uma shadow tree e herda as
**propriedades CSS** do `<svg>` que referencia, não os atributos de apresentação
do `<svg>` de origem — sem a classe todo ícone sai preenchido de preto.

O estado colapsado da sidebar é `data-sidebar="collapsed"` no `<html>`, aplicado
por um script `is:inline` no `<head>` do `AppShell`. Num `useEffect` a barra
abriria em 240px e encolheria na frente do usuário a cada carga.

`formatDate` corta a string ISO em vez de usar `new Date(iso)`: o construtor lê
data simples como UTC e, em UTC-3, 31/08 volta como 30/08.

`mise exec` **sobrescreve** as variáveis do `[env]` do `mise.toml`. Para rodar a
API contra um banco descartável, chame `backend/.venv/bin/uvicorn` direto com
`DATABASE_URL` e `SNAPSHOT_DIR` no comando — com `mise exec` o dado de teste vai
parar em `data/pauta.sqlite` e em `snapshots/`.

## Planejamento (Fase 7)

A grade e a lista leem a **mesma** resposta de `GET /planning/grid`. Alternar
Grade|Lista não custa requisição, e a lista não tem endpoint próprio: barra é
exatamente "responsável, sprint inicial, sprint final".

A grade só traz iniciativa que tem alocação na janela (`get_grid` parte das
`allocations`). Iniciativa nova aparece lá **depois** de alocada, e o caminho
para alocá-la é o botão "Alocar" do backlog.

Não existe endpoint de mover alocação (§8). "Mover" e "Estender até" são
`POST /allocations` no intervalo novo e `DELETE /allocations` na sobra —
`rangeLeftovers` calcula a sobra, em até dois pedaços. A ordem é obrigatória:
criar primeiro (RN1 é idempotente), apagar depois. Invertida, uma falha no meio
deixaria a iniciativa sem alocação nenhuma.

Uma linha da lista é uma **barra**, não uma iniciativa: quem troca de
responsável no meio da janela aparece duas vezes.

A grade é um `grid` CSS único do cabeçalho à última linha, com uma faixa
`minmax(0, 1fr)` no fim para as linhas não pararem no meio do cartão. A
marcação da sprint atual é um `<div>` absoluto atrás do grid, posicionado com
as mesmas constantes `LEAD_WIDTH`/`COLUMN_WIDTH` do `grid-template-columns` —
tingir só o cabeçalho sumiria ao rolar.

`alerts_by_sprint` não é afetado pelos filtros, por contrato (§8). O ícone no
cabeçalho da coluna continua igual com a grade filtrada em uma linha só; há
teste manual disso no fim da fase.

O filtro vive na URL (`lib/url-state.ts`), com `replaceState`: mexer em filtro
não é navegar. O hook devolve `mounted` como terceiro item porque o Astro
renderiza a ilha no build, onde não há `location` — quem chama segura o
esqueleto até ele virar `true`, senão o HTML do build diverge do primeiro
render do cliente.

Verificação de interação sem dependência nova: Chrome com
`--remote-debugging-port` e um script Node no scratchpad falando CDP pelo
`WebSocket` global do Node 24. Não entra `puppeteer` no projeto.
