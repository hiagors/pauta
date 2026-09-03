"""Repositórios fake in-memory, implementando as portas do §5.

São a razão de a Fase 2 vir antes de qualquer linha de SQLAlchemy: se um use
case precisa de banco para ser testado, a arquitetura está errada.

Duas escolhas que valem explicação:

- **Cópia na entrada e na saída.** `get` devolve uma cópia, e `add`/`update`
  guardam outra. Um fake que guardasse a referência deixaria a mutação do use
  case vazar para o "banco" sozinha, e um `update()` esquecido passaria no
  teste e quebraria na Fase 3.
- **Coleção vazia filtra tudo.** `sprint_ids=None` significa "sem filtro";
  `sprint_ids=()` significa "nenhuma sprint", e devolve lista vazia. É a
  semântica que o `WHERE ... IN ()` do adapter precisa ter, e a que os use
  cases assumem quando a janela de sprints está vazia.
"""

from collections.abc import Collection, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.ports.snapshot import SnapshotBundle
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


def _matches(text: str, query: str | None) -> bool:
    """Busca do `?q=`: pedaço do nome, sem diferenciar maiúscula."""
    return query is None or query.strip().casefold() in text.casefold()


def _selected(value: UUID, ids: Collection[UUID] | None) -> bool:
    return ids is None or value in ids


@dataclass
class FakeProjectRepository:
    rows: dict[UUID, Project] = field(default_factory=dict)

    def add(self, project: Project) -> None:
        self.rows[project.id] = deepcopy(project)

    def update(self, project: Project) -> None:
        self.rows[project.id] = deepcopy(project)

    def get(self, project_id: UUID) -> Project | None:
        return deepcopy(self.rows.get(project_id))

    def get_by_name(self, name: str) -> Project | None:
        for project in self.rows.values():
            if project.name == name:
                return deepcopy(project)
        return None

    def list_all(
        self, *, active: bool | None = None, query: str | None = None
    ) -> list[Project]:
        return [
            deepcopy(project)
            for project in self.rows.values()
            if (active is None or project.is_active is active)
            and _matches(project.name, query)
        ]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Project]:
        return [deepcopy(self.rows[key]) for key in ids if key in self.rows]

    def delete(self, project_id: UUID) -> None:
        self.rows.pop(project_id, None)


@dataclass
class FakeInitiativeRepository:
    rows: dict[UUID, Initiative] = field(default_factory=dict)

    def add(self, initiative: Initiative) -> None:
        self.rows[initiative.id] = deepcopy(initiative)

    def update(self, initiative: Initiative) -> None:
        self.rows[initiative.id] = deepcopy(initiative)

    def get(self, initiative_id: UUID) -> Initiative | None:
        return deepcopy(self.rows.get(initiative_id))

    def get_by_name(self, *, project_id: UUID, name: str) -> Initiative | None:
        for initiative in self.rows.values():
            if initiative.project_id == project_id and initiative.name == name:
                return deepcopy(initiative)
        return None

    def list_all(
        self,
        *,
        project_id: UUID | None = None,
        statuses: Collection[InitiativeStatus] | None = None,
        priorities: Collection[Priority] | None = None,
        layer: str | None = None,
        query: str | None = None,
    ) -> list[Initiative]:
        return [
            deepcopy(initiative)
            for initiative in self.rows.values()
            if (project_id is None or initiative.project_id == project_id)
            and (statuses is None or initiative.status in statuses)
            and (priorities is None or initiative.priority in priorities)
            and (layer is None or initiative.layer == layer)
            and _matches(initiative.name, query)
        ]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Initiative]:
        return [deepcopy(self.rows[key]) for key in ids if key in self.rows]

    def count_by_project(self, project_id: UUID) -> int:
        return sum(
            1
            for initiative in self.rows.values()
            if initiative.project_id == project_id
        )

    def delete(self, initiative_id: UUID) -> None:
        self.rows.pop(initiative_id, None)


@dataclass
class FakeMemberRepository:
    rows: dict[UUID, Member] = field(default_factory=dict)

    def add(self, member: Member) -> None:
        self.rows[member.id] = deepcopy(member)

    def update(self, member: Member) -> None:
        self.rows[member.id] = deepcopy(member)

    def get(self, member_id: UUID) -> Member | None:
        return deepcopy(self.rows.get(member_id))

    def list_all(self, *, active: bool | None = None) -> list[Member]:
        return [
            deepcopy(member)
            for member in self.rows.values()
            if active is None or member.is_active is active
        ]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Member]:
        return [deepcopy(self.rows[key]) for key in ids if key in self.rows]


@dataclass
class FakeSquadRepository:
    rows: dict[UUID, Squad] = field(default_factory=dict)

    def add(self, squad: Squad) -> None:
        self.rows[squad.id] = deepcopy(squad)

    def update(self, squad: Squad) -> None:
        self.rows[squad.id] = deepcopy(squad)

    def get(self, squad_id: UUID) -> Squad | None:
        return deepcopy(self.rows.get(squad_id))

    def get_by_name(self, name: str) -> Squad | None:
        for squad in self.rows.values():
            if squad.name == name:
                return deepcopy(squad)
        return None

    def list_all(self, *, active: bool | None = None) -> list[Squad]:
        return [
            deepcopy(squad)
            for squad in self.rows.values()
            if active is None or squad.is_active is active
        ]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Squad]:
        return [deepcopy(self.rows[key]) for key in ids if key in self.rows]


@dataclass
class FakeSquadMembershipRepository:
    rows: dict[UUID, SquadMembership] = field(default_factory=dict)

    def add_many(self, memberships: Sequence[SquadMembership]) -> None:
        for membership in memberships:
            self.rows[membership.id] = membership

    def list_all(
        self,
        *,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
        sprint_ids: Collection[UUID] | None = None,
    ) -> list[SquadMembership]:
        return [
            row
            for row in self.rows.values()
            if (squad_id is None or row.squad_id == squad_id)
            and (member_id is None or row.member_id == member_id)
            and _selected(row.sprint_id, sprint_ids)
        ]

    def delete(
        self,
        *,
        squad_id: UUID,
        sprint_ids: Collection[UUID],
        member_ids: Collection[UUID] | None = None,
    ) -> int:
        doomed = [
            row.id
            for row in self.rows.values()
            if row.squad_id == squad_id
            and row.sprint_id in sprint_ids
            and (member_ids is None or row.member_id in member_ids)
        ]
        for key in doomed:
            del self.rows[key]
        return len(doomed)


@dataclass
class FakeSprintRepository:
    """Sem `delete`: sprint nunca é excluída (D13)."""

    rows: dict[UUID, Sprint] = field(default_factory=dict)

    def add(self, sprint: Sprint) -> None:
        self.rows[sprint.id] = deepcopy(sprint)

    def get(self, sprint_id: UUID) -> Sprint | None:
        return deepcopy(self.rows.get(sprint_id))

    def get_by_number(self, number: int) -> Sprint | None:
        for sprint in self.rows.values():
            if sprint.number == number:
                return deepcopy(sprint)
        return None

    def list_all(
        self, *, number_from: int | None = None, number_to: int | None = None
    ) -> list[Sprint]:
        return sorted(
            (
                deepcopy(sprint)
                for sprint in self.rows.values()
                if (number_from is None or sprint.number >= number_from)
                and (number_to is None or sprint.number <= number_to)
            ),
            key=lambda sprint: sprint.number,
        )


@dataclass
class FakeAllocationRepository:
    rows: dict[UUID, Allocation] = field(default_factory=dict)

    def add_many(self, allocations: Sequence[Allocation]) -> None:
        for allocation in allocations:
            self.rows[allocation.id] = allocation

    def get(self, allocation_id: UUID) -> Allocation | None:
        return self.rows.get(allocation_id)

    def list_all(
        self,
        *,
        sprint_ids: Collection[UUID] | None = None,
        initiative_ids: Collection[UUID] | None = None,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
    ) -> list[Allocation]:
        return [
            row
            for row in self.rows.values()
            if _selected(row.sprint_id, sprint_ids)
            and _selected(row.initiative_id, initiative_ids)
            and (squad_id is None or row.squad_id == squad_id)
            and (member_id is None or row.member_id == member_id)
        ]

    def count_by_initiative(self, initiative_id: UUID) -> int:
        return sum(
            1 for row in self.rows.values() if row.initiative_id == initiative_id
        )

    def delete(self, allocation_id: UUID) -> None:
        self.rows.pop(allocation_id, None)

    def delete_many(self, ids: Collection[UUID]) -> int:
        removed = 0
        for key in list(ids):
            if self.rows.pop(key, None) is not None:
                removed += 1
        return removed


@dataclass
class FakeMutedAlertRepository:
    rows: dict[UUID, MutedAlert] = field(default_factory=dict)

    def add(self, mute: MutedAlert) -> None:
        self.rows[mute.id] = mute

    def get(self, mute_id: UUID) -> MutedAlert | None:
        return self.rows.get(mute_id)

    def get_by_fingerprint(self, fingerprint: str) -> MutedAlert | None:
        for mute in self.rows.values():
            if mute.fingerprint == fingerprint:
                return mute
        return None

    def list_all(self) -> list[MutedAlert]:
        return list(self.rows.values())

    def delete(self, mute_id: UUID) -> None:
        self.rows.pop(mute_id, None)


@dataclass
class FakeSnapshotStore:
    """`SnapshotStore` sobre os outros fakes (§9).

    Não guarda dado próprio: `dump` lê as mesmas linhas que os repositórios
    veem e `replace` troca essas linhas. Um store com armazenamento paralelo
    passaria a suíte de contrato e mentiria no teste de use case, onde o export
    tem de ver o que o cenário escreveu pelos repositórios.
    """

    projects: FakeProjectRepository
    initiatives: FakeInitiativeRepository
    members: FakeMemberRepository
    squads: FakeSquadRepository
    memberships: FakeSquadMembershipRepository
    sprints: FakeSprintRepository
    allocations: FakeAllocationRepository
    muted_alerts: FakeMutedAlertRepository

    def dump(self) -> SnapshotBundle:
        return SnapshotBundle(
            projects=_by_id(self.projects.rows),
            initiatives=_by_id(self.initiatives.rows),
            members=_by_id(self.members.rows),
            squads=_by_id(self.squads.rows),
            squad_memberships=_by_id(self.memberships.rows),
            sprints=_by_id(self.sprints.rows),
            allocations=_by_id(self.allocations.rows),
            muted_alerts=_by_id(self.muted_alerts.rows),
        )

    def replace(self, bundle: SnapshotBundle) -> None:
        for rows, entities in (
            (self.projects.rows, bundle.projects),
            (self.initiatives.rows, bundle.initiatives),
            (self.members.rows, bundle.members),
            (self.squads.rows, bundle.squads),
            (self.memberships.rows, bundle.squad_memberships),
            (self.sprints.rows, bundle.sprints),
            (self.allocations.rows, bundle.allocations),
            (self.muted_alerts.rows, bundle.muted_alerts),
        ):
            rows.clear()
            for entity in entities:
                rows[entity.id] = deepcopy(entity)


def _by_id[E](rows: dict[UUID, E]) -> tuple[E, ...]:
    """Ordenado por `id`, como o `dump` do adapter (§9)."""
    return tuple(
        deepcopy(row) for row in sorted(rows.values(), key=lambda row: str(row.id))
    )
