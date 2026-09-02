"""Criar squad (§8)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.squads import CreateSquadInput, SquadView
from app.domain.entities.squad import Squad
from app.domain.errors import DuplicateName, InvalidRepresentative
from app.domain.ports.repositories import MemberRepository, SquadRepository


@dataclass(frozen=True)
class CreateSquad:
    squads: SquadRepository
    members: MemberRepository

    def execute(self, data: CreateSquadInput) -> SquadView:
        """RN-S1: o representante só precisa ser um membro existente e ativo.

        **Não** é validado contra a composição da squad: no momento da criação
        a squad não tem membership nenhuma, e o representante é uma ponte, não
        necessariamente quem executa.
        """
        squad = Squad.create(
            name=data.name, representative_member_id=data.representative_member_id
        )
        if self.squads.get_by_name(squad.name) is not None:
            raise DuplicateName("uma squad", squad.name)
        self._ensure_representative(squad.representative_member_id)
        self.squads.add(squad)
        return SquadView.of(squad)

    def _ensure_representative(self, member_id: UUID | None) -> None:
        if member_id is None:
            return
        member = self.members.get(member_id)
        if member is None or not member.is_active:
            raise InvalidRepresentative(member_id)
