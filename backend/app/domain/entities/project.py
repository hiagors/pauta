"""Projeto: agrupador. Não tem status, prioridade nem alocação (§6.1)."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from app.domain.errors import InvalidName
from app.domain.value_objects.color import Color


@dataclass
class Project:
    id: UUID
    name: str
    description: str = ""
    color: Color | None = None
    is_capacity_reserve: bool = False
    is_active: bool = True

    def __post_init__(self) -> None:
        self.name = _require_name(self.name)
        self.description = self.description.strip()

    @classmethod
    def create(
        cls,
        *,
        name: str,
        description: str = "",
        color: Color | None = None,
        is_capacity_reserve: bool = False,
        id: UUID | None = None,
    ) -> Self:
        """Projeto novo. Rehidratação (mapper, import de snapshot) usa o
        construtor da dataclass, que valida as mesmas invariantes."""
        return cls(
            id=id or uuid4(),
            name=name,
            description=description,
            color=color,
            is_capacity_reserve=is_capacity_reserve,
        )

    @property
    def effective_color(self) -> Color:
        """Projeto sem cor usa a cor neutra padrão (§10.2)."""
        return self.color or Color.default_project()

    def rename(self, name: str) -> None:
        self.name = _require_name(name)

    def set_description(self, description: str) -> None:
        self.description = description.strip()

    def set_color(self, color: Color | None) -> None:
        self.color = color

    def set_capacity_reserve(self, is_capacity_reserve: bool) -> None:
        """Reserva de capacidade é configuração, ligável e desligável (§3)."""
        self.is_capacity_reserve = is_capacity_reserve

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False


def _require_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidName("do projeto")
    return cleaned
