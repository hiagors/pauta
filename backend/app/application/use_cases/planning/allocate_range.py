"""Alocar uma iniciativa a um responsável num intervalo de sprints (RN1).

O que o use case faz que o domínio não pode fazer: traduzir número de sprint
para id, checar que o responsável existe, gravar e recalcular o status. A
decisão célula por célula — criar, ignorar, reclamar ou reportar como faltante
— é `plan_allocation`, no domínio.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from app.application.dto.allocations import (
    AllocateRangeInput,
    AllocationCellView,
    AllocationResultView,
)
from app.application.planning_view import load_mutes, load_snapshot, load_window
from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.errors import InitiativeNotFound, MemberNotFound, SquadNotFound
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
from app.domain.services.planning_rules import plan_allocation
from app.domain.value_objects.assignee import Assignee
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.sprint_range import SprintRange


@dataclass(frozen=True)
class AllocateRange:
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

    def execute(self, data: AllocateRangeInput) -> AllocationResultView:
        """RN1, RN5, RN7 e RN8, nesta ordem.

        Sprint que não existe não derruba a operação (RN5): o que existe é
        criado e o que falta volta em `missing_sprint_numbers`, com a UI
        oferecendo "criar próxima sprint".
        """
        assignee = Assignee.from_ids(squad_id=data.squad_id, member_id=data.member_id)
        sprint_range = SprintRange(data.from_sprint_number, data.to_sprint_number)
        initiative = self.initiatives.get(data.initiative_id)
        if initiative is None:
            raise InitiativeNotFound(data.initiative_id)
        initiative.ensure_accepts_allocation()
        self._ensure_assignee_exists(assignee)

        window = load_window(
            sprints=self.sprints,
            clock=self.clock,
            number_from=sprint_range.from_number,
            number_to=sprint_range.to_number,
        )
        by_number = window.by_number
        occupants = {
            window.number_of(cell.sprint_id): cell
            for cell in self.allocations.list_all(
                sprint_ids=window.ids, initiative_ids=(initiative.id,)
            )
        }
        plan = plan_allocation(
            initiative_id=initiative.id,
            sprint_range=sprint_range,
            assignee=assignee,
            existing_sprint_numbers=tuple(by_number),
            occupied={number: cell.assignee for number, cell in occupants.items()},
            occupant_names=self._occupant_names(occupants.values()),
        )
        created = [
            Allocation.create(
                initiative_id=initiative.id,
                sprint_id=by_number[number].id,
                assignee=assignee,
            )
            for number in plan.to_create
        ]
        if created:
            self.allocations.add_many(created)

        snapshot = load_snapshot(
            window=window,
            allocations=self.allocations,
            initiatives=self.initiatives,
            projects=self.projects,
            members=self.members,
            squads=self.squads,
            memberships=self.memberships,
        )
        return AllocationResultView(
            created=tuple(
                AllocationCellView(id=allocation.id, sprint_number=number)
                for number, allocation in zip(plan.to_create, created, strict=True)
            ),
            already_existed=tuple(
                AllocationCellView(id=occupants[number].id, sprint_number=number)
                for number in plan.already_existing
            ),
            missing_sprint_numbers=plan.missing_sprint_numbers,
            initiative_status=self._recalculate(initiative),
            alerts=tuple(
                self.alert_service.evaluate(snapshot, load_mutes(self.muted_alerts))
            ),
        )

    def _occupant_names(self, cells: Iterable[Allocation]) -> dict[UUID, str]:
        """Nome de quem já ocupa cada célula, para a mensagem da RN8.

        Busca por id, e não pelos ativos: a squad que ocupa a célula pode ter
        sido desativada depois de alocada, e a frase continua tendo que dizer
        de quem se trata.
        """
        assignees = [cell.assignee for cell in cells]
        squad_ids = {a.id for a in assignees if a.is_squad}
        member_ids = {a.id for a in assignees if not a.is_squad}
        names = {squad.id: squad.name for squad in self.squads.list_by_ids(squad_ids)}
        names.update(
            {
                member.id: member.short_name
                for member in self.members.list_by_ids(member_ids)
            }
        )
        return names

    def _ensure_assignee_exists(self, assignee: Assignee) -> None:
        """Responsável fantasma é 404, não alocação órfã."""
        if assignee.is_squad and self.squads.get(assignee.id) is None:
            raise SquadNotFound(assignee.id)
        if assignee.is_member and self.members.get(assignee.id) is None:
            raise MemberNotFound(assignee.id)

    def _recalculate(self, initiative: Initiative) -> InitiativeStatus:
        """RN2: só BACKLOG ⇄ PLANNED. Grava apenas se o status mudou."""
        before = initiative.status
        initiative.recalculate_status(
            self.allocations.count_by_initiative(initiative.id) > 0
        )
        if initiative.status is not before:
            self.initiatives.update(initiative)
        return initiative.status
