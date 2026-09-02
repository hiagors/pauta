"""Inativar membro (`DELETE /members/{id}`, §6.4).

Soft delete e ponto: apagar fisicamente reescreveria alocações passadas. O
inativo sai dos seletores da UI, continua no histórico, e os alertas param de
considerá-lo (premissa A3 do §16). A composição de squad dele em sprints
futuras permanece no dado, como registro.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.members import MemberView
from app.domain.errors import MemberNotFound
from app.domain.ports.repositories import MemberRepository


@dataclass(frozen=True)
class DeactivateMember:
    members: MemberRepository

    def execute(self, member_id: UUID) -> MemberView:
        member = self.members.get(member_id)
        if member is None:
            raise MemberNotFound(member_id)
        member.deactivate()
        self.members.update(member)
        return MemberView.of(member)
