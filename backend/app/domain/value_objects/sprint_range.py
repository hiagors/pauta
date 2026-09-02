"""Intervalo fechado de números de sprint."""

from collections.abc import Iterator
from dataclasses import dataclass

from app.domain.errors import InvalidSprintNumber, InvalidSprintRange

MIN_SPRINT_NUMBER = 1


@dataclass(frozen=True)
class SprintRange:
    """`[from_number, to_number]`, inclusivo nas duas pontas.

    É o que o pedido de alocação carrega (RN1). Um intervalo de uma sprint só
    tem `from_number == to_number`.
    """

    from_number: int
    to_number: int

    def __post_init__(self) -> None:
        if self.from_number < MIN_SPRINT_NUMBER:
            raise InvalidSprintNumber(self.from_number)
        if self.to_number < MIN_SPRINT_NUMBER:
            raise InvalidSprintNumber(self.to_number)
        if self.to_number < self.from_number:
            raise InvalidSprintRange(self.from_number, self.to_number)

    @property
    def numbers(self) -> tuple[int, ...]:
        return tuple(range(self.from_number, self.to_number + 1))

    def __iter__(self) -> Iterator[int]:
        return iter(self.numbers)

    def __contains__(self, number: int) -> bool:
        return self.from_number <= number <= self.to_number

    def __len__(self) -> int:
        return self.to_number - self.from_number + 1
