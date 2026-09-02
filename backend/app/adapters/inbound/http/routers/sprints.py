"""`/sprints` (§6.6, §8).

Sem `DELETE`: sprint é marcação de tempo e nunca é excluída (D13).
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.sprints import (
    SprintCreateIn,
    SprintOut,
    SprintProposalOut,
)
from app.application.use_cases.sprints.create import CreateSprint
from app.application.use_cases.sprints.create_next import (
    CreateNextSprint,
    PreviewNextSprint,
)
from app.application.use_cases.sprints.list import ListSprints

router = APIRouter(prefix="/sprints", tags=["sprints"])


@router.get("", summary="Lista sprints")
def list_sprints(
    ports: PortsDep,
    number_from: Annotated[int | None, Query(alias="from")] = None,
    number_to: Annotated[int | None, Query(alias="to")] = None,
) -> list[SprintOut]:
    """`from` e `to` são os nomes do §8; `from` é palavra reservada em Python,
    por isso o `alias`."""
    return [
        SprintOut.model_validate(view)
        for view in ports.use_case(ListSprints).execute(
            number_from=number_from, number_to=number_to
        )
    ]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Cria sprint")
def create_sprint(ports: PortsDep, body: SprintCreateIn) -> SprintOut:
    return SprintOut.model_validate(
        ports.use_case(CreateSprint).execute(body.to_input())
    )


@router.get("/next/preview", summary="Propõe a próxima sprint")
def preview_next_sprint(ports: PortsDep) -> SprintProposalOut:
    """RN10: próxima segunda depois do fim da anterior, `start + 11 dias`. É
    proposta, não criação — a tela deixa editar antes de confirmar."""
    return SprintProposalOut.model_validate(ports.use_case(PreviewNextSprint).execute())


@router.post(
    "/next", status_code=status.HTTP_201_CREATED, summary="Cria a próxima sprint"
)
def create_next_sprint(ports: PortsDep) -> SprintOut:
    """Sem corpo: cria exatamente a proposta de `/next/preview` (§8)."""
    return SprintOut.model_validate(ports.use_case(CreateNextSprint).execute())
