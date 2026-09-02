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
- `mise run lint` — ruff + mypy --strict
- `mise run types` — regenera os tipos do front a partir do OpenAPI

## Estado

Spec na revisão 2. D15–D17 confirmados em 02/09/2026: alocação é na iniciativa
(não no projeto), o terceiro alerta é `MEMBER_IDLE` (não `SQUAD_IDLE`), e a
unicidade da alocação é `(initiative_id, sprint_id)`.

Três pontos menores seguem abertos, com premissa em vigor documentada na seção 16
do spec — siga a premissa, não pergunte de novo.

Fases concluídas: **0** (scaffold), **1** (domínio puro), **2** (use cases com
repositórios fake), **3** (persistência em SQLite), **4** (API HTTP) e **5**
(CLI + snapshot). Próxima: **Fase 6** (shell do front, seção 13 do spec).

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
