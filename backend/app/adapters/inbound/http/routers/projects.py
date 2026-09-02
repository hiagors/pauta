"""`/projects` (§8)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.projects import (
    ProjectCreateIn,
    ProjectDetailOut,
    ProjectOut,
    ProjectPatchIn,
)
from app.application.use_cases.projects.archive import ArchiveProject
from app.application.use_cases.projects.create import CreateProject
from app.application.use_cases.projects.get import GetProject
from app.application.use_cases.projects.list import ListProjects
from app.application.use_cases.projects.update import UpdateProject

router = APIRouter(prefix="/projects", tags=["projetos"])


@router.get("", summary="Lista projetos")
def list_projects(
    ports: PortsDep,
    active: bool | None = None,
    q: Annotated[str | None, Query(description="Busca por nome")] = None,
) -> list[ProjectOut]:
    found = ports.use_case(ListProjects).execute(active=active, query=q)
    return [ProjectOut.model_validate(view) for view in found]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Cria projeto e a primeira iniciativa",
)
def create_project(ports: PortsDep, body: ProjectCreateIn) -> ProjectDetailOut:
    """RN-I1: projeto nasce com uma iniciativa, porque projeto sem iniciativa
    não é planejável."""
    return ProjectDetailOut.model_validate(
        ports.use_case(CreateProject).execute(body.to_input())
    )


@router.get("/{project_id}", summary="Projeto com as iniciativas dele")
def get_project(ports: PortsDep, project_id: UUID) -> ProjectDetailOut:
    return ProjectDetailOut.model_validate(
        ports.use_case(GetProject).execute(project_id)
    )


@router.patch("/{project_id}", summary="Altera projeto")
def update_project(
    ports: PortsDep, project_id: UUID, body: ProjectPatchIn
) -> ProjectOut:
    return ProjectOut.model_validate(
        ports.use_case(UpdateProject).execute(project_id, body.to_input())
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui projeto",
)
def delete_project(ports: PortsDep, project_id: UUID) -> None:
    """409 se alguma iniciativa do projeto tiver alocação (§8)."""
    ports.use_case(ArchiveProject).execute(project_id)
