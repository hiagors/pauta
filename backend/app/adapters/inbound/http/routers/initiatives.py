"""`/initiatives` (§8)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.initiatives import (
    InitiativeCreateIn,
    InitiativeOut,
    InitiativePatchIn,
    InitiativeStatusIn,
)
from app.application.dto.initiatives import InitiativeFilter
from app.application.use_cases.initiatives.archive import ArchiveInitiative
from app.application.use_cases.initiatives.change_status import ChangeInitiativeStatus
from app.application.use_cases.initiatives.create import CreateInitiative
from app.application.use_cases.initiatives.get import GetInitiative
from app.application.use_cases.initiatives.list import ListInitiatives
from app.application.use_cases.initiatives.update import UpdateInitiative
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority

router = APIRouter(prefix="/initiatives", tags=["iniciativas"])


@router.get("", summary="Lista iniciativas")
def list_initiatives(
    ports: PortsDep,
    project_id: UUID | None = None,
    status_: Annotated[InitiativeStatus | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    layer: str | None = None,
    q: Annotated[str | None, Query(description="Busca por nome")] = None,
) -> list[InitiativeOut]:
    """A query traz um valor por filtro; o `InitiativeFilter` é plural porque a
    porta do repositório é plural, e é aqui que o valor único é embrulhado."""
    filters = InitiativeFilter(
        project_id=project_id,
        statuses=() if status_ is None else (status_,),
        priorities=() if priority is None else (priority,),
        layer=layer,
        query=q,
    )
    return [
        InitiativeOut.model_validate(view)
        for view in ports.use_case(ListInitiatives).execute(filters)
    ]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Cria iniciativa")
def create_initiative(ports: PortsDep, body: InitiativeCreateIn) -> InitiativeOut:
    return InitiativeOut.model_validate(
        ports.use_case(CreateInitiative).execute(body.to_input())
    )


@router.get("/{initiative_id}", summary="Iniciativa")
def get_initiative(ports: PortsDep, initiative_id: UUID) -> InitiativeOut:
    return InitiativeOut.model_validate(
        ports.use_case(GetInitiative).execute(initiative_id)
    )


@router.patch("/{initiative_id}", summary="Altera iniciativa")
def update_initiative(
    ports: PortsDep, initiative_id: UUID, body: InitiativePatchIn
) -> InitiativeOut:
    return InitiativeOut.model_validate(
        ports.use_case(UpdateInitiative).execute(initiative_id, body.to_input())
    )


@router.post("/{initiative_id}/status", summary="Transição manual de status")
def change_status(
    ports: PortsDep, initiative_id: UUID, body: InitiativeStatusIn
) -> InitiativeOut:
    """Só as transições manuais do §6.3. `BACKLOG <-> PLANNED` não passa por
    aqui: é efeito automático de ganhar ou perder alocação."""
    return InitiativeOut.model_validate(
        ports.use_case(ChangeInitiativeStatus).execute(initiative_id, body.status)
    )


@router.delete(
    "/{initiative_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui iniciativa",
)
def delete_initiative(ports: PortsDep, initiative_id: UUID) -> None:
    """409 se houver alocação, ou se for a última do projeto (§8). Nos dois
    casos o caminho é `CANCELLED`."""
    ports.use_case(ArchiveInitiative).execute(initiative_id)
