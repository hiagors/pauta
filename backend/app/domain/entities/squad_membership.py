"""Composição da squad em uma sprint (§6.5).

Uma linha por (squad, membro, sprint), no mesmo idioma de `Allocation`. É o que
resolve o caso da Emilie: BNPL nas sprints 18 e 19, CRM da 20 em diante, sem
que isso vaze para as sprints anteriores.
"""

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SquadMembership:
    id: UUID
    squad_id: UUID
    member_id: UUID
    sprint_id: UUID

    @classmethod
    def create(
        cls,
        *,
        squad_id: UUID,
        member_id: UUID,
        sprint_id: UUID,
        id: UUID | None = None,
    ) -> Self:
        return cls(
            id=id or uuid4(),
            squad_id=squad_id,
            member_id=member_id,
            sprint_id=sprint_id,
        )
