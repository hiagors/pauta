"""Listar projetos (§8, `?active=&q=`)."""

from dataclasses import dataclass

from app.application.dto.projects import ProjectView
from app.domain.ports.repositories import ProjectRepository


@dataclass(frozen=True)
class ListProjects:
    projects: ProjectRepository

    def execute(
        self, *, active: bool | None = None, query: str | None = None
    ) -> list[ProjectView]:
        return [
            ProjectView.of(project)
            for project in sorted(
                self.projects.list_all(active=active, query=query),
                key=lambda project: project.name.casefold(),
            )
        ]
