"""Wiring dos use cases (§5).

Duas responsabilidades:

1. **A transação é da requisição.** O repositório faz `flush`, nunca `commit`
   (ver `persistence/session.py`); quem abre e fecha é este adapter. Uma
   requisição que termina bem faz `commit`; uma que levanta exceção — inclusive
   `DomainError`, que o handler traduz para 4xx — faz `rollback`. Meia
   operação gravada é pior que operação nenhuma.
2. **Montar o feixe de portas.** `Ports` tem exatamente os nomes de campo que
   os use cases declaram, e `use_case()` injeta por nome. É o mesmo desenho do
   `Fakes` da suíte de use case, e de propósito: a Fase 4 é a primeira vez que
   esse feixe é montado com dependência de verdade, e ter uma fábrica por use
   case seria trinta e cinco funções que dizem a mesma coisa.

A Fase 5 acrescentou a terceira: **agendar o export da RNF3**. A cada mutação
bem-sucedida, `schedule_snapshot_export` põe em `BackgroundTasks` um toque no
debounce de 5 segundos.

Duas propriedades do `BackgroundTasks` fazem a regra valer, e as duas custam
caro descobrir depois:

- **a tarefa só roda no caminho de sucesso.** Ela é registrada na resolução da
  dependência, mas quem a executa é a resposta do endpoint. Uma exceção — a
  `DomainError` que vira 4xx, um corpo inválido, um 500 — é respondida pelo
  handler de `errors.py`, e a resposta dele não carrega tarefa nenhuma. É
  assim que "mutação **bem-sucedida**" sai de graça, sem inspecionar status.
- **a tarefa roda antes do `commit` da requisição.** O teardown das
  dependências com `yield` acontece depois das tarefas de fundo, e é
  `provide_session` quem faz o `commit` no teardown. Por isso a tarefa não
  exporta nada: ela só **arma** o debounce, que dispara 5 segundos depois, numa
  sessão própria, quando a transação já fechou. Exportar aqui, na hora,
  gravaria o snapshot de antes da mutação que o disparou.

Quem fica de fora é o router de `/snapshots` (ver `main.py`): a importação
`replace` não dispara export automático (RNF3).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Annotated, Final, Self

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.persistence.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyInitiativeRepository,
    SqlAlchemyMemberRepository,
    SqlAlchemyMutedAlertRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySnapshotStore,
    SqlAlchemySprintRepository,
    SqlAlchemySquadMembershipRepository,
    SqlAlchemySquadRepository,
)
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from app.adapters.outbound.snapshot.debounce import (
    SnapshotDebouncer,
    TimerFactory,
    durable_timer,
)
from app.adapters.outbound.snapshot.reader import DirectorySnapshotReader
from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from app.adapters.outbound.system_clock import SystemClock
from app.application.use_cases.snapshots.export import ExportSnapshot
from app.config.settings import Settings
from app.domain.ports.clock import Clock

#: Os métodos que mudam dado. O `GET` não agenda export (RNF3).
MUTATING_METHODS: Final = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def provide_settings(request: Request) -> Settings:
    """As configurações **desta** aplicação, e não as do processo.

    `create_app(settings)` as guarda em `app.state`, e é de lá que elas vêm.
    Chamar `get_settings()` aqui faria a suíte de HTTP — que constrói um
    `Settings` explícito, com a pasta de snapshot do teste — ler o ambiente da
    máquina e escrever na pasta sincronizada de verdade.
    """
    config: Settings = request.app.state.settings
    return config


#: O que os endpoints e as outras dependências declaram.
SettingsDep = Annotated[Settings, Depends(provide_settings)]


def provide_session_factory(
    request: Request, settings: SettingsDep
) -> sessionmaker[Session]:
    """Engine e fábrica de sessões **desta** aplicação, criadas uma vez.

    A URL vem de `app.state.settings`, pelo mesmo motivo que `snapshot_dir` e
    `cors_origins` vêm: `create_app(settings)` tem que valer para todos os
    campos, e não para alguns. Lendo o ambiente aqui, o `database_url` passado
    à fábrica era silenciosamente ignorado — a única configuração do sistema
    com duas fontes de verdade.

    A memoização é em `app.state`, e não um `lru_cache` de módulo, pelo mesmo
    motivo de `provide_snapshot_debouncer`: duas aplicações no mesmo processo
    (a suíte cria uma por teste) não podem herdar a engine uma da outra.

    Nasce na primeira requisição, não no `create_app`: é o que mantém a
    promessa de que criar a aplicação não abre banco (ver `main.py`).
    """
    existing: sessionmaker[Session] | None = getattr(
        request.app.state, "session_factory", None
    )
    if existing is not None:
        return existing
    engine = make_engine(settings.database_url, echo=settings.sql_echo)
    factory = make_session_factory(engine)
    request.app.state.session_factory = factory
    return factory


def provide_clock() -> Clock:
    """O relógio é porta, e entra pelo adapter como qualquer outra.

    Ser uma dependência, e não um `SystemClock()` dentro de `Ports.build`, é o
    que deixa a suíte de HTTP congelar a data: `is_current` (RN12) e a janela
    default da grade (RN13) dependem de hoje, e um teste que muda de resultado
    conforme o dia não é teste.
    """
    return SystemClock()


def provide_session(
    factory: Annotated[sessionmaker[Session], Depends(provide_session_factory)],
) -> Iterator[Session]:
    """Uma transação por requisição."""
    with factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        session.commit()


@dataclass(frozen=True)
class Ports:
    """O feixe de portas da requisição.

    Todos os repositórios compartilham a **mesma** `Session`: é uma transação
    por requisição, não uma por repositório. Sem isso, o `flush` de um
    repositório não seria visto pela leitura seguinte de outro dentro do mesmo
    use case.
    """

    clock: Clock
    store: SqlAlchemySnapshotStore
    writer: DirectorySnapshotWriter
    reader: DirectorySnapshotReader
    projects: SqlAlchemyProjectRepository
    initiatives: SqlAlchemyInitiativeRepository
    members: SqlAlchemyMemberRepository
    squads: SqlAlchemySquadRepository
    memberships: SqlAlchemySquadMembershipRepository
    sprints: SqlAlchemySprintRepository
    allocations: SqlAlchemyAllocationRepository
    muted_alerts: SqlAlchemyMutedAlertRepository

    @classmethod
    def build(cls, *, session: Session, clock: Clock, snapshot_dir: Path) -> Self:
        return cls(
            clock=clock,
            store=SqlAlchemySnapshotStore(session),
            writer=DirectorySnapshotWriter(directory=snapshot_dir, clock=clock),
            reader=DirectorySnapshotReader(),
            projects=SqlAlchemyProjectRepository(session),
            initiatives=SqlAlchemyInitiativeRepository(session),
            members=SqlAlchemyMemberRepository(session),
            squads=SqlAlchemySquadRepository(session),
            memberships=SqlAlchemySquadMembershipRepository(session),
            sprints=SqlAlchemySprintRepository(session),
            allocations=SqlAlchemyAllocationRepository(session),
            muted_alerts=SqlAlchemyMutedAlertRepository(session),
        )

    def use_case[T](self, cls: type[T]) -> T:
        """Instancia o use case injetando as portas pelo nome do campo.

        Sem `hasattr`: todo campo do use case tem que existir no feixe, e a
        falta de um é `AttributeError` na hora, com o nome do campo na
        mensagem. Enquanto o `AlertService` era injetável, um campo com default
        podia sumir em silêncio — era a única peça do wiring que nenhum type
        checker cobria, e a que o `Ports` tipado com os `Protocol` do domínio
        agora fecha.
        """
        wanted = {item.name for item in fields(cls)}  # type: ignore[arg-type]
        return cls(**{name: getattr(self, name) for name in wanted})


def provide_ports(
    session: Annotated[Session, Depends(provide_session)],
    clock: Annotated[Clock, Depends(provide_clock)],
    settings: SettingsDep,
) -> Ports:
    return Ports.build(session=session, clock=clock, snapshot_dir=settings.snapshot_dir)


#: O que os routers declaram. Um parâmetro, e o wiring inteiro vem com ele.
PortsDep = Annotated[Ports, Depends(provide_ports)]


# --------------------------------------------------------------------------- #
# O export automático da RNF3
# --------------------------------------------------------------------------- #


def snapshot_exporter(
    *, factory: sessionmaker[Session], directory: Path, clock: Clock
) -> Callable[[], None]:
    """A função que o debounce chama, com sessão própria.

    Sessão própria porque ela roda numa thread, depois de a requisição ter
    fechado a dela. É leitura: não há `commit` a fazer.
    """

    def run() -> None:
        with factory() as session:
            ExportSnapshot(
                store=SqlAlchemySnapshotStore(session),
                writer=DirectorySnapshotWriter(directory=directory, clock=clock),
            ).execute()

    return run


def provide_timer_factory() -> TimerFactory:
    """O agendador do debounce, numa dependência só dele.

    É o único ponto do caminho da RNF3 que a suíte precisa trocar — e é por
    isso que ele existe separado. Antes, a suíte substituía
    `provide_snapshot_debouncer` inteiro por um lambda que devolvia sempre a
    mesma instância, e com isso a memoização em `app.state` — que **é** o
    mecanismo do coalescing em produção — não era exercitada por teste nenhum:
    trocá-la por um debouncer novo a cada requisição, ou seja, zero coalescing,
    deixaria a suíte verde do mesmo jeito.

    Com o timer fora, o resto do caminho roda de verdade em cada teste de HTTP.
    """
    return durable_timer


def provide_snapshot_debouncer(
    request: Request,
    factory: Annotated[sessionmaker[Session], Depends(provide_session_factory)],
    clock: Annotated[Clock, Depends(provide_clock)],
    settings: SettingsDep,
    timer_factory: Annotated[TimerFactory, Depends(provide_timer_factory)],
) -> SnapshotDebouncer:
    """Um debounce por aplicação, guardado em `app.state`.

    Precisa sobreviver à requisição — é disso que coalescer se trata —, e por
    isso não pode ser criado a cada chamada. Vive na aplicação, e não num
    global do módulo, para que duas aplicações no mesmo processo (a suíte cria
    uma por teste) não compartilhem o agendamento uma da outra.

    Nasce na primeira requisição, não no `create_app`: é o que mantém a
    promessa de que criar a aplicação não abre banco (ver `main.py`).
    """
    existing: SnapshotDebouncer | None = getattr(
        request.app.state, "snapshot_debouncer", None
    )
    if existing is not None:
        return existing
    debouncer = SnapshotDebouncer(
        snapshot_exporter(
            factory=factory, directory=settings.snapshot_dir, clock=clock
        ),
        timer_factory=timer_factory,
    )
    request.app.state.snapshot_debouncer = debouncer
    return debouncer


def schedule_snapshot_export(
    request: Request,
    tasks: BackgroundTasks,
    debouncer: Annotated[SnapshotDebouncer, Depends(provide_snapshot_debouncer)],
) -> None:
    """RNF3: a cada mutação bem-sucedida, um toque no debounce.

    `schedule()` não exporta nada — ele remarca o timer, e o export sai 5
    segundos depois da última mutação da sequência. Os dois motivos de a
    tarefa poder ser registrada aqui, antes de se saber o resultado da
    requisição, estão no topo do módulo.
    """
    if request.method in MUTATING_METHODS:
        tasks.add_task(debouncer.schedule)
