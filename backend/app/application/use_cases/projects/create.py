"""Criar projeto — e, com ele, a primeira iniciativa (RN-I1)."""

from dataclasses import dataclass

from app.application.dto.initiatives import InitiativeView
from app.application.dto.projects import (
    CreateProjectInput,
    ProjectDetailView,
    ProjectView,
)
from app.domain.entities.initiative import Initiative
from app.domain.entities.project import Project
from app.domain.errors import DuplicateName
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import InitiativeRepository, ProjectRepository
from app.domain.value_objects.color import Color


@dataclass(frozen=True)
class CreateProject:
    projects: ProjectRepository
    initiatives: InitiativeRepository
    clock: Clock

    def execute(self, data: CreateProjectInput) -> ProjectDetailView:
        """RN-I1: um projeto nunca nasce sem iniciativa.

        A primeira herda o nome do projeto, entra em `BACKLOG` com prioridade
        `MEDIUM` e é renomeável em seguida — quem tem uma frente única nunca
        precisa pensar em iniciativa.
        """
        project = Project.create(
            name=data.name,
            description=data.description,
            color=Color.parse(data.color),
            is_capacity_reserve=data.is_capacity_reserve,
        )
        if self.projects.get_by_name(project.name) is not None:
            raise DuplicateName("um projeto", project.name)
        initiative = Initiative.create_first_for_project(project, self.clock)
        self.projects.add(project)
        self.initiatives.add(initiative)
        return ProjectDetailView(
            project=ProjectView.of(project),
            initiatives=(InitiativeView.of(initiative),),
        )
