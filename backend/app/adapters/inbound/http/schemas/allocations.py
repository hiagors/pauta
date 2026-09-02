"""Schemas de alocação (§6.7, §7.1, §8)."""

from uuid import UUID

from app.adapters.inbound.http.schemas.alerts import AlertOut
from app.adapters.inbound.http.schemas.common import InputModel, OutputModel
from app.application.dto.allocations import (
    AllocateRangeInput,
    DeallocateRangeInput,
)
from app.domain.value_objects.initiative_status import InitiativeStatus


class AllocateRangeIn(InputModel):
    """`POST /allocations` (§8). Um responsável, nunca dois.

    Mandar squad e membro juntos é `AMBIGUOUS_ASSIGNEE`, e mandar nenhum é
    `ASSIGNEE_REQUIRED`: a invariante é do domínio (`Assignee.from_ids`), não
    do schema, para que a CLI da Fase 5 não precise reimplementá-la.
    """

    initiative_id: UUID
    from_sprint_number: int
    to_sprint_number: int
    squad_id: UUID | None = None
    member_id: UUID | None = None

    def to_input(self) -> AllocateRangeInput:
        return AllocateRangeInput(
            initiative_id=self.initiative_id,
            from_sprint_number=self.from_sprint_number,
            to_sprint_number=self.to_sprint_number,
            squad_id=self.squad_id,
            member_id=self.member_id,
        )


class DeallocateRangeIn(InputModel):
    """`DELETE /allocations` com o intervalo no corpo (RN6)."""

    initiative_id: UUID
    from_sprint_number: int
    to_sprint_number: int

    def to_input(self) -> DeallocateRangeInput:
        return DeallocateRangeInput(
            initiative_id=self.initiative_id,
            from_sprint_number=self.from_sprint_number,
            to_sprint_number=self.to_sprint_number,
        )


class AllocationOut(OutputModel):
    """Uma linha de `GET /allocations`."""

    id: UUID
    initiative_id: UUID
    sprint_id: UUID
    sprint_number: int
    squad_id: UUID | None
    member_id: UUID | None


class AllocationCellOut(OutputModel):
    """Uma célula tocada pela operação: a alocação e a sprint em que caiu."""

    id: UUID
    sprint_number: int


class AllocationResultOut(OutputModel):
    """Resposta de `POST /allocations` (§8).

    `missing_sprint_numbers` é o relatório da alocação **parcial**: sprint que
    não existe no intervalo não derruba a operação inteira.

    `alerts` é o **estado atual** dos alertas das sprints tocadas, não um diff,
    e inclui os silenciados com `is_muted: true` — para a UI dizer "já
    silenciado" em vez de gritar de novo.
    """

    created: list[AllocationCellOut]
    already_existed: list[AllocationCellOut]
    missing_sprint_numbers: list[int]
    initiative_status: InitiativeStatus
    alerts: list[AlertOut]


class DeallocationResultOut(OutputModel):
    """Resposta dos dois `DELETE` de alocação: o que saiu, o status resultante
    e os alertas das sprints tocadas."""

    removed: list[AllocationCellOut]
    initiative_status: InitiativeStatus
    alerts: list[AlertOut]
