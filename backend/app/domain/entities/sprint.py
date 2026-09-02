"""Sprint: marcação de tempo (§6.6).

Só as invariantes de **uma** sprint moram aqui. Sobreposição, numeração sem
buraco e `start(N+1) > end(N)` são invariantes do **conjunto** e vivem em
`services/planning_rules.py`.

Sprint nunca é excluída (D13).
"""

from dataclasses import dataclass
from datetime import date
from typing import Self
from uuid import UUID, uuid4

from app.domain.errors import InvalidSprintDates, InvalidSprintNumber
from app.domain.value_objects.sprint_range import MIN_SPRINT_NUMBER


@dataclass
class Sprint:
    id: UUID
    number: int
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.number < MIN_SPRINT_NUMBER:
            raise InvalidSprintNumber(self.number)
        if self.end_date <= self.start_date:
            raise InvalidSprintDates(self.start_date, self.end_date)

    @classmethod
    def create(
        cls,
        *,
        number: int,
        start_date: date,
        end_date: date,
        id: UUID | None = None,
    ) -> Self:
        return cls(
            id=id or uuid4(),
            number=number,
            start_date=start_date,
            end_date=end_date,
        )

    @property
    def duration_days(self) -> int:
        """Dias de calendário entre início e fim. O padrão é 11 (§6.6).

        Dias **úteis** variam por feriado e o sistema não os modela.
        """
        return (self.end_date - self.start_date).days

    def contains(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date

    def overlaps(self, other: Sprint) -> bool:
        return self.start_date <= other.end_date and other.start_date <= self.end_date

    def intersects(self, start: date, end: date) -> bool:
        """Intersecta a janela `[start, end]` — usado pela grade (RN13)."""
        return self.start_date <= end and start <= self.end_date
