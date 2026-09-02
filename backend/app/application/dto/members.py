"""DTOs de membro (§6.4)."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.application.dto.common import UNSET, Patch
from app.domain.entities.member import Member


@dataclass(frozen=True)
class CreateMemberInput:
    name: str
    short_name: str
    role: str = ""


@dataclass(frozen=True)
class UpdateMemberInput:
    name: Patch[str] = UNSET
    short_name: Patch[str] = UNSET
    role: Patch[str] = UNSET
    is_active: Patch[bool] = UNSET


@dataclass(frozen=True)
class MemberView:
    id: UUID
    name: str
    short_name: str
    role: str
    is_active: bool

    @classmethod
    def of(cls, member: Member) -> Self:
        return cls(
            id=member.id,
            name=member.name,
            short_name=member.short_name,
            role=member.role,
            is_active=member.is_active,
        )
