"""Excluir projeto (`DELETE /projects/{id}`).

O §8 anota "soft delete" onde a exclusão é lógica (membro e squad). Aqui não
anota: o projeto sai do banco de verdade, junto com as iniciativas dele — que
não podem ficar órfãs, porque projeto sem iniciativa não existe (RN-I2).

O que protege o histórico é a guarda: se **qualquer** iniciativa do projeto tem
alocação, a exclusão é 409 e o caminho é marcar a iniciativa como `CANCELLED`.
"""

from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import HasAllocations, ProjectNotFound
from app.domain.ports.repositories import (
    AllocationRepository,
    InitiativeRepository,
    ProjectRepository,
)


@dataclass(frozen=True)
class ArchiveProject:
    projects: ProjectRepository
    initiatives: InitiativeRepository
    allocations: AllocationRepository

    def execute(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise ProjectNotFound(project_id)
        initiatives = self.initiatives.list_all(project_id=project_id)
        for initiative in initiatives:
            if self.allocations.count_by_initiative(initiative.id) > 0:
                raise HasAllocations("o projeto")
        for initiative in initiatives:
            self.initiatives.delete(initiative.id)
        self.projects.delete(project_id)
