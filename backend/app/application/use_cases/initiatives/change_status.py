"""Transição manual de status (`POST /initiatives/{id}/status`, §6.3).

Só as transições da tabela do §6.3 passam por aqui. `BACKLOG` ⇄ `PLANNED` é
automático, efeito de ganhar ou perder alocação, e vive em
`recalculate_status` — os dois caminhos não se contaminam.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.initiatives import InitiativeView
from app.domain.errors import InitiativeNotFound
from app.domain.ports.repositories import InitiativeRepository
from app.domain.value_objects.initiative_status import InitiativeStatus


@dataclass(frozen=True)
class ChangeInitiativeStatus:
    initiatives: InitiativeRepository

    def execute(
        self, initiative_id: UUID, new_status: InitiativeStatus
    ) -> InitiativeView:
        initiative = self.initiatives.get(initiative_id)
        if initiative is None:
            raise InitiativeNotFound(initiative_id)
        initiative.change_status(new_status)
        self.initiatives.update(initiative)
        return InitiativeView.of(initiative)
