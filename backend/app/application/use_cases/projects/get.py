"""Ler um projeto com as iniciativas dele (§8)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.initiatives import InitiativeView
from app.application.dto.projects import ProjectDetailView, ProjectView
from app.domain.errors import ProjectNotFound
from app.domain.ports.repositories import InitiativeRepository, ProjectRepository


@dataclass(frozen=True)
class GetProject:
    projects: ProjectRepository
    initiatives: InitiativeRepository

    def execute(self, project_id: UUID) -> ProjectDetailView:
        project = self.projects.get(project_id)
        if project is None:
            raise ProjectNotFound(project_id)
        return ProjectDetailView(
            project=ProjectView.of(project),
            initiatives=tuple(
                InitiativeView.of(initiative)
                for initiative in sorted(
                    self.initiatives.list_all(project_id=project_id),
                    key=lambda item: (item.priority.rank, item.name),
                )
            ),
        )
