"""Substituir a composição de uma squad num intervalo (§8).

`PUT /squads/{id}/memberships` é substituição, não adição: a composição do
intervalo passa a ser exatamente `member_ids`. Lista vazia esvazia o intervalo
— e uma squad vazia com alocação é `EMPTY_SQUAD`, informativo, nunca bloqueio
(RN-S2).

Uma linha por (squad, membro, sprint), com unicidade `(squad_id, member_id,
sprint_id)` (§6.5): é isso que faz a Emilie no BNPL até a 19 e no CRM da 20 em
diante não ser conflito.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.squads import SetMembershipsInput, SprintCompositionView
from app.application.use_cases.squads.composition import (
    compose_by_sprint,
    resolve_sprint_range,
)
from app.domain.entities.squad_membership import SquadMembership
from app.domain.errors import MemberNotFound, SquadNotFound
from app.domain.ports.repositories import (
    MemberRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.value_objects.sprint_range import SprintRange


@dataclass(frozen=True)
class SetSquadMemberships:
    squads: SquadRepository
    memberships: SquadMembershipRepository
    members: MemberRepository
    sprints: SprintRepository

    def execute(
        self, squad_id: UUID, data: SetMembershipsInput
    ) -> tuple[SprintCompositionView, ...]:
        if self.squads.get(squad_id) is None:
            raise SquadNotFound(squad_id)
        member_ids = tuple(dict.fromkeys(data.member_ids))
        self._ensure_members_exist(member_ids)
        sprints = resolve_sprint_range(
            sprints=self.sprints,
            sprint_range=SprintRange(data.sprint_from, data.sprint_to),
        )
        sprint_ids = [sprint.id for sprint in sprints]
        self.memberships.delete(squad_id=squad_id, sprint_ids=sprint_ids)
        self.memberships.add_many(
            [
                SquadMembership.create(
                    squad_id=squad_id, member_id=member_id, sprint_id=sprint_id
                )
                for sprint_id in sprint_ids
                for member_id in member_ids
            ]
        )
        return compose_by_sprint(
            squad_id=squad_id,
            sprints=sprints,
            memberships=self.memberships,
            members=self.members,
        )

    def _ensure_members_exist(self, member_ids: tuple[UUID, ...]) -> None:
        """Existir é exigido; estar ativo não.

        O §6.4 diz que o inativo desaparece dos seletores, então a UI não
        oferece; e o §16 (premissa A3) diz que membership de inativo fica no
        dado como histórico. Recusar aqui seria inventar regra que o spec não
        pede.
        """
        found = {member.id for member in self.members.list_by_ids(member_ids)}
        for member_id in member_ids:
            if member_id not in found:
                raise MemberNotFound(member_id)
