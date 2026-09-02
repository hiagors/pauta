"""DTOs de sprint (§6.6).

Não existe DTO de exclusão: sprint nunca é excluída (D13).
"""

from dataclasses import dataclass
from datetime import date
from typing import Self
from uuid import UUID

from app.domain.entities.sprint import Sprint
from app.domain.services.planning_rules import SprintProposal


@dataclass(frozen=True)
class CreateSprintInput:
    """`number` nulo continua a numeração da última cadastrada (RN10)."""

    start_date: date
    end_date: date
    number: int | None = None


@dataclass(frozen=True)
class SprintView:
    """`is_current` é derivado do conjunto inteiro (RN12), não da sprint."""

    id: UUID
    number: int
    start_date: date
    end_date: date
    is_current: bool

    @classmethod
    def of(cls, sprint: Sprint, *, is_current: bool) -> Self:
        return cls(
            id=sprint.id,
            number=sprint.number,
            start_date=sprint.start_date,
            end_date=sprint.end_date,
            is_current=is_current,
        )


@dataclass(frozen=True)
class SprintProposalView:
    """`GET /sprints/next/preview`: editável antes de confirmar (RN10)."""

    number: int
    start_date: date
    end_date: date

    @classmethod
    def of(cls, proposal: SprintProposal) -> Self:
        return cls(
            number=proposal.number,
            start_date=proposal.start_date,
            end_date=proposal.end_date,
        )
