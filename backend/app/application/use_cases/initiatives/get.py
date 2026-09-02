"""Ler uma iniciativa (§8)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.initiatives import InitiativeView
from app.domain.errors import InitiativeNotFound
from app.domain.ports.repositories import InitiativeRepository


@dataclass(frozen=True)
class GetInitiative:
    initiatives: InitiativeRepository

    def execute(self, initiative_id: UUID) -> InitiativeView:
        initiative = self.initiatives.get(initiative_id)
        if initiative is None:
            raise InitiativeNotFound(initiative_id)
        return InitiativeView.of(initiative)
