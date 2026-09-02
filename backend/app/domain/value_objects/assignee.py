"""Responsável por uma alocação: uma squad **ou** um membro."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from uuid import UUID

from app.domain.errors import AmbiguousAssignee, AssigneeRequired


class AssigneeKind(StrEnum):
    """Minúsculo porque é o valor que viaja no JSON (`assignee.kind`, §8)."""

    SQUAD = "squad"
    MEMBER = "member"


@dataclass(frozen=True)
class Assignee:
    """Um responsável, nunca dois, nunca nenhum.

    A invariante "exatamente um de squad_id / member_id" (§6.7) fica aqui, e é
    por isso que `Allocation` guarda um `Assignee` em vez de dois UUIDs
    opcionais: estado inválido não é representável.
    """

    kind: AssigneeKind
    id: UUID

    @classmethod
    def for_squad(cls, squad_id: UUID) -> Self:
        return cls(kind=AssigneeKind.SQUAD, id=squad_id)

    @classmethod
    def for_member(cls, member_id: UUID) -> Self:
        return cls(kind=AssigneeKind.MEMBER, id=member_id)

    @classmethod
    def from_ids(
        cls, *, squad_id: UUID | None = None, member_id: UUID | None = None
    ) -> Self:
        """Constrói a partir do par de colunas do banco ou do payload HTTP."""
        if squad_id is not None and member_id is not None:
            raise AmbiguousAssignee
        if squad_id is not None:
            return cls.for_squad(squad_id)
        if member_id is not None:
            return cls.for_member(member_id)
        raise AssigneeRequired

    @property
    def is_squad(self) -> bool:
        return self.kind is AssigneeKind.SQUAD

    @property
    def is_member(self) -> bool:
        return self.kind is AssigneeKind.MEMBER

    @property
    def squad_id(self) -> UUID | None:
        return self.id if self.is_squad else None

    @property
    def member_id(self) -> UUID | None:
        return self.id if self.is_member else None
