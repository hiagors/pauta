"""DTOs de alocação (§6.7, §7.1) e as respostas de `POST /allocations` (§8)."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.alert import Alert
from app.domain.value_objects.initiative_status import InitiativeStatus


@dataclass(frozen=True)
class AllocateRangeInput:
    """Um responsável, nunca dois: quem valida é `Assignee.from_ids` (§6.7)."""

    initiative_id: UUID
    from_sprint_number: int
    to_sprint_number: int
    squad_id: UUID | None = None
    member_id: UUID | None = None


@dataclass(frozen=True)
class DeallocateRangeInput:
    """RN6: desalocar pelo intervalo. A célula única é `DeallocateCell`."""

    initiative_id: UUID
    from_sprint_number: int
    to_sprint_number: int


@dataclass(frozen=True)
class AllocationFilter:
    sprint_from: int | None = None
    sprint_to: int | None = None
    squad_id: UUID | None = None
    member_id: UUID | None = None
    initiative_id: UUID | None = None
    project_id: UUID | None = None


@dataclass(frozen=True)
class AllocationView:
    id: UUID
    initiative_id: UUID
    sprint_id: UUID
    sprint_number: int
    squad_id: UUID | None
    member_id: UUID | None


@dataclass(frozen=True)
class AllocationCellView:
    """Uma célula da grade: a alocação e a sprint em que ela caiu."""

    id: UUID
    sprint_number: int


@dataclass(frozen=True)
class AllocationResultView:
    """Resposta de `POST /allocations` (§8).

    `alerts` é o **estado atual** dos alertas das sprints tocadas, não um diff,
    e inclui os silenciados com `is_muted = true` — para a UI dizer "já
    silenciado" em vez de gritar de novo.
    """

    created: tuple[AllocationCellView, ...]
    already_existed: tuple[AllocationCellView, ...]
    missing_sprint_numbers: tuple[int, ...]
    initiative_status: InitiativeStatus
    alerts: tuple[Alert, ...]


@dataclass(frozen=True)
class DeallocationResultView:
    """Mesma ideia da alocação: o que saiu, o status resultante e os alertas."""

    removed: tuple[AllocationCellView, ...]
    initiative_status: InitiativeStatus
    alerts: tuple[Alert, ...]
