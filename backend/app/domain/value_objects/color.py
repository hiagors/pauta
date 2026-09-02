"""Cor de projeto, em hexadecimal."""

import re
from dataclasses import dataclass
from typing import Final, Self

from app.domain.errors import InvalidColor

#: Cor de projeto sem cor definida (§6.1, §10.2 `--color-project-default`).
DEFAULT_PROJECT_COLOR: Final = "#7A869A"

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class Color:
    """`#RRGGBB`, normalizado em maiúsculas para o diff do snapshot ser estável."""

    value: str

    def __post_init__(self) -> None:
        if not _HEX.match(self.value):
            raise InvalidColor(self.value)
        object.__setattr__(self, "value", self.value.upper())

    @classmethod
    def parse(cls, raw: str | None) -> Self | None:
        """`None` e string vazia viram `None` — o projeto usa a cor padrão."""
        if raw is None or not raw.strip():
            return None
        return cls(raw.strip())

    @classmethod
    def default_project(cls) -> Self:
        return cls(DEFAULT_PROJECT_COLOR)

    def __str__(self) -> str:
        return self.value
