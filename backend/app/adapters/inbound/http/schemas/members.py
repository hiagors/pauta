"""Schemas de membro (§6.4, §8)."""

from uuid import UUID

from app.adapters.inbound.http.schemas.common import (
    InputModel,
    OutputModel,
    PatchModel,
)
from app.application.dto.members import CreateMemberInput, UpdateMemberInput


class MemberCreateIn(InputModel):
    name: str
    short_name: str
    role: str = ""

    def to_input(self) -> CreateMemberInput:
        return CreateMemberInput(
            name=self.name, short_name=self.short_name, role=self.role
        )


class MemberPatchIn(PatchModel):
    name: str = ""
    short_name: str = ""
    role: str = ""
    is_active: bool = True

    def to_input(self) -> UpdateMemberInput:
        return UpdateMemberInput(
            name=self.patch("name"),
            short_name=self.patch("short_name"),
            role=self.patch("role"),
            is_active=self.patch("is_active"),
        )


class MemberOut(OutputModel):
    id: UUID
    name: str
    short_name: str
    role: str
    is_active: bool
