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

## Usar

A interface abre em <http://localhost:4321> e cai direto no planejamento. Não
existe `seed` nem importação de planilha: **todo dado entra pela tela**.

### Planejar uma sprint do zero

A ordem abaixo não é sugestão — cada passo depende do anterior existir.

**1. Sprints.** Em *Sprints*, "Criar a primeira sprint": informe o número (o
primeiro raramente é 1) e as datas. O fim é sugerido em duas semanas de
calendário, e é editável. Da segunda em diante o botão vira "Criar próxima
sprint" e já vem com a proposta pronta — número seguinte, início na segunda
depois do fim da última. Crie de uma vez as sprints do trimestre: composição de
squad e alocação só existem em sprint cadastrada.

Confira as datas antes de confirmar: sprint não é excluída nem editada — a
numeração é sequencial sem buraco, e permitir apagar quebraria isso. Uma data
errada se corrige restaurando um snapshot anterior.

**2. Pessoas.** Em *Time*, "Nova pessoa". O nome curto é o que aparece dentro
das barras da grade, então prefira o primeiro nome. Quem sai do time é marcado
como inativo, nunca apagado: apagar reescreveria o passado.

**3. Squads.** No mesmo lugar, "Nova squad". Só nome e representante — a squad
**não** tem lista de membros. O representante é a ponte com a squad e não
precisa executar nada nela.

**4. Composição.** O terceiro bloco de *Time* é a matriz pessoa × sprint. Marque
quem está na squad em cada sprint. É por sprint de propósito: alguém pode estar
numa squad até a Sprint 19 e em outra da 20 em diante sem que isso seja
conflito. Se a pessoa já estiver em outra squad naquela sprint, a célula diz
qual — em vermelho quando ela ficar nas duas ao mesmo tempo.

**5. Projetos e iniciativas.** Em *Projetos*, "Novo projeto". Escolha a cor: é
ela que pinta as barras da grade, e é o que faz a leitura vertical agrupar. O
projeto já nasce com a primeira iniciativa, de mesmo nome — clique nela para
renomear, dar prioridade e estimativa em sprints. Projetos com mais de uma
frente ganham iniciativas novas pelo botão do cabeçalho do grupo.

Marque como **reserva de capacidade** o projeto de sustentação sob demanda: as
iniciativas dele não contam para sobrecarga de squad nem para conflito de
pessoa, e não aparecem no backlog.

**6. Alocação.** Iniciativa sem alocação vive no *Backlog*. O botão "Alocar" de
cada linha abre o diálogo com a iniciativa e a sprint inicial já preenchidas:
escolha uma squad **ou** uma pessoa e o intervalo de sprints. Uma iniciativa tem
um responsável por sprint, e pode trocar de responsável entre sprints.

Alocar em sprint que ainda não existe não derruba a operação: o que falta volta
listado, com o atalho para criar.

**7. Grade.** A iniciativa aparece no *Planejamento* **depois** de alocada — a
grade parte das alocações. Clicar na barra abre "Mover", "Estender até" e
"Remover"; o `+` que aparece ao passar o mouse numa célula vazia aloca ali. O
filtro fica na URL, então o link reproduz a tela.

**8. Alertas.** O sino conta os avisos abertos. O painel agrupa por sprint e
cada alerta leva para a tela onde ele se resolve. Nada disso bloqueia nada: são
avisos. O que for decisão consciente do time, silencie com o motivo — o
silenciamento sobrevive a mudanças nas iniciativas envolvidas, e o botão
"Reativar" desfaz.

**9. Nada a salvar.** Cada alteração reexporta o snapshot sozinho, cinco
segundos depois da última da sequência.

### Atalhos de teclado

`?` abre a lista, e o ícone de teclado na topbar também.

| Tecla | O que faz |
|---|---|
| `g` depois `1`–`5` | Planejamento, Backlog, Projetos, Time, Sprints |
| `/` | Foca a busca |
| `n` | A ação principal da tela |
| `?` | A lista de atalhos |
| `Esc` | Fecha o diálogo ou o painel aberto |

Nenhum deles dispara enquanto o foco está num campo de texto ou com um diálogo
aberto.

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

As dez fases da seção 13 do spec estão concluídas: domínio, use cases,
persistência, API, CLI e snapshot no backend; shell, planejamento, backlog,
projetos, time, sprints e painel de alertas no front.

Com `mise run dev:api` no ar, a documentação navegável da API fica em
<http://127.0.0.1:8000/docs> e o OpenAPI em `/api/v1/openapi.json`. Todos os
endpoints da seção 8 do spec existem.

Três pontos seguem abertos na seção 16 do spec, cada um com uma premissa em
vigor que o código segue. O mais visível é o `MEMBER_IDLE` sem teto: com o time
inteiro cadastrado, quase toda sprint futura tem alguém sem frente, e o painel
enche de itens informativos. Eles não entram no contador do sino, e o ícone da
coluna da grade só fica vermelho quando há aviso de verdade — mas o teto
continua sendo a decisão que resolve isso de fato.
