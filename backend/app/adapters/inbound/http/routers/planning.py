"""`/planning/grid` e `/planning/backlog` (§8)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.planning import BacklogOut, GridOut
from app.application.dto.planning import BacklogOrder, BacklogQuery, GridQuery
from app.application.use_cases.planning.get_backlog import GetBacklog
from app.application.use_cases.planning.get_grid import GetGrid

router = APIRouter(prefix="/planning", tags=["planejamento"])


@router.get("/grid", summary="A grade de planejamento")
def get_grid(
    ports: PortsDep,
    sprint_from: int | None = None,
    sprint_to: int | None = None,
    squad_id: UUID | None = None,
    member_id: UUID | None = None,
    project_id: UUID | None = None,
) -> GridOut:
    """Sem intervalo, a janela é o trimestre corrente (RN13)."""
    query = GridQuery(
        sprint_from=sprint_from,
        sprint_to=sprint_to,
        squad_id=squad_id,
        member_id=member_id,
        project_id=project_id,
    )
    return GridOut.model_validate(ports.use_case(GetGrid).execute(query))


@router.get("/backlog", summary="O backlog")
def get_backlog(
    ports: PortsDep,
    order_by: BacklogOrder = BacklogOrder.PRIORITY,
    descending: Annotated[
        bool, Query(description="Inverte a ordem; nulos seguem por último")
    ] = False,
) -> BacklogOut:
    """Iniciativas em `BACKLOG`, sem as de projeto de reserva de capacidade.
    `DEPRIORITIZED` não aparece aqui — é filtro da tela de projetos (§8)."""
    return BacklogOut.model_validate(
        ports.use_case(GetBacklog).execute(
            BacklogQuery(order_by=order_by, descending=descending)
        )
    )
