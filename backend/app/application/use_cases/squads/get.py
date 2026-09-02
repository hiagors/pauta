"""Ler uma squad com a composição sprint por sprint (§8)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.squads import SquadDetailView, SquadView
from app.application.use_cases.squads.composition import compose_by_sprint
from app.domain.errors import SquadNotFound
from app.domain.ports.repositories import (
    MemberRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)


@dataclass(frozen=True)
class GetSquad:
    squads: SquadRepository
    memberships: SquadMembershipRepository
    members: MemberRepository
    sprints: SprintRepository

    def execute(self, squad_id: UUID) -> SquadDetailView:
        """Só as sprints em que a squad tem gente aparecem.

        A leitura de uma squad não é a matriz de edição: listar todas as
        sprints cadastradas vazias aqui seria ruído.
        """
        squad = self.squads.get(squad_id)
        if squad is None:
            raise SquadNotFound(squad_id)
        occupied = {
            link.sprint_id for link in self.memberships.list_all(squad_id=squad_id)
        }
        return SquadDetailView(
            squad=SquadView.of(squad),
            memberships=compose_by_sprint(
                squad_id=squad_id,
                sprints=[
                    sprint
                    for sprint in self.sprints.list_all()
                    if sprint.id in occupied
                ],
                memberships=self.memberships,
                members=self.members,
            ),
        )
