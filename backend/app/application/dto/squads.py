"""DTOs de squad e da composição por sprint (§6.5)."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.application.dto.common import UNSET, Patch
from app.application.dto.members import MemberView
from app.domain.entities.squad import Squad


@dataclass(frozen=True)
class CreateSquadInput:
    name: str
    representative_member_id: UUID | None = None


@dataclass(frozen=True)
class UpdateSquadInput:
    name: Patch[str] = UNSET
    representative_member_id: Patch[UUID | None] = UNSET
    is_active: Patch[bool] = UNSET


@dataclass(frozen=True)
class SetMembershipsInput:
    """`PUT /squads/{id}/memberships`: **substitui** a composição no intervalo."""

    sprint_from: int
    sprint_to: int
    member_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class RemoveMembershipsInput:
    """`DELETE /squads/{id}/memberships`. `member_ids` nulo remove todos."""

    sprint_from: int
    sprint_to: int
    member_ids: tuple[UUID, ...] | None = None


@dataclass(frozen=True)
class SprintCompositionView:
    """Quem está na squad em **uma** sprint."""

    sprint_id: UUID
    sprint_number: int
    members: tuple[MemberView, ...]


@dataclass(frozen=True)
class SquadView:
    """`members` só vem preenchido quando `GET /squads` recebe `sprint_number`.

    Sem a sprint pedida não existe "os membros da squad": a composição é por
    sprint (D11), e uma lista sem sprint seria mentira.
    """

    id: UUID
    name: str
    representative_member_id: UUID | None
    is_active: bool
    sprint_number: int | None = None
    members: tuple[MemberView, ...] = ()

    @classmethod
    def of(
        cls,
        squad: Squad,
        *,
        sprint_number: int | None = None,
        members: tuple[MemberView, ...] = (),
    ) -> Self:
        return cls(
            id=squad.id,
            name=squad.name,
            representative_member_id=squad.representative_member_id,
            is_active=squad.is_active,
            sprint_number=sprint_number,
            members=members,
        )


@dataclass(frozen=True)
class SquadDetailView:
    """`GET /squads/{id}`: a squad e a composição sprint por sprint."""

    squad: SquadView
    memberships: tuple[SprintCompositionView, ...]
