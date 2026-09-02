"""Schemas de sprint (§6.6, §8).

Não existe schema de exclusão: sprint nunca é excluída (D13).
"""

from datetime import date
from uuid import UUID

from app.adapters.inbound.http.schemas.common import InputModel, OutputModel
from app.application.dto.sprints import CreateSprintInput


class SprintCreateIn(InputModel):
    """`number` ausente continua a numeração da última cadastrada (RN10)."""

    start_date: date
    end_date: date
    number: int | None = None

    def to_input(self) -> CreateSprintInput:
        return CreateSprintInput(
            start_date=self.start_date, end_date=self.end_date, number=self.number
        )


class SprintOut(OutputModel):
    """`is_current` é derivado do conjunto inteiro (RN12), não da sprint."""

    id: UUID
    number: int
    start_date: date
    end_date: date
    is_current: bool


class SprintProposalOut(OutputModel):
    """`GET /sprints/next/preview`: editável antes de confirmar (RN10)."""

    number: int
    start_date: date
    end_date: date
