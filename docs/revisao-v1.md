# Revisão de código — v1

> Revisão do sistema inteiro contra [`spec.md`](spec.md) (revisão 2). O backend foi
> lido em 02/09/2026, no fim da Fase 5; o front, em 03/09/2026, depois da Fase 9 e
> antes de abrir os requisitos da v2.
>
> Cada achado tem um identificador estável (`A1`, `N2`, `F3`, …). Quando um fecha, a
> linha dele fica marcada na tabela do §1 e a seção correspondente sai do documento —
> o que resta aqui é o que continua aberto.
>
> Onde este documento e o `spec.md` divergirem, o `spec.md` vence.

## 0. Método e estado da árvore

Lidos por inteiro: `spec.md`, `backend/app/`, `backend/tests/` e `frontend/src/`.

Estado em 03/09/2026, depois de fechados os achados, verificado rodando:

| Comando | Resultado |
|---|---|
| `mise run test` | 710 pytest + 123 vitest, todos verdes |
| `mise run lint` | ruff, `ruff format --check`, `mypy --strict app` e `tsc --noEmit` limpos |

O escopo do `mypy` mudou nesta revisão: era `app/domain app/application`, e passou a
ser `app` inteiro. O motivo está no `A3`.

---

## 1. Índice dos achados

Severidade:

- **Desvio** — o código faz coisa diferente do que o spec escreve.
- **Risco** — não diverge, mas esconde regressão: uma quebra futura não apareceria.
- **Ruído** — morto, duplicado ou inconsistente. Não quebra nada hoje.

### Backend (lido em 02/09/2026)

| # | Achado | Severidade | Situação |
|---|---|---|---|
| `A1` | `Path` numa porta de domínio | Risco | **fechado** |
| `A2` | `get_session_factory` lê o ambiente, não `app.state` | Desvio | **fechado** |
| `A3` | `Ports` tipado com as classes concretas | Risco | **fechado** |
| `A4` | `use_case()` injeta por nome com `hasattr` | Risco | **fechado** |
| `N1` | `SQUAD_OVERLOADED` ignora squad inativa | Desvio | **fechado** |
| `N2` | A mensagem do RN8 não diz quem já está lá | Desvio | **fechado** |
| `N3` | `MEMBER_IDLE` conta reserva como trabalho | Desvio | **fechado** |
| `N4` | `alerts_by_sprint` exclui os silenciados | Interpretação | **fechado** |
| `C1` | Campos de resposta e de query fora do §8 | Desvio | **fechado** |
| `C2` | O teste de contrato cobre rota, não corpo | Risco | **fechado** |
| `C3` | A grade não devolve linha sem alocação na janela | Lacuna | **fechado** |
| `M1` | Oito símbolos mortos | Ruído | **fechado** |
| `M2` | `AlertService` como classe injetável que ninguém injeta | Ruído | **fechado** |
| `M3` | `runtime_checkable` e `pytest-asyncio` sem uso real | Ruído | **fechado** |
| `R1` | O timer do debounce era daemon, ao contrário do que o módulo promete | Desvio | **fechado** |
| `T1` | `test_every_repository_satisfies_its_port` não testa nada | Risco | **fechado** |
| `T2` | O teste de coalescing por HTTP não testa coalescing | Risco | **fechado** |
| `T3` | A memoização do debouncer nunca é exercitada | Risco | **fechado** |
| `T4` | Dois testes-fumaça remanescentes | Ruído | **fechado** |
| `V1` | Nomes de teste em português em `tests/domain/` | Ruído | **fechado** |

`R1` não estava na revisão original: apareceu ao escrever o teste do `A2`, e é o
único achado que o próprio conserto de outro achado produziu.

### Front (lido em 03/09/2026)

| # | Achado | Severidade | Situação |
|---|---|---|---|
| `F1` | Nenhuma das 15 ilhas tem teste | Risco | **aberto** |
| `F2` | `JSON.parse` sem guarda em `api.ts` | Risco | **fechado** |
| `F3` | Corrida na matriz de composição, na mesma sprint | Risco | **fechado** |
| `F4` | Invalidação de cache incompleta em duas mutações | Ruído | **fechado** |
| `F5` | `SquadComposition` sombreia o `window` global | Ruído | **fechado** |
| `F6` | Ordenação de sprint repetida no cliente | Ruído | **fechado** |

---

## 2. O que continua aberto

### `F1` — nenhuma das 15 ilhas tem teste

`frontend/tests/` são oito arquivos, e todos exercitam `src/lib/`: o cliente de API, a
geometria da grade, a matriz de composição, os formatadores, o estado na URL. Essa
parte é forte, e é de propósito que ela é grande — a lógica que erra em silêncio foi
extraída para funções puras justamente para caber num teste sem DOM.

O que sobra sem cobertura é o que as ilhas fazem com essas funções: qual estado
desenha qual bloco, se o `+` da célula vazia some numa linha `DONE` (RN7), se o botão
de confirmar fica desabilitado com o intervalo inválido, se o drawer fecha depois da
mutação. Uma ilha inteira quebrada passa `mise run test`.

**Por que está aberto e não fechado:** fechar pede dependência nova — `jsdom` como
ambiente do Vitest e uma testing library —, e nenhuma das duas está no §4.1. O §14 é
explícito: perguntar antes.

O §11 não pede teste de componente, então isto não é desvio do spec. É a diferença
entre o que a suíte promete (`mise run test` verde) e o que ela cobre.

---

## 3. O que foi conferido e está certo

Para o diagnóstico ser justo, e para estas partes não serem revisitadas sem motivo.

### Backend

- **§6.3, transições de status.** `recalculate_status` e `change_status` são dois
  métodos que não se contaminam, exatamente como o §6.3 manda. A tabela
  `MANUAL_TRANSITIONS` deixa `BACKLOG ⇄ PLANNED` de fora de propósito, e as transições
  **proibidas** são testadas uma a uma. `DEPRIORITIZED` aceita alocação e continua
  `DEPRIORITIZED` (RN7).
- **§7.3, `fingerprint`.** Ancorado só em `(tipo, sujeito, sprint)`. O cenário G do
  §13.1 — silenciar a Ana na 19 e depois alocar uma terceira frente à `Alfa` —
  passa, e é o erro da revisão 1 que não voltou.
- **RN5, alocação parcial.** Sprint inexistente não derruba a operação: o que existe é
  criado e o resto volta em `missing_sprint_numbers`.
- **RN12, `is_current`.** "Maior `start_date` que já passou", com teste da folga de
  calendário entre sprints e do caso "nenhuma sprint começou".
- **RNF4, roundtrip.** `export → import → export` byte a byte, contra SQLite de
  verdade com schema criado pelas migrations, mais um banco novo reconstruído do zero
  e comparado com `assert restored.dump() == bundle`.
- **`SnapshotStore` como terceira porta.** A leitura certa do §6.4, §6.5 e D13: abrir
  um `delete` em `MemberRepository`, `SquadRepository` e `SprintRepository` para servir
  à restauração desfaria a regra que a ausência do método protege.
- **`UNSET` no PATCH.** Campo ausente e campo nulo são coisas distintas nos quatro
  recursos, e o OpenAPI publica os campos sem `default` pelo motivo certo — o
  `openapi-typescript` trata propriedade com `default` como não-opcional.
- **RNF1 e RNF2.** `PRAGMA foreign_keys=ON` e `pauta_casefold` registrados por
  conexão, no listener de `connect`; schema dos testes criado rodando as migrations,
  nunca `metadata.create_all()`.
- **§8, o contrato.** Fechado nas duas direções por `tests/http/test_app.py`, em três
  níveis: as rotas, os campos de cada resposta (`RESPONSE_FIELDS`) e os filtros de
  query (`QUERY_PARAMETERS`).
- **§5, regra de dependência.** Os testes de varredura de import — domínio, aplicação,
  o guarda "a varredura realmente vê imports" e, desde o `A1`, o que proíbe stdlib de
  sistema de arquivos no domínio — são o desenho certo: incluem um teste contra o pior
  modo de falha, que é o scanner passar vazio.

### Front

- **Um `QueryClient` por página, não por ilha.** `getQueryClient()` é um singleton de
  módulo e as ilhas compartilham o bundle, então o sino da topbar e a tela abaixo dele
  leem o mesmo cache de `/alerts`. É o que faz `invalidateQueries` de uma ilha chegar
  na outra sem barramento nenhum.
- **`rangeLeftovers` e a ordem das duas chamadas.** Não existe endpoint de mover (§8):
  mover é `POST` no intervalo novo e `DELETE` na sobra, nessa ordem. Invertida, uma
  falha no meio deixaria a iniciativa sem alocação nenhuma. Está escrito no código, ao
  lado da chamada, e testado na unidade.
- **A grade é um `grid` CSS único.** A barra é um item que ocupa `span` colunas, e não
  um bloco posicionado por cima: o navegador resolve a largura, e nada sai do lugar
  quando a fonte muda de tamanho.
- **`formatDate` corta a string ISO.** `new Date('2026-08-31')` é UTC, e em UTC-3
  voltaria 30/08.
- **O estado colapsado da sidebar é um script `is:inline` no `<head>`.** Num
  `useEffect` a barra abriria em 240px e encolheria na frente do usuário a cada carga.
- **`ALERT_TYPE_SEVERITY` é a única cópia da tabela do §7.3 no front**, e existe só
  para o ícone da coluna da grade, que recebe tipo sem severidade. Em todo outro lugar
  quem manda é o `severity` do próprio `AlertOut`.
- **`memberIdsAfterToggle` sai do que está gravado, não das caixas marcadas.** É o que
  cumpre a RN-S3: a matriz desenha só quem está ativo, e montar a lista pela tela
  apagaria em silêncio a membership de quem foi inativado.
