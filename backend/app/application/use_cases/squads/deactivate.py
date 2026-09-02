"""Inativar squad (`DELETE /squads/{id}`, §8).

Soft delete: a squad sai dos seletores e das contas de alerta, e as alocações
que ela tem no passado continuam de pé. Squad é agrupamento com prazo — o
prazo terminar não apaga o que ela fez.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.squads import SquadView
from app.domain.errors import SquadNotFound
from app.domain.ports.repositories import SquadRepository


@dataclass(frozen=True)
class DeactivateSquad:
    squads: SquadRepository

    def execute(self, squad_id: UUID) -> SquadView:
        squad = self.squads.get(squad_id)
        if squad is None:
            raise SquadNotFound(squad_id)
        squad.deactivate()
        self.squads.update(squad)
        return SquadView.of(squad)
