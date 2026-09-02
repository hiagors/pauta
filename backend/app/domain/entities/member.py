"""Membro do time (§6.4).

É `Member`, não `User`: não há login no sistema. **Nunca é deletado** —
apagar reescreveria alocações passadas.
"""

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from app.domain.errors import InvalidName


@dataclass
class Member:
    id: UUID
    name: str
    short_name: str
    role: str = ""
    is_active: bool = True

    def __post_init__(self) -> None:
        self.name = _require(self.name, "do membro")
        self.short_name = _require(self.short_name, "curto do membro")
        self.role = self.role.strip()

    @classmethod
    def create(
        cls,
        *,
        name: str,
        short_name: str,
        role: str = "",
        id: UUID | None = None,
    ) -> Self:
        return cls(id=id or uuid4(), name=name, short_name=short_name, role=role)

    def rename(self, name: str) -> None:
        self.name = _require(name, "do membro")

    def set_short_name(self, short_name: str) -> None:
        self.short_name = _require(short_name, "curto do membro")

    def set_role(self, role: str) -> None:
        self.role = role.strip()

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        """`DELETE /members/{id}` cai aqui: inativo sai dos seletores e
        continua no histórico."""
        self.is_active = False


def _require(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidName(label)
    return cleaned
