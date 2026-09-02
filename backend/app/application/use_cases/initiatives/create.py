"""Criar iniciativa dentro de um projeto (§8)."""

from dataclasses import dataclass

from app.application.dto.initiatives import CreateInitiativeInput, InitiativeView
from app.domain.entities.initiative import Initiative
from app.domain.errors import DuplicateName, ProjectNotFound
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import InitiativeRepository, ProjectRepository


@dataclass(frozen=True)
class CreateInitiative:
    initiatives: InitiativeRepository
    projects: ProjectRepository
    clock: Clock

    def execute(self, data: CreateInitiativeInput) -> InitiativeView:
        """O nome é único **dentro do projeto** (§6.2), não no sistema.

        Duas "Reestruturação", uma no CRM e uma no BNPL, são normais.
        """
        if self.projects.get(data.project_id) is None:
            raise ProjectNotFound(data.project_id)
        initiative = Initiative.create(
            project_id=data.project_id,
            name=data.name,
            clock=self.clock,
            layer=data.layer,
            description=data.description,
            priority=data.priority,
            estimated_sprints=data.estimated_sprints,
        )
        existing = self.initiatives.get_by_name(
            project_id=data.project_id, name=initiative.name
        )
        if existing is not None:
            raise DuplicateName("uma iniciativa neste projeto", initiative.name)
        self.initiatives.add(initiative)
        return InitiativeView.of(initiative)
