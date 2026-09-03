# Revisão de código — Fases 0 a 5

> Revisão do backend contra [`spec.md`](spec.md) (revisão 2), feita em 02/09/2026,
> no fim da Fase 5 e antes da Fase 6.
>
> Cada achado tem um identificador estável (`A1`, `N2`, …). Quando um é fechado, a
> linha dele fica marcada na tabela do §1 e a seção correspondente sai do documento —
> o que resta aqui é o que continua aberto.
>
> Onde este documento e o `spec.md` divergirem, o `spec.md` vence.

## 0. Método e estado da árvore

Lidos por inteiro: `spec.md` (1324 linhas), `backend/app/` (9.848 linhas) e
`backend/tests/` (10.005 linhas). O front não entrou: `frontend/src/` está vazio
até a Fase 6, e o único arquivo é o teste-fumaça do §13 Fase 0.

Estado no momento da revisão, verificado rodando:

| Comando | Resultado |
|---|---|
| `uv run pytest` | 671 testes, todos verdes |
| `uv run ruff check .` | limpo |
| `uv run ruff format --check .` | limpo |
| `uv run mypy --strict app/domain app/application` | limpo, 87 arquivos |
| `uv run mypy --strict app/adapters app/config` | **não faz parte da task `lint`** — 3 erros, ver `A3`/`T1` |

O último não é violação: o §11 diz "adapters podem ser menos rígidos". Está na
tabela porque é a premissa de que `T1` depende.

O que **não** está em revisão: o `frontend/`, as telas (§10.3), e qualquer coisa
das Fases 6 a 9.

---

## 1. Índice dos achados

Severidade:

- **Desvio** — o código faz coisa diferente do que o spec escreve.
- **Risco** — não diverge, mas esconde regressão: uma quebra futura não apareceria.
- **Ruído** — morto, duplicado ou inconsistente. Não quebra nada hoje.

| # | Achado | Severidade | Onde | Situação |
|---|---|---|---|---|
| `A1` | `Path` numa porta de domínio | Risco | `domain/ports/snapshot.py:56` | aberto |
| `A2` | `get_session_factory` lê o ambiente, não `app.state` | Desvio | `http/deps.py:73` | aberto |
| `A3` | `Ports` tipado com as classes concretas | Risco | `http/deps.py:127` | aberto |
| `A4` | `use_case()` injeta por nome com `hasattr` | Risco | `http/deps.py:166` | aberto |
| `N1` | `SQUAD_OVERLOADED` ignora squad inativa | Desvio | `alert_service.py:66` | **fechado** |
| `N2` | A mensagem do RN8 não diz quem já está lá | Desvio | `domain/errors.py:303` | **fechado** |
| `N3` | `MEMBER_IDLE` conta reserva como trabalho — 4º ponto aberto não declarado | Desvio | `alert_service.py:172` | **fechado** |
| `N4` | `alerts_by_sprint` exclui os silenciados | Interpretação | `get_grid.py:244` | **fechado** |
| `C1` | Campos de resposta e de query fora do §8 | Desvio | vários routers | **fechado** |
| `C2` | O teste de contrato cobre rota, não corpo | Risco | `tests/http/test_app.py` | **fechado** |
| `C3` | A grade não devolve linha sem alocação na janela | Lacuna | `get_grid.py:158` | **fechado** |
| `M1` | Oito símbolos mortos | Ruído | vários | aberto |
| `M2` | `AlertService` como classe injetável que ninguém injeta | Ruído | `alert_service.py:40` | aberto |
| `M3` | `runtime_checkable` e `pytest-asyncio` sem uso real | Ruído | `domain/ports/`, `pyproject.toml` | aberto |
| `T1` | `test_every_repository_satisfies_its_port` não testa nada | Risco | `test_repository_contract.py:51` | aberto |
| `T2` | O teste de coalescing por HTTP não testa coalescing | Risco | `tests/http/test_snapshots.py:191` | aberto |
| `T3` | A memoização do debouncer nunca é exercitada | Risco | `http/deps.py:214` | aberto |
| `T4` | Dois testes-fumaça remanescentes | Ruído | `tests/domain/test_smoke.py` | aberto |
| `V1` | Nomes de teste em português em `tests/domain/` | Ruído | `tests/domain/` | aberto |

---

## 2. Arquitetura hexagonal

### `A1` — `Path` numa porta de domínio

`backend/app/domain/ports/snapshot.py:56-69` declara:

```python
class SnapshotWriter(Protocol):
    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]: ...

class SnapshotReader(Protocol):
    def read(self, path: Path) -> SnapshotBundle: ...
```

`pathlib` é stdlib, então o teste de dependência do §5 passa e a regra **literal**
não é violada. O que entrou no domínio foi o **conceito** "sistema de arquivos": a
única implementação concebível dessas portas é um diretório local.

Ele propaga para fora: `application/dto/snapshots.py` carrega
`ExportSnapshotResultView.paths: tuple[Path, ...]` e `ImportSnapshotInput.path`, e
daí chega ao schema HTTP (`SnapshotExportOut.paths: list[Path]`).

A ponta HTTP está certa — o §8 pede explicitamente "→ caminhos gerados" na resposta
de `POST /snapshots/export`. O que está fora de lugar é a **porta**.

### `A2` — `get_session_factory` lê o ambiente, não `app.state.settings`

`backend/app/adapters/inbound/http/deps.py:86-95` documenta, com precisão, por que
uma dependência não pode chamar `get_settings()`:

> Chamar `get_settings()` aqui faria a suíte de HTTP — que constrói um `Settings`
> explícito, com a pasta de snapshot do teste — ler o ambiente da máquina e escrever
> na pasta sincronizada de verdade.

E `deps.py:72-84`, treze linhas acima, faz exatamente isso:

```python
@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """..."""                             # docstring elidido
    settings = get_settings()           # <- o ambiente do processo
    engine = make_engine(settings.database_url, echo=settings.sql_echo)
    return make_session_factory(engine)
```

Resultado: `create_app(Settings(database_url=X))` **ignora** `X`. O banco vem sempre
do `DATABASE_URL` do processo, enquanto `snapshot_dir` e `cors_origins` vêm de
`app.state`. Duas fontes de verdade para configuração, no mesmo módulo, uma delas
explicitamente condenada pelo docstring da outra.

Está invisível hoje por dois motivos que se somam:

1. `tests/http/conftest.py` sobrescreve `get_session_factory` com a fábrica de
   memória — o caminho de produção nunca roda na suíte;
2. `test_creating_the_application_touches_no_database` passa
   `database_url="sqlite+pysqlite:///nao/existe.sqlite"` de propósito, e passa
   **justamente porque ninguém lê esse campo**.

### `A3` — `Ports` tipado com as classes concretas

`deps.py:127-151` declara `projects: SqlAlchemyProjectRepository`, e não
`ProjectRepository`. Idem para os outros oito.

Isolado, não é violação: está no adapter, que pode conhecer as duas coisas. O que o
torna um risco é a soma com `T1` e com o escopo do `mypy` (§0): não existe, em lugar
nenhum do projeto, um ponto em que uma implementação seja atribuída a uma variável
tipada com o `Protocol`. É o único lugar onde a conformidade seria verificada
estaticamente, e ele não existe.

### `A4` — `use_case()` injeta por nome com `hasattr`

`deps.py:166-175`:

```python
def use_case[T](self, cls: type[T]) -> T:
    """..."""                             # docstring elidido
    wanted = {item.name for item in fields(cls)}  # type: ignore[arg-type]
    return cls(
        **{name: getattr(self, name) for name in wanted if hasattr(self, name)}
    )
```

Wiring reflexivo, com um `type: ignore`. O `if hasattr(...)` é o ponto: um campo que
o feixe não tem é silenciosamente omitido.

- Campo **obrigatório** ausente → `TypeError` na primeira requisição. Falha alto,
  aceitável.
- Campo **com default** ausente → silêncio. Hoje só `alert_service` tem default (ver
  `M2`), então o impacto prático é zero — mas é a única peça do wiring que nenhum
  type checker cobre, e a razão de ela ser aceitável é a mesma que `M2` propõe
  eliminar.

---

## 3. Código morto e abstração sem uso

### `M1` — Oito símbolos mortos

Nenhum tem caminho de produção. Vários têm teste próprio, o que os faz parecer vivos.

| Símbolo | Situação |
|---|---|
| `Sprint.overlaps` (`entities/sprint.py:59`) | só `tests/domain/test_sprint.py`. A checagem real de sobreposição é `validate_sprint_sequence`, que compara `start`/`end` direto |
| `Sprint.contains` (`sprint.py:56`) | só testes |
| `Sprint.duration_days` (`sprint.py:49`) | só testes |
| `SprintRange.__len__` e `__contains__` (`sprint_range.py:37-41`) | nem testes |
| `SprintRepository.last()` (`ports/repositories.py:148`) | porta + implementação SQLAlchemy + fake + teste de contrato. Zero uso: `propose_next_sprint` faz `max(sprints, key=number)` sobre a lista inteira |
| `SquadMembershipRepository.exists()` (`ports/repositories.py:115`) | idem — porta, duas implementações, um teste de contrato, nenhum use case |
| `ImmediateTimer` (`tests/snapshot/timers.py:19`) | o docstring do módulo explica para que ela serve, e nenhum teste a usa. Todos usam `ManualTimer` |
| `tests/domain/test_smoke.py` | ver `T4` |

Os dois métodos de porta (`last`, `exists`) merecem atenção separada: eles custam
quatro lugares cada (Protocol, SQLAlchemy, fake, contrato) e não servem a ninguém.

### `M2` — `AlertService` é uma classe injetável que ninguém injeta

`alert_service.py:40`:

```python
class AlertService:
    """Serviço de domínio sem estado. Instanciável para ficar injetável."""
```

Sem estado, um método público (`evaluate`), e **nada** em `app/` ou `tests/` passa uma
instância diferente. Ela entra como `field(default_factory=AlertService)` em quatro use
cases (`ListAlerts`, `AllocateRange`, `_Deallocation`, `GetGrid`), e são esses quatro
campos que obrigam o `hasattr` do `A4` a existir.

No mesmo módulo, `_build`, `_dedupe`, `_sorted` e `_join` já são funções livres. A
classe é a única parte que não é.

### `M3` — `runtime_checkable` e `pytest-asyncio` sem uso real

- **`runtime_checkable`** está nos 17 `Protocol` de `domain/ports/`. O único
  `isinstance` contra eles em todo o projeto é o teste do `T1` — que, como se vê lá,
  não verifica nada. Sem esse teste, o decorador é inerte.
- **`pytest-asyncio ~=1.4.0`** + `asyncio_mode = "strict"` no `pyproject.toml`: zero
  `async def` em `tests/`. Está no §4.1, então é dependência que o spec manda ter, mas
  hoje é peso morto.

### Não entram nesta lista

`domain/ports/task_suggester.py` e `ExternalRefModel` estão sem uso **porque o spec
manda** (§12 e §6.10, "sem endpoint, sem UI, sem uso na v1"). Estão corretos.

Uma observação sobre o primeiro, que não é sobre estar morto:
`task_suggester.py:15` importa `InitiativeRef` de `domain/services/planning_rules`.
Isso acopla a porta da v2 a um detalhe interno do modelo de leitura da v1 — o dia em
que `InitiativeRef` mudar de forma para servir à grade, a assinatura da porta muda
junto.

---

## 4. Testes que passam sem testar nada

### `T1` — `test_every_repository_satisfies_its_port`

`tests/persistence/test_repository_contract.py:51`, sob o cabeçalho
"O contrato estrutural":

```python
def test_every_repository_satisfies_its_port(repos: Repositories) -> None:
    assert isinstance(repos.store, SnapshotStore)
    assert isinstance(repos.projects, ProjectRepository)
    ...
```

`isinstance` contra `Protocol` `runtime_checkable` confere **só nome de atributo**,
nunca assinatura. Comprovado neste repositório, no interpretador do projeto:

```python
class Bogus:
    def add(self): ...
    def update(self): ...
    def get(self): ...
    def get_by_name(self): ...
    def list_all(self): ...
    def list_by_ids(self): ...
    def delete(self): ...

isinstance(Bogus(), ProjectRepository)   # -> True
```

Sete métodos com as assinaturas todas erradas passam.

Some com o escopo do `mypy` (§0): `mise run lint` roda `--strict` só em
`app/domain app/application`, e `A3` mostra que não há nenhum ponto onde uma
implementação seja atribuída a uma variável tipada com o `Protocol`. Portanto **nada,
em lugar nenhum, verifica que `SqlAlchemyProjectRepository` implementa
`ProjectRepository`.**

O que segura de verdade é o comportamento: os 36 testes de contrato rodando duas
vezes, contra os fakes e contra o SQLAlchemy. Essa parte é forte e faz o trabalho. O
teste estrutural é decoração — e é pior que ausente, porque parece cobrir o buraco.

### `T2` — O teste de coalescing por HTTP não testa coalescing

`tests/http/test_snapshots.py:191`:

```python
def test_a_sequence_of_mutations_collapses_into_one_export(api: Api) -> None:
    api.project("Aurora")
    api.project("Boreal")
    api.sprints(18, 19)

    api.flush_snapshot()

    text = (api.snapshot_dir / "projects.json").read_text(encoding="utf-8")
    assert "Aurora" in text
    assert "Boreal" in text
```

O nome promete coalescing. O corpo assere que o arquivo final tem os dois projetos —
o que é verdade tanto se o debounce coalescer quanto se cada mutação exportar na hora.
Não assere quantos timers nasceram (`api._snapshot_timers.created`) nem quantos
exports saíram.

O coalescing real está coberto, e bem, na unidade —
`tests/snapshot/test_debounce.py`, com
`[timer.cancelled for timer in timers.created] == [True, True, False]`. O teste de
HTTP duplica o nome sem duplicar a garantia.

### `T3` — A memoização do debouncer nunca é exercitada

`http/deps.py:214-238`, `provide_snapshot_debouncer`, guarda o debouncer em
`app.state` para que ele **sobreviva à requisição** — que é literalmente o mecanismo de
que o coalescing depende em produção:

> Precisa sobreviver à requisição — é disso que coalescer se trata —, e por isso não
> pode ser criado a cada chamada.

`tests/http/conftest.py:240` sobrescreve essa dependência:

```python
app.dependency_overrides[provide_snapshot_debouncer] = lambda: debouncer
```

O lambda devolve sempre a mesma instância. Se `provide_snapshot_debouncer` criasse um
debouncer novo a cada requisição — ou seja, **zero coalescing em produção** — a suíte
inteira continuaria verde, `T2` inclusive.

É a única peça da RNF3 sem cobertura, e é a que faz a regra valer.

### `T4` — Dois testes-fumaça remanescentes

- `backend/tests/domain/test_smoke.py` — assere que `app.domain.__name__ ==
  "app.domain"`. Cumpriu o papel do §13 Fase 0 (`pytest` sem nenhum teste sai com
  código 5 e a task falharia). Com 671 testes, é o único teste do backend que não
  testa nada.
- `frontend/tests/smoke.test.ts` — `expect(1 + 1).toBe(2)`. **Ainda necessário**:
  `frontend/src/` está vazio até a Fase 6. Fica registrado para sair junto com o
  primeiro teste de verdade do front.

---

## 5. Convenção

### `V1` — Nomes de teste em português em `tests/domain/`

O CLAUDE.md e o §8 são categóricos: "todo identificador de código (classe, função,
variável, tabela, coluna, rota) é em inglês". Nome de função de teste é identificador.

Contagem por suíte, de nomes com marcador de português
(`test_a_squad_nao_carrega_lista_de_membros`, `test_o_padrao_do_dado_real_tem_onze_dias`):

| Suíte | Nomes em português |
|---|---|
| `tests/domain/` | **144 de 170** |
| `tests/http/` | 10 de 140 |
| `tests/persistence/` | 4 de 62 |
| `tests/application/` | 3 de 134 |
| `tests/snapshot/` | 1 de 40 |
| `tests/cli/` | 0 de 9 |

Uma das duas metades está errada. Como a Fase 1 é a mais antiga, o mais provável é que
a convenção só tenha se firmado a partir da Fase 2 e ninguém tenha voltado.

---

## 6. O que foi conferido e está certo

Para o diagnóstico ser justo, e para estas partes não serem revisitadas sem motivo:

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
  e comparado com `assert restored.dump() == bundle`. O critério de aceite da Fase 5
  está cumprido de verdade.
- **`SnapshotStore` como terceira porta.** A leitura certa do §6.4, §6.5 e D13: abrir
  um `delete` em `MemberRepository`, `SquadRepository` e `SprintRepository` para servir
  à restauração desfaria a regra que a ausência do método protege.
- **`UNSET` no PATCH.** Campo ausente e campo nulo são coisas distintas nos quatro
  recursos, e o OpenAPI publica os campos sem `default` pelo motivo certo — o
  `openapi-typescript` trata propriedade com `default` como não-opcional.
- **RNF1 e RNF2.** `PRAGMA foreign_keys=ON` e `pauta_casefold` registrados por
  conexão, no listener de `connect`; schema dos testes criado rodando as migrations,
  nunca `metadata.create_all()`.
- **§8, a lista de rotas.** Fechada nas duas direções por `tests/http/test_app.py`:
  os 38 pares método/caminho do §8, `/snapshots` inclusive, nenhum a mais. Desde o
  fechamento do `C2`, os campos de cada resposta e os filtros de query são conferidos
  do mesmo jeito, também nas duas direções.
- **§5, regra de dependência.** Os três testes de varredura de import (domínio,
  aplicação, e o guarda "a varredura realmente vê imports") são o desenho certo:
  incluem um teste contra o pior modo de falha, que é o scanner passar vazio.

---

## 7. Ordem do que resta

O grupo de contrato — `N1` a `N4`, `C1` a `C3` — foi fechado primeiro, depois das dez
fases, porque o front já dependia dele e cada dia só encarecia. O que sobra:

1. **`T1`, `T3` e `A2`**, que são o mesmo problema visto de três ângulos: o caminho de
   produção do wiring não é exercitado nem verificado. `A3` e `A4` andam junto — os
   quatro se resolvem no mesmo arquivo.
2. **`T2`**, que é curto e independente.
3. **`M1`, `M2`, `M3`, `T4`, `V1` e `A1`**, o ruído. Nenhum quebra nada hoje.
