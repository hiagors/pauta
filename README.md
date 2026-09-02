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

## Snapshot

O banco é a fonte da verdade; `snapshots/` é saída, e é a pasta que fica no
Drive. A cada alteração bem-sucedida pela API o snapshot é reexportado
sozinho, cinco segundos depois da última alteração da sequência — editar dez
coisas seguidas gera **um** export, não dez.

Para exportar à mão:

```sh
mise run snapshot                       # para a pasta do SNAPSHOT_DIR
cd backend && uv run python -m app.adapters.inbound.cli snapshot export --path /tmp/copia
```

A pasta tem os oito JSON das entidades, um `meta.json` com a hora da geração e
os arquivos de leitura: `plan-sprint-18.md` (quem está em quê naquela sprint) e
`plan-grid.md` (a grade inteira em tabela).

Para restaurar em outra máquina, ou depois de perder o banco:

```sh
cd backend
uv run alembic upgrade head                                    # banco vazio
uv run python -m app.adapters.inbound.cli snapshot import ../snapshots
```

**A importação apaga tudo e recria** a partir da pasta — é restauração, não
sincronização. Ela pergunta antes; `--yes` pula a pergunta. Os mesmos dois
caminhos existem na API, em `POST /api/v1/snapshots/export` e
`POST /api/v1/snapshots/import?confirm=true`.

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

Fases 0 a 5 concluídas (seção 13 do spec): scaffold, domínio, use cases,
persistência em SQLite, API HTTP e o snapshot com a CLI.

O backend já responde: com `mise run dev:api` no ar, a documentação navegável
fica em <http://127.0.0.1:8000/docs> e o OpenAPI em `/api/v1/openapi.json`.
Todos os endpoints da seção 8 do spec existem.

O front ainda não tem nenhuma rota — `src/pages/` é a Fase 6 —, então
`mise run dev:web` sobe um servidor sem tela para mostrar. Não existe `seed`:
todo dado entra pela API, ou pela interface quando ela existir.
