"""O backlog (`GET /planning/backlog`, §8).

Backlog é **por status** (§6.3): trabalho que em algum momento será executado,
não priorizado, não iniciado, e que não entra em nenhuma conta de capacidade.

Duas exclusões, as duas do spec:

- iniciativas de projeto com `is_capacity_reserve` — sustentação sob demanda não
  é fila de trabalho;
- `DEPRIORITIZED` — que não é backlog e vive no filtro da tela de projetos.
  Aqui isso sai de graça, porque o filtro é `status = BACKLOG`.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.dto.initiatives import InitiativeView
from app.application.dto.planning import (
    BacklogItemView,
    BacklogOrder,
    BacklogProjectView,
    BacklogQuery,
    BacklogSummaryView,
    BacklogView,
)
from app.domain.entities.initiative import Initiative
from app.domain.ports.repositories import InitiativeRepository, ProjectRepository
from app.domain.value_objects.initiative_status import InitiativeStatus


@dataclass(frozen=True)
class GetBacklog:
    initiatives: InitiativeRepository
    projects: ProjectRepository

    def execute(self, query: BacklogQuery | None = None) -> BacklogView:
        criteria = query or BacklogQuery()
        candidates = self.initiatives.list_all(statuses=(InitiativeStatus.BACKLOG,))
        projects = {
            project.id: project
            for project in self.projects.list_by_ids(
                {initiative.project_id for initiative in candidates}
            )
        }
        items = [
            initiative
            for initiative in candidates
            if initiative.project_id in projects
            and not projects[initiative.project_id].is_capacity_reserve
        ]
        ordered = _order(items, criteria)
        estimates = [
            initiative.estimated_sprints
            for initiative in ordered
            if initiative.estimated_sprints is not None
        ]
        return BacklogView(
            items=tuple(
                BacklogItemView(
                    initiative=InitiativeView.of(initiative),
                    project=BacklogProjectView.of(projects[initiative.project_id]),
                )
                for initiative in ordered
            ),
            summary=BacklogSummaryView(
                count=len(ordered),
                estimated_sprints_total=sum(estimates),
                items_without_estimate=len(ordered) - len(estimates),
            ),
        )


def _order(items: Sequence[Initiative], criteria: BacklogQuery) -> list[Initiative]:
    """`size` põe quem não tem estimativa **por último** em qualquer direção.

    Inverter a ordem não pode promover o desconhecido ao topo: "sem estimativa"
    não é "estimativa zero".
    """
    if criteria.order_by is BacklogOrder.SIZE:
        estimated = sorted(
            (item for item in items if item.estimated_sprints is not None),
            key=lambda item: (item.estimated_sprints or 0, item.name.casefold()),
            reverse=criteria.descending,
        )
        unknown = sorted(
            (item for item in items if item.estimated_sprints is None),
            key=lambda item: item.name.casefold(),
        )
        return [*estimated, *unknown]
    if criteria.order_by is BacklogOrder.ENTERED_AT:
        return sorted(
            items,
            key=lambda item: (item.entered_at, item.name.casefold()),
            reverse=criteria.descending,
        )
    return sorted(
        items,
        key=lambda item: (item.priority.rank, item.name.casefold()),
        reverse=criteria.descending,
    )
