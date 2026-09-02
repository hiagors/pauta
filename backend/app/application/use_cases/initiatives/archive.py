"""Excluir iniciativa (`DELETE /initiatives/{id}`).

Duas guardas, as duas 409 (§8):

- iniciativa com alocação não sai — apagar reescreveria o histórico do plano;
- a última iniciativa do projeto não sai — projeto sem iniciativa não existe
  (RN-I2).

Nos dois casos o caminho é `CANCELLED`, que preserva o registro.
"""

from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import (
    HasAllocations,
    InitiativeNotFound,
    LastInitiativeOfProject,
)
from app.domain.ports.repositories import AllocationRepository, InitiativeRepository

#: Abaixo disso o projeto ficaria sem iniciativa.
_MIN_INITIATIVES_PER_PROJECT = 1


@dataclass(frozen=True)
class ArchiveInitiative:
    initiatives: InitiativeRepository
    allocations: AllocationRepository

    def execute(self, initiative_id: UUID) -> None:
        initiative = self.initiatives.get(initiative_id)
        if initiative is None:
            raise InitiativeNotFound(initiative_id)
        if self.allocations.count_by_initiative(initiative_id) > 0:
            raise HasAllocations("a iniciativa")
        remaining = self.initiatives.count_by_project(initiative.project_id)
        if remaining <= _MIN_INITIATIVES_PER_PROJECT:
            raise LastInitiativeOfProject(initiative.project_id)
        self.initiatives.delete(initiative_id)
