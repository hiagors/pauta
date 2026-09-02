"""Tirar membros da composição num intervalo (`DELETE /squads/{id}/memberships`).

`member_ids` ausente remove todo mundo do intervalo; com a lista, remove só
quem está nela.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.squads import RemoveMembershipsInput, SprintCompositionView
from app.application.use_cases.squads.composition import (
    compose_by_sprint,
    resolve_sprint_range,
)
from app.domain.errors import SquadNotFound
from app.domain.ports.repositories import (
    MemberRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.value_objects.sprint_range import SprintRange


@dataclass(frozen=True)
class RemoveSquadMemberships:
    squads: SquadRepository
    memberships: SquadMembershipRepository
    members: MemberRepository
    sprints: SprintRepository

    def execute(
        self, squad_id: UUID, data: RemoveMembershipsInput
    ) -> tuple[SprintCompositionView, ...]:
        """Devolve a composição resultante, para a matriz não recarregar tudo."""
        if self.squads.get(squad_id) is None:
            raise SquadNotFound(squad_id)
        sprints = resolve_sprint_range(
            sprints=self.sprints,
            sprint_range=SprintRange(data.sprint_from, data.sprint_to),
        )
        member_ids: list[UUID] | None = (
            list(dict.fromkeys(data.member_ids))
            if data.member_ids is not None
            else None
        )
        self.memberships.delete(
            squad_id=squad_id,
            sprint_ids=[sprint.id for sprint in sprints],
            member_ids=member_ids,
        )
        return compose_by_sprint(
            squad_id=squad_id,
            sprints=sprints,
            memberships=self.memberships,
            members=self.members,
        )
