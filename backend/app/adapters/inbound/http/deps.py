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
"""

from collections.abc import Iterator
from dataclasses import dataclass, fields
from functools import lru_cache
from typing import Annotated, Self

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.persistence.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyInitiativeRepository,
    SqlAlchemyMemberRepository,
    SqlAlchemyMutedAlertRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySprintRepository,
    SqlAlchemySquadMembershipRepository,
    SqlAlchemySquadRepository,
)
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from app.adapters.outbound.system_clock import SystemClock
from app.config.settings import get_settings
from app.domain.ports.clock import Clock


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Engine e fábrica de sessões, uma vez por processo.

    É uma dependência, e não um global do módulo, para que ela seja
    substituível: a suíte de HTTP troca esta função por uma que devolve a
    fábrica do SQLite em memória, e nenhuma engine de arquivo é aberta como
    efeito colateral de importar `main.py`.
    """
    settings = get_settings()
    engine = make_engine(settings.database_url, echo=settings.sql_echo)
    return make_session_factory(engine)


def provide_clock() -> Clock:
    """O relógio é porta, e entra pelo adapter como qualquer outra.

    Ser uma dependência, e não um `SystemClock()` dentro de `Ports.build`, é o
    que deixa a suíte de HTTP congelar a data: `is_current` (RN12) e a janela
    default da grade (RN13) dependem de hoje, e um teste que muda de resultado
    conforme o dia não é teste.
    """
    return SystemClock()


def provide_session(
    factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
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
    projects: SqlAlchemyProjectRepository
    initiatives: SqlAlchemyInitiativeRepository
    members: SqlAlchemyMemberRepository
    squads: SqlAlchemySquadRepository
    memberships: SqlAlchemySquadMembershipRepository
    sprints: SqlAlchemySprintRepository
    allocations: SqlAlchemyAllocationRepository
    muted_alerts: SqlAlchemyMutedAlertRepository

    @classmethod
    def build(cls, *, session: Session, clock: Clock) -> Self:
        return cls(
            clock=clock,
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

        Campo que o feixe não tem — `alert_service`, que tem default — fica
        com o default do próprio use case.
        """
        wanted = {item.name for item in fields(cls)}  # type: ignore[arg-type]
        return cls(
            **{name: getattr(self, name) for name in wanted if hasattr(self, name)}
        )


def provide_ports(
    session: Annotated[Session, Depends(provide_session)],
    clock: Annotated[Clock, Depends(provide_clock)],
) -> Ports:
    return Ports.build(session=session, clock=clock)


#: O que os routers declaram. Um parâmetro, e o wiring inteiro vem com ele.
PortsDep = Annotated[Ports, Depends(provide_ports)]
