"""`/members` (§8)."""

from uuid import UUID

from fastapi import APIRouter, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.members import (
    MemberCreateIn,
    MemberOut,
    MemberPatchIn,
)
from app.application.use_cases.members.create import CreateMember
from app.application.use_cases.members.deactivate import DeactivateMember
from app.application.use_cases.members.list import ListMembers
from app.application.use_cases.members.update import UpdateMember

router = APIRouter(prefix="/members", tags=["membros"])


@router.get("", summary="Lista membros")
def list_members(ports: PortsDep, active: bool | None = None) -> list[MemberOut]:
    return [
        MemberOut.model_validate(view)
        for view in ports.use_case(ListMembers).execute(active=active)
    ]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Cria membro")
def create_member(ports: PortsDep, body: MemberCreateIn) -> MemberOut:
    return MemberOut.model_validate(
        ports.use_case(CreateMember).execute(body.to_input())
    )


@router.patch("/{member_id}", summary="Altera membro")
def update_member(ports: PortsDep, member_id: UUID, body: MemberPatchIn) -> MemberOut:
    return MemberOut.model_validate(
        ports.use_case(UpdateMember).execute(member_id, body.to_input())
    )


@router.delete("/{member_id}", summary="Inativa membro")
def deactivate_member(ports: PortsDep, member_id: UUID) -> MemberOut:
    """Soft delete: `is_active = false` (§6.4). Membro nunca é apagado —
    apagar reescreveria alocações passadas. Por isso a resposta é o membro
    inativado, e não 204: a UI atualiza a linha sem recarregar a lista.
    """
    return MemberOut.model_validate(ports.use_case(DeactivateMember).execute(member_id))
