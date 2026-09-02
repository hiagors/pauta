"""Editar projeto (`PATCH /projects/{id}`)."""

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.common import is_set
from app.application.dto.projects import ProjectView, UpdateProjectInput
from app.domain.errors import DuplicateName, ProjectNotFound
from app.domain.ports.repositories import ProjectRepository
from app.domain.value_objects.color import Color


@dataclass(frozen=True)
class UpdateProject:
    projects: ProjectRepository

    def execute(self, project_id: UUID, data: UpdateProjectInput) -> ProjectView:
        """Campo ausente não é tocado; `color: null` limpa a cor (§6.1)."""
        project = self.projects.get(project_id)
        if project is None:
            raise ProjectNotFound(project_id)
        if is_set(data.name):
            project.rename(data.name)
            other = self.projects.get_by_name(project.name)
            if other is not None and other.id != project.id:
                raise DuplicateName("um projeto", project.name)
        if is_set(data.description):
            project.set_description(data.description)
        if is_set(data.color):
            project.set_color(Color.parse(data.color))
        if is_set(data.is_capacity_reserve):
            project.set_capacity_reserve(data.is_capacity_reserve)
        if is_set(data.is_active):
            project.activate() if data.is_active else project.deactivate()
        self.projects.update(project)
        return ProjectView.of(project)
