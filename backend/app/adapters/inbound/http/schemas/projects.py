"""Schemas de projeto (§6.1, §8)."""

from uuid import UUID

from app.adapters.inbound.http.schemas.common import (
    InputModel,
    OutputModel,
    PatchModel,
)
from app.adapters.inbound.http.schemas.initiatives import InitiativeOut
from app.application.dto.projects import CreateProjectInput, UpdateProjectInput


class ProjectCreateIn(InputModel):
    """`POST /projects` cria também a primeira iniciativa (RN-I1)."""

    name: str
    description: str = ""
    color: str | None = None
    is_capacity_reserve: bool = False

    def to_input(self) -> CreateProjectInput:
        return CreateProjectInput(
            name=self.name,
            description=self.description,
            color=self.color,
            is_capacity_reserve=self.is_capacity_reserve,
        )


class ProjectPatchIn(PatchModel):
    """`color: null` limpa a cor; a **ausência** de `color` não mexe nela (§8)."""

    name: str = ""
    description: str = ""
    color: str | None = None
    is_capacity_reserve: bool = False
    is_active: bool = True

    def to_input(self) -> UpdateProjectInput:
        return UpdateProjectInput(
            name=self.patch("name"),
            description=self.patch("description"),
            color=self.patch("color"),
            is_capacity_reserve=self.patch("is_capacity_reserve"),
            is_active=self.patch("is_active"),
        )


class ProjectOut(OutputModel):
    """`color` é o que está gravado, e pode ser nulo.

    Quem edita precisa ver o campo vazio para saber que não escolheu cor; a
    grade e o backlog recebem a cor já resolvida (§10.2).
    """

    id: UUID
    name: str
    description: str
    color: str | None
    is_capacity_reserve: bool
    is_active: bool


class ProjectDetailOut(OutputModel):
    """`GET /projects/{id}` e a resposta de `POST /projects`: inclui as
    iniciativas (§8)."""

    project: ProjectOut
    initiatives: list[InitiativeOut]
