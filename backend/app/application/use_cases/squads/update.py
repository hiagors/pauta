"""Editar squad (`PATCH /squads/{id}`: nome, representante, `is_active`)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.common import is_set
from app.application.dto.squads import SquadView, UpdateSquadInput
from app.domain.errors import DuplicateName, InvalidRepresentative, SquadNotFound
from app.domain.ports.repositories import MemberRepository, SquadRepository


@dataclass(frozen=True)
class UpdateSquad:
    squads: SquadRepository
    members: MemberRepository

    def execute(self, squad_id: UUID, data: UpdateSquadInput) -> SquadView:
        """`representative_member_id: null` tira o representante (RN-S1)."""
        squad = self.squads.get(squad_id)
        if squad is None:
            raise SquadNotFound(squad_id)
        if is_set(data.name):
            squad.rename(data.name)
            other = self.squads.get_by_name(squad.name)
            if other is not None and other.id != squad.id:
                raise DuplicateName("uma squad", squad.name)
        if is_set(data.representative_member_id):
            self._ensure_representative(data.representative_member_id)
            squad.set_representative(data.representative_member_id)
        if is_set(data.is_active):
            squad.activate() if data.is_active else squad.deactivate()
        self.squads.update(squad)
        return SquadView.of(squad)

    def _ensure_representative(self, member_id: UUID | None) -> None:
        if member_id is None:
            return
        member = self.members.get(member_id)
        if member is None or not member.is_active:
            raise InvalidRepresentative(member_id)
