# Pauta

Planejamento de sprints do time, rodando local. Sem autenticação e sem rede
externa: uma API FastAPI em `:8000`, um front Astro em `:4321` e um SQLite em
arquivo único dentro de `data/`.

A especificação está em [`docs/spec.md`](docs/spec.md); a mesma coisa em
linguagem de negócio, em [`docs/requisitos-v1.md`](docs/requisitos-v1.md).

## Preparar a máquina

Só o [mise](https://mise.jdx.dev) precisa estar instalado. Ele cuida de Python,
Node, uv e pnpm nas versões pinadas em `mise.toml`.

```sh
mise trust       # autoriza o mise.toml deste diretório
mise install     # instala os runtimes
mise run setup   # cria data/ e snapshots/, instala dependências, aplica migrations
```

Na primeira entrada no diretório o mise avisa que `backend/.venv` não existe.
É esperado: o venv é do `uv` e nasce no `mise run setup`.

## Rodar

```sh
mise run dev     # API em :8000 e front em :4321
```

As duas tarefas sobem em paralelo e não são encerradas juntas — se uma cair,
reinicie com `mise run dev:api` ou `mise run dev:web`.

## Tarefas

| Comando | O que faz |
|---|---|
| `mise run setup` | Prepara a máquina do zero |
| `mise run dev` | Sobe API (`:8000`) e front (`:4321`) |
| `mise run test` | `pytest` + `vitest` |
| `mise run lint` | `ruff check`, `ruff format --check` e `mypy --strict` no domínio e na aplicação |
| `mise run fmt` | Formata o backend com o `ruff` |
| `mise run types` | Regenera `frontend/src/lib/types.ts` a partir do OpenAPI (exige a API no ar) |
| `mise run snapshot` | Exporta o snapshot para a pasta sincronizada |

## Estrutura

```
backend/    API FastAPI em arquitetura hexagonal (domain, application, adapters)
frontend/   Astro com ilhas React e Tailwind
data/       banco SQLite — ignorado pelo Git
snapshots/  saída em JSON e Markdown — ignorada pelo Git
docs/       especificação e requisitos
```

`backend/uv.lock` e `frontend/pnpm-lock.yaml` são versionados: são eles que
travam na prática as versões da seção 4.1 do spec.

## Estado

Fase 0 (scaffold) concluída. As fases seguintes estão na seção 13 do spec. Por
enquanto o front não tem nenhuma rota (`src/pages/` chega na Fase 6) e o backend
não tem nenhuma migration aplicada além do controle do Alembic (Fase 3), então
`mise run dev` ainda não tem tela para mostrar.
