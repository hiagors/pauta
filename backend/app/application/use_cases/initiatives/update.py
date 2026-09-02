"""Editar iniciativa (`PATCH /initiatives/{id}`)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.common import is_set
from app.application.dto.initiatives import InitiativeView, UpdateInitiativeInput
from app.domain.errors import DuplicateName, InitiativeNotFound
from app.domain.ports.repositories import InitiativeRepository


@dataclass(frozen=True)
class UpdateInitiative:
    initiatives: InitiativeRepository

    def execute(
        self, initiative_id: UUID, data: UpdateInitiativeInput
    ) -> InitiativeView:
        initiative = self.initiatives.get(initiative_id)
        if initiative is None:
            raise InitiativeNotFound(initiative_id)
        if is_set(data.name):
            initiative.rename(data.name)
            other = self.initiatives.get_by_name(
                project_id=initiative.project_id, name=initiative.name
            )
            if other is not None and other.id != initiative.id:
                raise DuplicateName("uma iniciativa neste projeto", initiative.name)
        if is_set(data.layer):
            initiative.set_layer(data.layer)
        if is_set(data.description):
            initiative.set_description(data.description)
        if is_set(data.priority):
            initiative.set_priority(data.priority)
        if is_set(data.estimated_sprints):
            initiative.set_estimated_sprints(data.estimated_sprints)
        self.initiatives.update(initiative)
        return InitiativeView.of(initiative)
