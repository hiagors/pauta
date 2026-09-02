"""Listar squads (§8, `?active=&sprint_number=`)."""

from dataclasses import dataclass

from app.application.dto.squads import SquadView
from app.application.use_cases.squads.composition import compose_by_sprint
from app.domain.errors import SprintNotFound
from app.domain.ports.repositories import (
    MemberRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)


@dataclass(frozen=True)
class ListSquads:
    squads: SquadRepository
    memberships: SquadMembershipRepository
    members: MemberRepository
    sprints: SprintRepository

    def execute(
        self, *, active: bool | None = None, sprint_number: int | None = None
    ) -> list[SquadView]:
        """Com `sprint_number`, cada squad vem com a composição daquela sprint."""
        found = sorted(
            self.squads.list_all(active=active),
            key=lambda squad: squad.name.casefold(),
        )
        if sprint_number is None:
            return [SquadView.of(squad) for squad in found]
        sprint = self.sprints.get_by_number(sprint_number)
        if sprint is None:
            raise SprintNotFound(number=sprint_number)
        views: list[SquadView] = []
        for squad in found:
            composition = compose_by_sprint(
                squad_id=squad.id,
                sprints=[sprint],
                memberships=self.memberships,
                members=self.members,
            )
            views.append(
                SquadView.of(
                    squad,
                    sprint_number=sprint_number,
                    members=composition[0].members,
                )
            )
        return views
