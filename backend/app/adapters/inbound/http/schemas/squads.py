"""Schemas de squad e da composição por sprint (§6.5, §8)."""

from uuid import UUID

from app.adapters.inbound.http.schemas.common import (
    InputModel,
    OutputModel,
    PatchModel,
)
from app.adapters.inbound.http.schemas.members import MemberOut
from app.application.dto.squads import (
    CreateSquadInput,
    RemoveMembershipsInput,
    SetMembershipsInput,
    UpdateSquadInput,
)


class SquadCreateIn(InputModel):
    name: str
    representative_member_id: UUID | None = None

    def to_input(self) -> CreateSquadInput:
        return CreateSquadInput(
            name=self.name, representative_member_id=self.representative_member_id
        )


class SquadPatchIn(PatchModel):
    name: str = ""
    representative_member_id: UUID | None = None
    is_active: bool = True

    def to_input(self) -> UpdateSquadInput:
        return UpdateSquadInput(
            name=self.patch("name"),
            representative_member_id=self.patch("representative_member_id"),
            is_active=self.patch("is_active"),
        )


class SetMembershipsIn(InputModel):
    """`PUT /squads/{id}/memberships`: **substitui** a composição no intervalo.

    Lista vazia é operação válida e significa "ninguém nesta squad nestas
    sprints" — é como se esvazia a composição sem apagar a squad.
    """

    sprint_from: int
    sprint_to: int
    member_ids: list[UUID] = []

    def to_input(self) -> SetMembershipsInput:
        return SetMembershipsInput(
            sprint_from=self.sprint_from,
            sprint_to=self.sprint_to,
            member_ids=tuple(self.member_ids),
        )


class RemoveMembershipsIn(InputModel):
    """`DELETE /squads/{id}/memberships`. `member_ids` ausente remove todos."""

    sprint_from: int
    sprint_to: int
    member_ids: list[UUID] | None = None

    def to_input(self) -> RemoveMembershipsInput:
        return RemoveMembershipsInput(
            sprint_from=self.sprint_from,
            sprint_to=self.sprint_to,
            member_ids=None if self.member_ids is None else tuple(self.member_ids),
        )


class SprintCompositionOut(OutputModel):
    """Quem está na squad em **uma** sprint."""

    sprint_id: UUID
    sprint_number: int
    members: list[MemberOut]


class SquadOut(OutputModel):
    """`members` só vem preenchido quando `GET /squads` recebe `sprint_number`.

    Sem a sprint pedida não existe "os membros da squad": a composição é por
    sprint (D11), e uma lista sem sprint seria mentira.
    """

    id: UUID
    name: str
    representative_member_id: UUID | None
    is_active: bool
    sprint_number: int | None = None
    members: list[MemberOut] = []


class SquadDetailOut(OutputModel):
    """`GET /squads/{id}`: a squad e a composição sprint por sprint (§8)."""

    squad: SquadOut
    memberships: list[SprintCompositionOut]
