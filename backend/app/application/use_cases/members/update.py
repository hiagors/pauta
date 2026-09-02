"""Editar membro (`PATCH /members/{id}`)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.common import is_set
from app.application.dto.members import MemberView, UpdateMemberInput
from app.domain.errors import MemberNotFound
from app.domain.ports.repositories import MemberRepository


@dataclass(frozen=True)
class UpdateMember:
    members: MemberRepository

    def execute(self, member_id: UUID, data: UpdateMemberInput) -> MemberView:
        """`is_active: true` é o caminho de volta de quem foi inativado."""
        member = self.members.get(member_id)
        if member is None:
            raise MemberNotFound(member_id)
        if is_set(data.name):
            member.rename(data.name)
        if is_set(data.short_name):
            member.set_short_name(data.short_name)
        if is_set(data.role):
            member.set_role(data.role)
        if is_set(data.is_active):
            member.activate() if data.is_active else member.deactivate()
        self.members.update(member)
        return MemberView.of(member)
