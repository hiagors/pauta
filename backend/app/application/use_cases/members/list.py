"""Listar membros (§8, `?active=true`)."""

from dataclasses import dataclass

from app.application.dto.members import MemberView
from app.domain.ports.repositories import MemberRepository


@dataclass(frozen=True)
class ListMembers:
    members: MemberRepository

    def execute(self, *, active: bool | None = None) -> list[MemberView]:
        return [
            MemberView.of(member)
            for member in sorted(
                self.members.list_all(active=active),
                key=lambda member: member.name.casefold(),
            )
        ]
