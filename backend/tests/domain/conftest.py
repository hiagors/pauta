"""Apoio dos testes de domínio.

Sem mock e sem banco (§11). O único "fake" é o `FrozenClock`, que implementa a
porta `Clock` — e ele vive aqui, nos testes, nunca no domínio.
"""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from app.domain.entities.member import Member
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.services.planning_rules import (
    AllocationFact,
    InitiativeRef,
    MembershipFact,
)
from app.domain.value_objects.assignee import Assignee


class FrozenClock:
    """Implementação de `Clock` com data e hora fixas."""

    def __init__(self, today: date, now: datetime | None = None) -> None:
        self._today = today
        self._now = now or datetime(
            today.year, today.month, today.day, 12, 0, tzinfo=UTC
        )

    def today(self) -> date:
        return self._today

    def now(self) -> datetime:
        return self._now


def uid(seed: int) -> UUID:
    """UUID determinístico e legível no output de teste."""
    return UUID(int=seed)


@pytest.fixture
def clock() -> FrozenClock:
    """02/09/2026 — a data das confirmações de D15-D17."""
    return FrozenClock(date(2026, 9, 2))


def make_sprint(number: int, start: date, *, length_days: int = 11) -> Sprint:
    from datetime import timedelta

    return Sprint.create(
        number=number,
        start_date=start,
        end_date=start + timedelta(days=length_days),
        id=uid(1000 + number),
    )


def sprint_18_to_22() -> list[Sprint]:
    """As sprints do dado real: a 18 começa na segunda 31/08/2026."""
    from datetime import timedelta

    sprints: list[Sprint] = []
    start = date(2026, 8, 31)
    for number in range(18, 23):
        sprints.append(make_sprint(number, start))
        start = start + timedelta(days=14)
    return sprints


def make_project(seed: int, name: str, *, reserve: bool = False) -> Project:
    return Project.create(name=name, is_capacity_reserve=reserve, id=uid(seed))


def make_member(seed: int, name: str, *, active: bool = True) -> Member:
    member = Member.create(name=name, short_name=name.split()[0], id=uid(seed))
    if not active:
        member.deactivate()
    return member


def make_squad(seed: int, name: str) -> Squad:
    return Squad.create(name=name, id=uid(seed))


def make_ref(
    seed: int,
    name: str,
    *,
    project_seed: int,
    project_name: str,
    reserve: bool = False,
) -> InitiativeRef:
    return InitiativeRef(
        id=uid(seed),
        name=name,
        project_id=uid(project_seed),
        project_name=project_name,
        is_capacity_reserve=reserve,
    )


def squad_alloc(
    sprint_number: int, initiative: InitiativeRef, squad_id: UUID
) -> AllocationFact:
    return AllocationFact(
        sprint_number=sprint_number,
        initiative=initiative,
        assignee=Assignee.for_squad(squad_id),
    )


def member_alloc(
    sprint_number: int, initiative: InitiativeRef, member_id: UUID
) -> AllocationFact:
    return AllocationFact(
        sprint_number=sprint_number,
        initiative=initiative,
        assignee=Assignee.for_member(member_id),
    )


def membership(sprint_number: int, squad_id: UUID, member_id: UUID) -> MembershipFact:
    return MembershipFact(
        sprint_number=sprint_number, squad_id=squad_id, member_id=member_id
    )
