"""Squad: agrupamento com prazo (§6.5).

A squad **não** carrega lista de membros. Quem está nela em cada sprint é
`SquadMembership`.
"""

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from app.domain.errors import InvalidName


@dataclass
class Squad:
    id: UUID
    name: str
    representative_member_id: UUID | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        self.name = _require_name(self.name)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        representative_member_id: UUID | None = None,
        id: UUID | None = None,
    ) -> Self:
        return cls(
            id=id or uuid4(),
            name=name,
            representative_member_id=representative_member_id,
        )

    def rename(self, name: str) -> None:
        self.name = _require_name(name)

    def set_representative(self, member_id: UUID | None) -> None:
        """RN-S1: o domínio só guarda o UUID.

        Que o membro exista e esteja ativo é checado no use case, que tem o
        repositório. Validar contra a composição da squad é **proibido**: no
        momento da criação a squad não tem membership nenhuma, e o
        representante é uma ponte, não necessariamente quem executa.
        """
        self.representative_member_id = member_id

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False


def _require_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidName("da squad")
    return cleaned
