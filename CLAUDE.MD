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

Fases concluídas: **0** (scaffold) e **1** (domínio puro). Próxima: **Fase 2**
(use cases com repositórios fake, seção 13 do spec).

A consulta filtrada dos repositórios se chama `list_all`, não `list`: um método
`list` no corpo da classe sombreia o builtin e quebra as anotações `list[X]` dos
métodos declarados depois dele.
