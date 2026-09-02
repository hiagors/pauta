"""`/squads` e a composição por sprint (§6.5, §8)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.squads import (
    RemoveMembershipsIn,
    SetMembershipsIn,
    SprintCompositionOut,
    SquadCreateIn,
    SquadDetailOut,
    SquadOut,
    SquadPatchIn,
)
from app.application.use_cases.squads.create import CreateSquad
from app.application.use_cases.squads.deactivate import DeactivateSquad
from app.application.use_cases.squads.get import GetSquad
from app.application.use_cases.squads.list import ListSquads
from app.application.use_cases.squads.list_memberships import ListSquadMemberships
from app.application.use_cases.squads.remove_memberships import RemoveSquadMemberships
from app.application.use_cases.squads.set_memberships import SetSquadMemberships
from app.application.use_cases.squads.update import UpdateSquad

router = APIRouter(prefix="/squads", tags=["squads"])


@router.get("", summary="Lista squads")
def list_squads(
    ports: PortsDep,
    active: bool | None = None,
    sprint_number: Annotated[
        int | None, Query(description="Expande a composição desta sprint")
    ] = None,
) -> list[SquadOut]:
    """Sem `sprint_number`, `members` vem vazio: a composição é por sprint
    (D11), e uma lista sem sprint seria mentira."""
    return [
        SquadOut.model_validate(view)
        for view in ports.use_case(ListSquads).execute(
            active=active, sprint_number=sprint_number
        )
    ]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Cria squad")
def create_squad(ports: PortsDep, body: SquadCreateIn) -> SquadOut:
    return SquadOut.model_validate(ports.use_case(CreateSquad).execute(body.to_input()))


@router.get("/{squad_id}", summary="Squad com a composição sprint por sprint")
def get_squad(ports: PortsDep, squad_id: UUID) -> SquadDetailOut:
    return SquadDetailOut.model_validate(ports.use_case(GetSquad).execute(squad_id))


@router.patch("/{squad_id}", summary="Altera squad")
def update_squad(ports: PortsDep, squad_id: UUID, body: SquadPatchIn) -> SquadOut:
    return SquadOut.model_validate(
        ports.use_case(UpdateSquad).execute(squad_id, body.to_input())
    )


@router.delete("/{squad_id}", summary="Inativa squad")
def deactivate_squad(ports: PortsDep, squad_id: UUID) -> SquadOut:
    """Soft delete: `is_active = false` (§8). As alocações que a squad tem no
    passado continuam de pé."""
    return SquadOut.model_validate(ports.use_case(DeactivateSquad).execute(squad_id))


@router.get("/{squad_id}/memberships", summary="Composição por sprint")
def list_memberships(
    ports: PortsDep,
    squad_id: UUID,
    sprint_from: int | None = None,
    sprint_to: int | None = None,
) -> list[SprintCompositionOut]:
    return [
        SprintCompositionOut.model_validate(view)
        for view in ports.use_case(ListSquadMemberships).execute(
            squad_id, sprint_from=sprint_from, sprint_to=sprint_to
        )
    ]


@router.put("/{squad_id}/memberships", summary="Substitui a composição no intervalo")
def set_memberships(
    ports: PortsDep, squad_id: UUID, body: SetMembershipsIn
) -> list[SprintCompositionOut]:
    """Devolve a composição resultante, para a matriz da tela de time não
    recarregar o intervalo inteiro depois de cada edição."""
    return [
        SprintCompositionOut.model_validate(view)
        for view in ports.use_case(SetSquadMemberships).execute(
            squad_id, body.to_input()
        )
    ]


@router.delete("/{squad_id}/memberships", summary="Remove membros do intervalo")
def remove_memberships(
    ports: PortsDep, squad_id: UUID, body: RemoveMembershipsIn
) -> list[SprintCompositionOut]:
    return [
        SprintCompositionOut.model_validate(view)
        for view in ports.use_case(RemoveSquadMemberships).execute(
            squad_id, body.to_input()
        )
    ]
