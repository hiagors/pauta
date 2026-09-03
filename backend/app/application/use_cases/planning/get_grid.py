"""A grade do Gantt (`GET /planning/grid`, §8).

Formato pensado para renderizar direto: linhas agrupadas por projeto, barras já
consolidadas pelo domínio e cor já resolvida. O front desenha barras, não
células.

A grade não parte só das alocações: iniciativa viva sem barra na janela também
vira linha, com `bars` vazio. É o que faz a célula vazia com o `+` do §10.3 ter
onde existir, e o que impede uma iniciativa em andamento que perdeu todas as
alocações de sumir da tela sem caminho de volta.
"""

from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.application.dto.planning import (
    GridAssigneeView,
    GridBarView,
    GridGroupView,
    GridInitiativeView,
    GridProjectView,
    GridQuery,
    GridRowView,
    GridSprintView,
    GridView,
)
from app.application.planning_view import (
    SprintWindow,
    load_mutes,
    load_quarter_window,
    load_snapshot,
    load_window,
)
from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
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
from app.domain.services.bar_consolidation import AllocationCell, consolidate_bars
from app.domain.services.planning_rules import PlanningSnapshot
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.initiative_status import InitiativeStatus

#: Quem ganha linha na grade mesmo sem barra na janela.
#:
#: `BACKLOG` fica fora porque o caminho dela é o botão "Alocar" do backlog
#: (§10.3), e mostrá-la aqui duplicaria a tela. `DONE` e `CANCELLED` ficam fora
#: porque não aceitam nova alocação (RN7): a célula com `+` só saberia devolver
#: 422.
_ROWLESS_STATUSES = (
    InitiativeStatus.PLANNED,
    InitiativeStatus.IN_PROGRESS,
    InitiativeStatus.DEPRIORITIZED,
)


@dataclass(frozen=True)
class GetGrid:
    sprints: SprintRepository
    allocations: AllocationRepository
    initiatives: InitiativeRepository
    projects: ProjectRepository
    squads: SquadRepository
    members: MemberRepository
    memberships: SquadMembershipRepository
    muted_alerts: MutedAlertRepository
    clock: Clock
    alert_service: AlertService = field(default_factory=AlertService)

    def execute(self, query: GridQuery | None = None) -> GridView:
        criteria = query or GridQuery()
        window = self._window(criteria)
        snapshot = load_snapshot(
            window=window,
            allocations=self.allocations,
            initiatives=self.initiatives,
            projects=self.projects,
            members=self.members,
            squads=self.squads,
            memberships=self.memberships,
        )
        cells = self.allocations.list_all(sprint_ids=window.ids)
        initiatives = {
            initiative.id: initiative
            for initiative in self.initiatives.list_by_ids(
                {cell.initiative_id for cell in cells}
            )
        }
        numbered = [
            (window.number_of(cell.sprint_id), cell)
            for cell in cells
            if cell.initiative_id in initiatives
        ]
        kept = [
            (number, cell)
            for number, cell in numbered
            if self._matches(
                criteria,
                snapshot=snapshot,
                sprint_number=number,
                initiative=initiatives[cell.initiative_id],
                squad_id=cell.squad_id,
                member_id=cell.member_id,
            )
        ]
        rowless = self._rowless(
            criteria, allocated={cell.initiative_id for _, cell in kept}
        )
        initiatives.update({initiative.id: initiative for initiative in rowless})
        return GridView(
            sprints=tuple(
                GridSprintView(
                    id=sprint.id,
                    number=sprint.number,
                    start_date=sprint.start_date,
                    end_date=sprint.end_date,
                    is_current=window.is_current(sprint),
                )
                for sprint in window.selected
            ),
            groups=self._groups(
                kept,
                initiatives,
                rowless=tuple(initiative.id for initiative in rowless),
            ),
            alerts_by_sprint=self._alerts_by_sprint(snapshot),
        )

    # ------------------------------------------------------------------ #

    def _window(self, criteria: GridQuery) -> SprintWindow:
        """RN13: sem intervalo explícito, o trimestre corrente."""
        if criteria.sprint_from is None and criteria.sprint_to is None:
            return load_quarter_window(sprints=self.sprints, clock=self.clock)
        return load_window(
            sprints=self.sprints,
            clock=self.clock,
            number_from=criteria.sprint_from,
            number_to=criteria.sprint_to,
        )

    def _matches(
        self,
        criteria: GridQuery,
        *,
        snapshot: PlanningSnapshot,
        sprint_number: int,
        initiative: Initiative,
        squad_id: UUID | None,
        member_id: UUID | None,
    ) -> bool:
        """O filtro `member_id` é a alocação **efetiva** do §6.8.

        Filtrar a grade por uma pessoa e ver só as linhas em que ela é a
        responsável direta esconderia justamente o trabalho que chega até ela
        pela squad — que é a forma normal de alocar frente grande.
        """
        if (
            criteria.project_id is not None
            and initiative.project_id != criteria.project_id
        ):
            return False
        if criteria.squad_id is not None and squad_id != criteria.squad_id:
            return False
        if criteria.member_id is not None:
            through_squad = squad_id is not None and squad_id in snapshot.squad_ids_of(
                criteria.member_id, sprint_number
            )
            if member_id != criteria.member_id and not through_squad:
                return False
        return True

    def _rowless(
        self, criteria: GridQuery, *, allocated: Collection[UUID]
    ) -> list[Initiative]:
        """Iniciativas que viram linha vazia (C3).

        Só quando não há filtro de responsável: pedir a grade de uma squad e
        receber linha vazia de iniciativa que ela não toca contradiz o filtro.
        O filtro de projeto, esse continua valendo — ele é sobre a iniciativa,
        não sobre quem a executa.
        """
        if criteria.squad_id is not None or criteria.member_id is not None:
            return []
        return [
            initiative
            for initiative in self.initiatives.list_all(
                project_id=criteria.project_id, statuses=_ROWLESS_STATUSES
            )
            if initiative.id not in allocated
        ]

    def _groups(
        self,
        kept: Sequence[tuple[int, Allocation]],
        initiatives: Mapping[UUID, Initiative],
        *,
        rowless: Sequence[UUID] = (),
    ) -> tuple[GridGroupView, ...]:
        """Agrupa por projeto, que é quem carrega a cor e a leitura vertical."""
        by_initiative: dict[UUID, list[AllocationCell]] = defaultdict(list)
        # Semear com lista vazia é o que faz `consolidate_bars` devolver `()` e
        # a linha existir sem barra nenhuma.
        for initiative_id in rowless:
            by_initiative[initiative_id] = []
        for number, cell in kept:
            by_initiative[cell.initiative_id].append(
                AllocationCell(
                    allocation_id=cell.id,
                    sprint_number=number,
                    assignee=cell.assignee,
                )
            )
        involved = [initiatives[key] for key in by_initiative]
        projects = {
            project.id: project
            for project in self.projects.list_by_ids(
                {initiative.project_id for initiative in involved}
            )
        }
        names = self._assignee_names(kept)
        rows: dict[UUID, list[GridRowView]] = defaultdict(list)
        for initiative in involved:
            rows[initiative.project_id].append(
                GridRowView(
                    initiative=GridInitiativeView(
                        id=initiative.id,
                        name=initiative.name,
                        layer=initiative.layer,
                        status=initiative.status,
                        priority=initiative.priority,
                    ),
                    bars=tuple(
                        GridBarView(
                            assignee=GridAssigneeView(
                                kind=bar.assignee.kind,
                                id=bar.assignee.id,
                                name=names[bar.assignee.id],
                            ),
                            from_sprint_number=bar.from_sprint_number,
                            to_sprint_number=bar.to_sprint_number,
                            allocation_ids=bar.allocation_ids,
                        )
                        for bar in consolidate_bars(by_initiative[initiative.id])
                    ),
                )
            )
        return tuple(
            GridGroupView(
                project=GridProjectView.of(projects[project_id]),
                rows=tuple(
                    sorted(
                        group,
                        key=lambda row: (
                            row.initiative.priority.rank,
                            row.initiative.name.casefold(),
                        ),
                    )
                ),
            )
            for project_id, group in sorted(
                rows.items(), key=lambda item: projects[item[0]].name.casefold()
            )
        )

    def _assignee_names(
        self, kept: Sequence[tuple[int, Allocation]]
    ) -> dict[UUID, str]:
        """Nome de squad e `short_name` de membro — o rótulo da barra é curto.

        Busca por id, e não pelos ativos: uma squad inativada continua sendo a
        responsável das sprints passadas, e a barra dela tem que ter nome.
        """
        squad_ids = {cell.squad_id for _, cell in kept if cell.squad_id is not None}
        member_ids = {cell.member_id for _, cell in kept if cell.member_id is not None}
        found = {squad.id: squad.name for squad in self.squads.list_by_ids(squad_ids)}
        found.update(
            {
                member.id: member.short_name
                for member in self.members.list_by_ids(member_ids)
            }
        )
        return found

    def _alerts_by_sprint(
        self, snapshot: PlanningSnapshot
    ) -> dict[int, tuple[AlertType, ...]]:
        """Os silenciados ficam fora.

        O ícone no cabeçalho da coluna é o resumo da sprint; se o silenciamento
        não o apagasse, silenciar não silenciaria nada (§7.3).
        """
        alerts = self.alert_service.evaluate(snapshot, load_mutes(self.muted_alerts))
        grouped: dict[int, list[AlertType]] = defaultdict(list)
        for alert in alerts:
            if alert.is_muted:
                continue
            grouped[alert.sprint_number].append(alert.type)
        return {
            number: tuple(dict.fromkeys(types))
            for number, types in sorted(grouped.items())
        }
