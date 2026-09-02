"""DTOs de iniciativa (§6.2)."""

from dataclasses import dataclass
from datetime import date
from typing import Self
from uuid import UUID

from app.application.dto.common import UNSET, Patch
from app.domain.entities.initiative import Initiative
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class CreateInitiativeInput:
    project_id: UUID
    name: str
    layer: str | None = None
    description: str = ""
    priority: Priority = Priority.MEDIUM
    estimated_sprints: int | None = None


@dataclass(frozen=True)
class UpdateInitiativeInput:
    """Sem `status` e sem `project_id`.

    Status muda por `POST /initiatives/{id}/status`, que é a transição manual
    validada do §6.3. Mover iniciativa de projeto não está no spec.
    """

    name: Patch[str] = UNSET
    layer: Patch[str | None] = UNSET
    description: Patch[str] = UNSET
    priority: Patch[Priority] = UNSET
    estimated_sprints: Patch[int | None] = UNSET


@dataclass(frozen=True)
class InitiativeFilter:
    """Filtros de `GET /initiatives` (§8).

    `statuses` e `priorities` são coleções porque a porta do repositório é
    plural; a borda HTTP recebe um valor só e embrulha.
    """

    project_id: UUID | None = None
    statuses: tuple[InitiativeStatus, ...] = ()
    priorities: tuple[Priority, ...] = ()
    layer: str | None = None
    query: str | None = None


@dataclass(frozen=True)
class InitiativeView:
    id: UUID
    project_id: UUID
    name: str
    layer: str | None
    description: str
    priority: Priority
    estimated_sprints: int | None
    status: InitiativeStatus
    entered_at: date

    @classmethod
    def of(cls, initiative: Initiative) -> Self:
        return cls(
            id=initiative.id,
            project_id=initiative.project_id,
            name=initiative.name,
            layer=initiative.layer,
            description=initiative.description,
            priority=initiative.priority,
            estimated_sprints=initiative.estimated_sprints,
            status=initiative.status,
            entered_at=initiative.entered_at,
        )
