"""Schemas de iniciativa (§6.2, §8)."""

from datetime import date
from uuid import UUID

from app.adapters.inbound.http.schemas.common import (
    InputModel,
    OutputModel,
    PatchModel,
)
from app.application.dto.initiatives import (
    CreateInitiativeInput,
    UpdateInitiativeInput,
)
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


class InitiativeCreateIn(InputModel):
    project_id: UUID
    name: str
    layer: str | None = None
    description: str = ""
    priority: Priority = Priority.MEDIUM
    estimated_sprints: int | None = None

    def to_input(self) -> CreateInitiativeInput:
        return CreateInitiativeInput(
            project_id=self.project_id,
            name=self.name,
            layer=self.layer,
            description=self.description,
            priority=self.priority,
            estimated_sprints=self.estimated_sprints,
        )


class InitiativePatchIn(PatchModel):
    """Sem `status` e sem `project_id`.

    Status muda por `POST /initiatives/{id}/status`, que é a transição manual
    validada do §6.3. Mover iniciativa de projeto não está no spec.
    """

    name: str = ""
    layer: str | None = None
    description: str = ""
    priority: Priority = Priority.MEDIUM
    estimated_sprints: int | None = None

    def to_input(self) -> UpdateInitiativeInput:
        return UpdateInitiativeInput(
            name=self.patch("name"),
            layer=self.patch("layer"),
            description=self.patch("description"),
            priority=self.patch("priority"),
            estimated_sprints=self.patch("estimated_sprints"),
        )


class InitiativeStatusIn(InputModel):
    """`POST /initiatives/{id}/status`: transição manual do §6.3."""

    status: InitiativeStatus


class InitiativeOut(OutputModel):
    id: UUID
    project_id: UUID
    name: str
    layer: str | None
    description: str
    priority: Priority
    estimated_sprints: int | None
    status: InitiativeStatus
    entered_at: date
