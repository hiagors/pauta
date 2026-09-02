"""Portas de persistência.

Declaradas aqui, implementadas em `adapters/outbound/persistence/repositories/`
(Fase 3) e por fakes in-memory nos testes de use case (Fase 2). Nenhum use case
recebe `Session` ou modelo SQLAlchemy — só estas portas e DTOs.

Duas ausências são regra de negócio, não esquecimento:

- `MemberRepository` e `SquadRepository` não têm `delete` — o `DELETE` da API é
  soft delete, `is_active = false` (§6.4, §8);
- `SprintRepository` não tem `delete` — sprint nunca é excluída (D13).

Os filtros por sprint são por `sprint_id`, a chave estrangeira. Traduzir número
para id é trabalho do use case, que já precisa das `Sprint` para montar a grade.

A consulta filtrada se chama `list_all`, e não `list`, porque um método `list`
dentro do corpo da classe sombreia o builtin `list` e quebra as anotações
`list[Project]` dos métodos declarados depois dele.
"""

from collections.abc import Collection, Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


@runtime_checkable
class ProjectRepository(Protocol):
    def add(self, project: Project) -> None: ...

    def update(self, project: Project) -> None: ...

    def get(self, project_id: UUID) -> Project | None: ...

    def get_by_name(self, name: str) -> Project | None: ...

    def list_all(
        self, *, active: bool | None = None, query: str | None = None
    ) -> list[Project]: ...

    def list_by_ids(self, ids: Collection[UUID]) -> list[Project]: ...

    def delete(self, project_id: UUID) -> None: ...


@runtime_checkable
class InitiativeRepository(Protocol):
    def add(self, initiative: Initiative) -> None: ...

    def update(self, initiative: Initiative) -> None: ...

    def get(self, initiative_id: UUID) -> Initiative | None: ...

    def get_by_name(self, *, project_id: UUID, name: str) -> Initiative | None: ...

    def list_all(
        self,
        *,
        project_id: UUID | None = None,
        statuses: Collection[InitiativeStatus] | None = None,
        priorities: Collection[Priority] | None = None,
        layer: str | None = None,
        query: str | None = None,
    ) -> list[Initiative]: ...

    def list_by_ids(self, ids: Collection[UUID]) -> list[Initiative]: ...

    def count_by_project(self, project_id: UUID) -> int: ...

    def delete(self, initiative_id: UUID) -> None: ...


@runtime_checkable
class MemberRepository(Protocol):
    def add(self, member: Member) -> None: ...

    def update(self, member: Member) -> None: ...

    def get(self, member_id: UUID) -> Member | None: ...

    def list_all(self, *, active: bool | None = None) -> list[Member]: ...

    def list_by_ids(self, ids: Collection[UUID]) -> list[Member]: ...


@runtime_checkable
class SquadRepository(Protocol):
    def add(self, squad: Squad) -> None: ...

    def update(self, squad: Squad) -> None: ...

    def get(self, squad_id: UUID) -> Squad | None: ...

    def get_by_name(self, name: str) -> Squad | None: ...

    def list_all(self, *, active: bool | None = None) -> list[Squad]: ...

    def list_by_ids(self, ids: Collection[UUID]) -> list[Squad]: ...


@runtime_checkable
class SquadMembershipRepository(Protocol):
    def add_many(self, memberships: Sequence[SquadMembership]) -> None: ...

    def exists(self, *, squad_id: UUID, member_id: UUID, sprint_id: UUID) -> bool: ...

    def list_all(
        self,
        *,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
        sprint_ids: Collection[UUID] | None = None,
    ) -> list[SquadMembership]: ...

    def delete(
        self,
        *,
        squad_id: UUID,
        sprint_ids: Collection[UUID],
        member_ids: Collection[UUID] | None = None,
    ) -> int: ...


@runtime_checkable
class SprintRepository(Protocol):
    def add(self, sprint: Sprint) -> None: ...

    def get(self, sprint_id: UUID) -> Sprint | None: ...

    def get_by_number(self, number: int) -> Sprint | None: ...

    def list_all(
        self, *, number_from: int | None = None, number_to: int | None = None
    ) -> list[Sprint]:
        """Ordenado por `number` crescente."""
        ...

    def last(self) -> Sprint | None: ...


@runtime_checkable
class AllocationRepository(Protocol):
    def add_many(self, allocations: Sequence[Allocation]) -> None: ...

    def get(self, allocation_id: UUID) -> Allocation | None: ...

    def list_all(
        self,
        *,
        sprint_ids: Collection[UUID] | None = None,
        initiative_ids: Collection[UUID] | None = None,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
    ) -> list[Allocation]: ...

    def count_by_initiative(self, initiative_id: UUID) -> int: ...

    def delete(self, allocation_id: UUID) -> None: ...

    def delete_many(self, ids: Collection[UUID]) -> int: ...


@runtime_checkable
class MutedAlertRepository(Protocol):
    def add(self, mute: MutedAlert) -> None: ...

    def get(self, mute_id: UUID) -> MutedAlert | None: ...

    def get_by_fingerprint(self, fingerprint: str) -> MutedAlert | None: ...

    def list_all(self) -> list[MutedAlert]: ...

    def delete(self, mute_id: UUID) -> None: ...
