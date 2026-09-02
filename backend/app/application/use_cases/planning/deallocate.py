"""Desalocar: o intervalo inteiro ou uma célula só (RN6).

As duas operações terminam igual: recalcular o status da iniciativa (RN2) e
devolver o estado atual dos alertas das sprints tocadas — é o que a UI precisa
para atualizar a barra e o cabeçalho sem uma segunda chamada.

Perder todas as alocações **não** tira ninguém de `IN_PROGRESS`: quem começou
não volta para o backlog (§6.3). Parar é `DEPRIORITIZED`, à mão.
"""

from dataclasses import dataclass, field
from uuid import UUID

from app.application.dto.allocations import (
    AllocationCellView,
    DeallocateRangeInput,
    DeallocationResultView,
)
from app.application.planning_view import (
    SprintWindow,
    load_mutes,
    load_snapshot,
    load_window,
)
from app.domain.entities.initiative import Initiative
from app.domain.errors import AllocationNotFound, InitiativeNotFound
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
from app.domain.services.alert_service import AlertService
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.sprint_range import SprintRange


@dataclass(frozen=True)
class _Deallocation:
    """Parte comum das duas formas de desalocar."""

    initiatives: InitiativeRepository
    allocations: AllocationRepository
    sprints: SprintRepository
    projects: ProjectRepository
    squads: SquadRepository
    members: MemberRepository
    memberships: SquadMembershipRepository
    muted_alerts: MutedAlertRepository
    clock: Clock
    alert_service: AlertService = field(default_factory=AlertService)

    def _result(
        self,
        *,
        initiative: Initiative,
        window: SprintWindow,
        removed: tuple[AllocationCellView, ...],
    ) -> DeallocationResultView:
        snapshot = load_snapshot(
            window=window,
            allocations=self.allocations,
            initiatives=self.initiatives,
            projects=self.projects,
            members=self.members,
            squads=self.squads,
            memberships=self.memberships,
        )
        return DeallocationResultView(
            removed=removed,
            initiative_status=self._recalculate(initiative),
            alerts=tuple(
                self.alert_service.evaluate(snapshot, load_mutes(self.muted_alerts))
            ),
        )

    def _recalculate(self, initiative: Initiative) -> InitiativeStatus:
        before = initiative.status
        initiative.recalculate_status(
            self.allocations.count_by_initiative(initiative.id) > 0
        )
        if initiative.status is not before:
            self.initiatives.update(initiative)
        return initiative.status

    def _initiative(self, initiative_id: UUID) -> Initiative:
        initiative = self.initiatives.get(initiative_id)
        if initiative is None:
            raise InitiativeNotFound(initiative_id)
        return initiative


@dataclass(frozen=True)
class DeallocateRange(_Deallocation):
    """`DELETE /allocations` com o intervalo no corpo."""

    def execute(self, data: DeallocateRangeInput) -> DeallocationResultView:
        """Intervalo sem nenhuma alocação não é erro: é operação vazia."""
        sprint_range = SprintRange(data.from_sprint_number, data.to_sprint_number)
        initiative = self._initiative(data.initiative_id)
        window = load_window(
            sprints=self.sprints,
            clock=self.clock,
            number_from=sprint_range.from_number,
            number_to=sprint_range.to_number,
        )
        targets = self.allocations.list_all(
            sprint_ids=window.ids, initiative_ids=(initiative.id,)
        )
        removed = tuple(
            sorted(
                (
                    AllocationCellView(
                        id=cell.id, sprint_number=window.number_of(cell.sprint_id)
                    )
                    for cell in targets
                ),
                key=lambda cell: cell.sprint_number,
            )
        )
        if targets:
            self.allocations.delete_many([cell.id for cell in targets])
        return self._result(initiative=initiative, window=window, removed=removed)


@dataclass(frozen=True)
class DeallocateCell(_Deallocation):
    """`DELETE /allocations/{id}`: uma célula da grade."""

    def execute(self, allocation_id: UUID) -> DeallocationResultView:
        allocation = self.allocations.get(allocation_id)
        if allocation is None:
            raise AllocationNotFound(allocation_id)
        initiative = self._initiative(allocation.initiative_id)
        whole = load_window(sprints=self.sprints, clock=self.clock)
        number = whole.number_of(allocation.sprint_id)
        self.allocations.delete(allocation_id)
        return self._result(
            initiative=initiative,
            window=whole.narrowed(number_from=number, number_to=number),
            removed=(AllocationCellView(id=allocation.id, sprint_number=number),),
        )
