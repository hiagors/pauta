"""Alocação: uma linha por sprint ocupada (§6.7).

O Catálogo do Aurora, da Sprint 18 à 22, são cinco linhas. É o que torna a
grade trivial de renderizar e permite pausar uma frente no meio sem gambiarra.
"""

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from app.domain.value_objects.assignee import Assignee


@dataclass(frozen=True)
class Allocation:
    id: UUID
    initiative_id: UUID
    sprint_id: UUID
    assignee: Assignee

    @classmethod
    def create(
        cls,
        *,
        initiative_id: UUID,
        sprint_id: UUID,
        assignee: Assignee,
        id: UUID | None = None,
    ) -> Self:
        return cls(
            id=id or uuid4(),
            initiative_id=initiative_id,
            sprint_id=sprint_id,
            assignee=assignee,
        )

    @classmethod
    def create_from_ids(
        cls,
        *,
        initiative_id: UUID,
        sprint_id: UUID,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
        id: UUID | None = None,
    ) -> Self:
        """Caminho do payload HTTP e do mapper: valida "exatamente um"."""
        return cls.create(
            initiative_id=initiative_id,
            sprint_id=sprint_id,
            assignee=Assignee.from_ids(squad_id=squad_id, member_id=member_id),
            id=id,
        )

    @property
    def squad_id(self) -> UUID | None:
        return self.assignee.squad_id

    @property
    def member_id(self) -> UUID | None:
        return self.assignee.member_id
