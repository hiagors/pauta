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

As dez fases da seção 13 estão concluídas: **0** (scaffold), **1** (domínio
puro), **2** (use cases com repositórios fake), **3** (persistência em SQLite),
**4** (API HTTP), **5** (CLI + snapshot), **6** (shell do front), **7**
(planejamento e backlog), **8** (projetos, time, sprints e painel de alertas) e
**9** (acabamento).

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

## Projetos, time, sprints e alertas (Fase 8)

`Drawer` (`ui/Drawer.tsx`) é o mesmo `<dialog>` do `Modal`, preso à direita: a
armadilha de foco, o `Esc` e o `inert` vêm do navegador. O flex é `open:flex`, e
não `flex` na classe — `<dialog>` fechado é `display: none` pela folha do
navegador, e um `flex` fixo venceria essa regra: o painel apareceria aberto.

O sino chama `/alerts` com `include_muted=true`, uma vez. O contador filtra
`WARNING` não silenciado do mesmo dado (`warningCount`), e o painel precisa dos
silenciados **com** `mute_id` e `mute_reason` para oferecer "Reativar". Duas
chamadas dariam dois caches para a mesma janela.

O link de cada alerta aponta para a tela onde ele **se resolve**, não para onde
ele apareceu (`alertContext`): sobrecarga e ociosidade viram planejamento
filtrado naquela sprint; conflito e squad vazia viram a matriz do time. Por isso
`MEMBER_CONFLICT` aponta para uma das squads do `entity_refs`, e não para o
`subject_id`, que é o membro.

`PUT /squads/{id}/memberships` **substitui** a composição, então a lista vai
inteira — e sai do que está gravado (`memberIdsAfterToggle` sobre
`currentMemberIds`), nunca das caixas marcadas. A matriz só desenha membro
ativo (premissa A3 do §16); montar a lista pela tela apagaria em silêncio a
membership de quem foi inativado, que a premissa manda preservar.

A matriz grava sprint a sprint (`sprint_from == sprint_to`). O `PUT` de
intervalo exige que **todas** as sprints do intervalo existam (404, ao
contrário da RN5 da alocação), e uma célula é sempre uma sprint só.

A janela da matriz vem de uma chamada por sprint (`GET /squads?sprint_number=`),
cada uma trazendo todas as squads com a composição daquela sprint. É o que faz
a célula responder as duas perguntas do §10.3 — "está nesta squad?" e "em qual
outra já está?" — sem uma segunda consulta por membro.

Status **não** é campo de formulário no drawer de iniciativa: é botão, um por
transição que a tabela do §6.3 permite (`manualTransitions`). `BACKLOG ⇄
PLANNED` não está lá porque é automático (RN2). Um `<select>` com os seis
valores ofereceria caminhos cuja única resposta possível é 422.

Os `PATCH` montam só o que mudou (`projectPatch`, `initiativePatch`,
`memberPatch`, `squadPatch`). Mandar o formulário inteiro apagaria a distinção
do §8 entre campo ausente e campo nulo — `color: null` limpa a cor.

Sem nenhuma sprint, `GET /sprints/next/preview` é 404 por regra: não há o que
propor. O diálogo abre em branco com o número editável (a primeira sprint de um
time real raramente é a 1). Com proposta e datas intocadas quem cria é
`POST /sprints/next`, para o cálculo da RN10 não ser refeito no front.

`mutationFn` cujo `if` devolve tipos diferentes (`ProjectDetailOut` do `POST`
contra `ProjectOut` do `PATCH`) não compila. O retorno não é usado — a tela relê
pelo cache invalidado —, então a função é `async (): Promise<void>`.

`cors_origins` é campo de `Settings`, então dá para subir a API de verificação
em outra porta com `CORS_ORIGINS='["http://localhost:4322"]'` no comando,
junto de `DATABASE_URL` e `SNAPSHOT_DIR` apontando para um banco descartável.

## Acabamento (Fase 9)

Os atalhos moram no shell (`layout/Shortcuts.astro`), fora do React: valem em
qualquer rota, e uma ilha por página seria a mesma lógica montada cinco vezes.
O script lê as rotas da **própria** barra lateral (`nav a[href]`) em vez de
manter uma segunda lista — o sintoma de esquecer de sincronizar seria `g 3`
levando para a tela errada.

`n` dispara a ação principal da tela clicando no primeiro
`[data-primary-action]` da página. É a ponte entre o script do shell e as ilhas:
ele não precisa saber qual botão é nem em qual ilha ele está. Tela nova com ação
primária marca o botão e ganha o atalho de graça.

Nenhum atalho usa `[` ou `\`: no ABNT2 essas teclas exigem AltGr, e atalho que
só funciona em metade das máquinas não é atalho.

O guarda dos atalhos é `isTyping(target)` mais `document.querySelector('dialog[open]')`.
Sem o segundo, `g 3` navegaria com um drawer aberto e o formulário sumiria com o
que estava digitado.

O `alerts_by_sprint` da grade manda **tipo** sem severidade, então
`ALERT_TYPE_SEVERITY` (`lib/alerts.ts`) repete a tabela do §7.3 só para o ícone
da coluna. É a única cópia dessa tabela no front — em todo outro lugar quem
manda é o `severity` do próprio `AlertOut`. Sem ela o ícone sairia vermelho para
`MEMBER_IDLE`, que é informação: com o time inteiro, quase toda sprint futura
tem alguém sem frente (premissa A2 do §16), e o vermelho pararia de significar
alguma coisa.

A busca da topbar não é tela de resultado: é um `<form method="get">` para
`/projects`, que já filtra iniciativa por `?q=`. Ligá-la assim resolve o campo
permanentemente desabilitado sem inventar rota. Como toda iniciativa nasce com o
nome do projeto (RN-I1), procurar o nome do projeto também acha.

`public/favicon.svg` existe porque sem ele o navegador pedia `/favicon.ico` e
levava 404 em toda carga de página. O `P` é caminho, não `<text>`: o ícone é
gerado fora do documento e não pode depender da fonte carregada.

Verificação do critério de aceite: um roteiro de CDP planeja uma sprint inteira
do zero contra um banco recém-migrado — cria sprint, pessoa, squad, composição,
projeto, iniciativa, aloca pelo backlog e confere a grade e o painel. Ele mora
no scratchpad, não no repositório: depende de Chrome e de servidor no ar, o que
não é `mise run test`.

## Nomes nas fixtures e nos docs

Nenhum nome real de projeto, squad, iniciativa ou pessoa entra neste
repositório — nem em teste, nem em comentário, nem no `spec.md`. O vocabulário
neutro em vigor:

- projetos: **Aurora**, **Boreal**, **Plantão** (o de `is_capacity_reserve`);
- iniciativas: **Catálogo V1**, **Serviço de Envio**, **Portal Externo**,
  **API de Cobrança**;
- squads: **Alfa**, **Beta**, **Gama**, **Delta**;
- pessoas: **Ana**, **Carla**, **Bruno**, **Diana** (sobrenomes Martins e
  Ribeiro).

Trocar um nome quebra assertiva de ordenação alfabética e de busca por
substring, em lugares que não citam o nome: a ordem esperada em
`test_projects`, `test_grid`, `test_initiatives` e `test_planning_rules`, as
frases de alerta em `test_alert_service`, e os fragmentos de `?q=` em
`test_repository_contract`, que existem para exercitar o `pauta_casefold` e por
isso precisam de acento no meio da palavra.

O histórico do Git anterior a esta limpeza ainda tem os nomes antigos.
