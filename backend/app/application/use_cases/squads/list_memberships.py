"""Ler a composição de uma squad num intervalo (`GET /squads/{id}/memberships`)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.squads import SprintCompositionView
from app.application.use_cases.squads.composition import (
    compose_by_sprint,
    resolve_sprint_range,
)
from app.domain.errors import SprintNotFound, SquadNotFound
from app.domain.ports.repositories import (
    MemberRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.value_objects.sprint_range import SprintRange


@dataclass(frozen=True)
class ListSquadMemberships:
    squads: SquadRepository
    memberships: SquadMembershipRepository
    members: MemberRepository
    sprints: SprintRepository

    def execute(
        self,
        squad_id: UUID,
        *,
        sprint_from: int | None = None,
        sprint_to: int | None = None,
    ) -> tuple[SprintCompositionView, ...]:
        """Sem intervalo, devolve todas as sprints cadastradas.

        É a matriz de composição inteira (`SquadMembershipMatrix`, §5), com as
        células vazias no lugar.
        """
        if self.squads.get(squad_id) is None:
            raise SquadNotFound(squad_id)
        everything = list(self.sprints.list_all())
        if sprint_from is None and sprint_to is None:
            sprints = everything
        else:
            numbers = [sprint.number for sprint in everything]
            if not numbers:
                raise SprintNotFound
            sprints = resolve_sprint_range(
                sprints=self.sprints,
                sprint_range=SprintRange(
                    sprint_from if sprint_from is not None else min(numbers),
                    sprint_to if sprint_to is not None else max(numbers),
                ),
            )
        return compose_by_sprint(
            squad_id=squad_id,
            sprints=sprints,
            memberships=self.memberships,
            members=self.members,
        )
