"""Listar alocações (`GET /allocations`, §8).

O filtro `member_id` aqui é **direto**: devolve as linhas cujo responsável é
aquele membro. A alocação efetiva do §6.8 — que inclui o que chega pelas squads
dele — é a leitura de capacidade, e quem faz essa leitura é a grade.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.allocations import AllocationFilter, AllocationView
from app.application.planning_view import initiative_ids_of_projects, load_window
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import (
    AllocationRepository,
    InitiativeRepository,
    SprintRepository,
)


@dataclass(frozen=True)
class ListAllocations:
    allocations: AllocationRepository
    initiatives: InitiativeRepository
    sprints: SprintRepository
    clock: Clock

    def execute(self, filters: AllocationFilter | None = None) -> list[AllocationView]:
        criteria = filters or AllocationFilter()
        window = load_window(
            sprints=self.sprints,
            clock=self.clock,
            number_from=criteria.sprint_from,
            number_to=criteria.sprint_to,
        )
        initiative_ids = self._initiative_ids(criteria)
        if initiative_ids is not None and not initiative_ids:
            return []
        cells = self.allocations.list_all(
            sprint_ids=window.ids,
            initiative_ids=initiative_ids,
            squad_id=criteria.squad_id,
            member_id=criteria.member_id,
        )
        return sorted(
            (
                AllocationView(
                    id=cell.id,
                    initiative_id=cell.initiative_id,
                    sprint_id=cell.sprint_id,
                    sprint_number=window.number_of(cell.sprint_id),
                    squad_id=cell.squad_id,
                    member_id=cell.member_id,
                )
                for cell in cells
            ),
            key=lambda view: (view.sprint_number, str(view.initiative_id)),
        )

    def _initiative_ids(self, criteria: AllocationFilter) -> set[UUID] | None:
        """`None` significa "sem filtro"; conjunto vazio, "nada bate"."""
        if criteria.project_id is None and criteria.initiative_id is None:
            return None
        selected: set[UUID] | None = None
        if criteria.project_id is not None:
            selected = set(
                initiative_ids_of_projects(
                    initiatives=self.initiatives, project_id=criteria.project_id
                )
            )
        if criteria.initiative_id is not None:
            wanted = {criteria.initiative_id}
            selected = wanted if selected is None else selected & wanted
        return selected
