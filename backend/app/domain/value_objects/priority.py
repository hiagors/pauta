"""Prioridade da iniciativa."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def rank(self) -> int:
        """Peso de ordenação: 0 é o mais prioritário.

        Existe porque o backlog ordena por prioridade (§8) e a ordem
        HIGH > MEDIUM > LOW é um fato de negócio, não da tela.
        """
        return _RANKS[self]


_RANKS: Final[Mapping[Priority, int]] = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}
