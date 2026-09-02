"""Apoio dos testes de use case.

Sem banco e sem mock: os fakes de `fakes.py` implementam as portas, e o
`FrozenClock` da suíte de domínio implementa a porta `Clock`. Nenhum use case
recebe outra coisa.

`World` monta o cenário escrevendo direto nos repositórios. Isso é de
propósito: o cenário é o **arranjo**, e arranjar via use case faria cada teste
depender de todos os outros para nada. Onde o use case de escrita é o que está
sob teste, o teste o chama.

`World` fala com o `Repositories` — o feixe de portas —, não com os fakes: é o
que permite `tests/persistence/` montar o mesmo cenário contra os repositórios
SQLAlchemy e rodar a mesma suíte de contrato (critério da Fase 3).
"""

import dataclasses
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol
from uuid import UUID

import pytest

from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import (
    AllocationRepository,
    InitiativeRepository,
    MemberRepository,
    MutedAlertRepository,
    ProjectRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.value_objects.assignee import Assignee
from app.domain.value_objects.color import Color
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.fakes import (
    FakeAllocationRepository,
    FakeInitiativeRepository,
    FakeMemberRepository,
    FakeMutedAlertRepository,
    FakeProjectRepository,
    FakeSprintRepository,
    FakeSquadMembershipRepository,
    FakeSquadRepository,
)
from tests.domain.conftest import FrozenClock, uid

#: 02/09/2026, a data das confirmações de D15-D17. Cai dentro da Sprint 18.
TODAY = date(2026, 9, 2)

#: A Sprint 18 começa na segunda 31/08/2026 (§6.6).
FIRST_SPRINT_START = date(2026, 8, 31)


class Repositories(Protocol):
    """O feixe de portas, sem dizer quem as implementa.

    Existe para que `World` sirva tanto aos fakes desta suíte quanto aos
    repositórios SQLAlchemy de `tests/persistence/`. Os nomes dos campos são os
    mesmos dos campos dos use cases — é o que permite `Fakes.use_case()`
    injetar por nome.
    """

    clock: Clock
    projects: ProjectRepository
    initiatives: InitiativeRepository
    members: MemberRepository
    squads: SquadRepository
    memberships: SquadMembershipRepository
    sprints: SprintRepository
    allocations: AllocationRepository
    muted_alerts: MutedAlertRepository


@dataclass
class Fakes:
    """O feixe de portas que a Fase 4 vai montar com dependências de verdade.

    Os nomes dos campos são os mesmos dos campos dos use cases — é o que
    permite `use_case()` injetar por nome, sem uma fábrica por caso.
    """

    clock: FrozenClock
    projects: FakeProjectRepository = field(default_factory=FakeProjectRepository)
    initiatives: FakeInitiativeRepository = field(
        default_factory=FakeInitiativeRepository
    )
    members: FakeMemberRepository = field(default_factory=FakeMemberRepository)
    squads: FakeSquadRepository = field(default_factory=FakeSquadRepository)
    memberships: FakeSquadMembershipRepository = field(
        default_factory=FakeSquadMembershipRepository
    )
    sprints: FakeSprintRepository = field(default_factory=FakeSprintRepository)
    allocations: FakeAllocationRepository = field(
        default_factory=FakeAllocationRepository
    )
    muted_alerts: FakeMutedAlertRepository = field(
        default_factory=FakeMutedAlertRepository
    )

    def use_case[T](self, cls: type[T]) -> T:
        """Instancia o use case injetando as portas pelo nome do campo.

        Campo que o feixe não tem — `alert_service`, que tem default — fica
        com o default do próprio use case.
        """
        wanted = {item.name for item in dataclasses.fields(cls)}
        return cls(
            **{name: getattr(self, name) for name in wanted if hasattr(self, name)}
        )


@dataclass
class World:
    """Construtores de cenário. Ids determinísticos, para o output ser legível."""

    repos: Repositories
    _seed: int = 0

    def _id(self) -> UUID:
        self._seed += 1
        return uid(self._seed)

    # -- tempo ---------------------------------------------------------- #

    def sprints(self, first: int = 18, last: int = 22) -> list[Sprint]:
        """Sprints contíguas de duas semanas, a partir de 31/08/2026."""
        created: list[Sprint] = []
        start = FIRST_SPRINT_START + timedelta(days=14 * (first - 18))
        for number in range(first, last + 1):
            sprint = Sprint.create(
                number=number,
                start_date=start,
                end_date=start + timedelta(days=11),
                id=uid(1000 + number),
            )
            self.repos.sprints.add(sprint)
            created.append(sprint)
            start += timedelta(days=14)
        return created

    def sprint(self, number: int) -> Sprint:
        found = self.repos.sprints.get_by_number(number)
        assert found is not None, f"Sprint {number} não foi criada no cenário"
        return found

    # -- estrutura ------------------------------------------------------ #

    def project(
        self, name: str, *, reserve: bool = False, color: str | None = None
    ) -> Project:
        project = Project.create(
            name=name,
            is_capacity_reserve=reserve,
            color=Color.parse(color),
            id=self._id(),
        )
        self.repos.projects.add(project)
        return project

    def initiative(
        self,
        project: Project,
        name: str,
        *,
        priority: Priority = Priority.MEDIUM,
        status: InitiativeStatus = InitiativeStatus.BACKLOG,
        estimated_sprints: int | None = None,
        layer: str | None = None,
    ) -> Initiative:
        initiative = Initiative(
            id=self._id(),
            project_id=project.id,
            name=name,
            entered_at=self.repos.clock.today(),
            layer=layer,
            priority=priority,
            estimated_sprints=estimated_sprints,
            status=status,
        )
        self.repos.initiatives.add(initiative)
        return initiative

    def member(self, name: str, *, active: bool = True) -> Member:
        member = Member.create(
            name=name,
            short_name=name.split()[0],
            id=self._id(),
        )
        if not active:
            member.deactivate()
        self.repos.members.add(member)
        return member

    def squad(self, name: str, *, active: bool = True) -> Squad:
        squad = Squad.create(name=name, id=self._id())
        if not active:
            squad.deactivate()
        self.repos.squads.add(squad)
        return squad

    # -- plano ---------------------------------------------------------- #

    def join(self, squad: Squad, member: Member, *sprint_numbers: int) -> None:
        """Coloca o membro na squad nas sprints informadas (§6.5)."""
        self.repos.memberships.add_many(
            [
                SquadMembership.create(
                    squad_id=squad.id,
                    member_id=member.id,
                    sprint_id=self.sprint(number).id,
                    id=self._id(),
                )
                for number in sprint_numbers
            ]
        )

    def allocate(
        self,
        initiative: Initiative,
        *sprint_numbers: int,
        squad: Squad | None = None,
        member: Member | None = None,
    ) -> list[Allocation]:
        assignee = Assignee.from_ids(
            squad_id=squad.id if squad is not None else None,
            member_id=member.id if member is not None else None,
        )
        created = [
            Allocation.create(
                initiative_id=initiative.id,
                sprint_id=self.sprint(number).id,
                assignee=assignee,
                id=self._id(),
            )
            for number in sprint_numbers
        ]
        self.repos.allocations.add_many(created)
        return created


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(TODAY)


@pytest.fixture
def fakes(clock: FrozenClock) -> Fakes:
    return Fakes(clock=clock)


@pytest.fixture
def world(fakes: Fakes) -> World:
    return World(repos=fakes)
