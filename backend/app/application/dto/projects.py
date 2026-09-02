"""DTOs de projeto (§6.1)."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.application.dto.common import UNSET, Patch
from app.application.dto.initiatives import InitiativeView
from app.domain.entities.project import Project


@dataclass(frozen=True)
class CreateProjectInput:
    name: str
    description: str = ""
    color: str | None = None
    is_capacity_reserve: bool = False


@dataclass(frozen=True)
class UpdateProjectInput:
    name: Patch[str] = UNSET
    description: Patch[str] = UNSET
    color: Patch[str | None] = UNSET
    is_capacity_reserve: Patch[bool] = UNSET
    is_active: Patch[bool] = UNSET


@dataclass(frozen=True)
class ProjectView:
    """`color` é o que está **gravado**, e pode ser nulo.

    Quem edita precisa ver o campo vazio para saber que não escolheu cor; quem
    só desenha usa a cor padrão do token `--color-project-default` (§10.2). As
    telas de leitura (grade, backlog) recebem a cor já resolvida.
    """

    id: UUID
    name: str
    description: str
    color: str | None
    is_capacity_reserve: bool
    is_active: bool

    @classmethod
    def of(cls, project: Project) -> Self:
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            color=str(project.color) if project.color is not None else None,
            is_capacity_reserve=project.is_capacity_reserve,
            is_active=project.is_active,
        )


@dataclass(frozen=True)
class ProjectDetailView:
    """`GET /projects/{id}` e a resposta de `POST /projects` (RN-I1)."""

    project: ProjectView
    initiatives: tuple[InitiativeView, ...]
