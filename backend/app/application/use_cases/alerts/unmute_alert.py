"""Reativar um alerta silenciado (`DELETE /alerts/mute/{mute_id}`).

É o botão "Reativar" do painel, que usa o `mute_id` que o alerta devolve.
"""

from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import MutedAlertNotFound
from app.domain.ports.repositories import MutedAlertRepository


@dataclass(frozen=True)
class UnmuteAlert:
    muted_alerts: MutedAlertRepository

    def execute(self, mute_id: UUID) -> None:
        if self.muted_alerts.get(mute_id) is None:
            raise MutedAlertNotFound(mute_id)
        self.muted_alerts.delete(mute_id)
