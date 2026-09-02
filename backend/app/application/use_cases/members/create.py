"""Cadastrar membro (§8)."""

from dataclasses import dataclass

from app.application.dto.members import CreateMemberInput, MemberView
from app.domain.entities.member import Member
from app.domain.ports.repositories import MemberRepository


@dataclass(frozen=True)
class CreateMember:
    members: MemberRepository

    def execute(self, data: CreateMemberInput) -> MemberView:
        """Nome de membro não é único: homônimo no time é possível, e o §6.4
        não pede unicidade."""
        member = Member.create(
            name=data.name, short_name=data.short_name, role=data.role
        )
        self.members.add(member)
        return MemberView.of(member)
