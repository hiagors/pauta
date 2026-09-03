"""Use cases de membro (§6.4). Membro nunca é apagado."""

import pytest

from app.application.dto.members import CreateMemberInput, UpdateMemberInput
from app.application.use_cases.members.create import CreateMember
from app.application.use_cases.members.deactivate import DeactivateMember
from app.application.use_cases.members.list import ListMembers
from app.application.use_cases.members.update import UpdateMember
from app.domain.errors import InvalidName, MemberNotFound
from tests.application.conftest import Fakes, World
from tests.domain.conftest import uid


def test_create_member(fakes: Fakes) -> None:
    view = fakes.use_case(CreateMember).execute(
        CreateMemberInput(name="Ana Martins", short_name="Ana", role="Dados")
    )

    assert view.is_active is True
    assert view.short_name == "Ana"
    assert fakes.members.get(view.id) is not None


def test_create_member_requires_a_name(fakes: Fakes) -> None:
    with pytest.raises(InvalidName):
        fakes.use_case(CreateMember).execute(
            CreateMemberInput(name="  ", short_name="Ana")
        )


def test_deactivate_member_keeps_the_row(world: World, fakes: Fakes) -> None:
    """Soft delete: apagar reescreveria alocações passadas."""
    member = world.member("Diana")

    view = fakes.use_case(DeactivateMember).execute(member.id)

    assert view.is_active is False
    stored = fakes.members.get(member.id)
    assert stored is not None
    assert stored.is_active is False


def test_deactivate_member_reports_unknown_id(fakes: Fakes) -> None:
    with pytest.raises(MemberNotFound):
        fakes.use_case(DeactivateMember).execute(uid(999))


def test_update_member_can_reactivate(world: World, fakes: Fakes) -> None:
    member = world.member("Diana", active=False)

    view = fakes.use_case(UpdateMember).execute(
        member.id, UpdateMemberInput(is_active=True, role="Produto")
    )

    assert view.is_active is True
    assert view.role == "Produto"


def test_list_members_filters_by_active(world: World, fakes: Fakes) -> None:
    world.member("Ana")
    world.member("Ana", active=False)

    assert [view.name for view in fakes.use_case(ListMembers).execute()] == [
        "Ana",
        "Ana",
    ]
    assert [view.name for view in fakes.use_case(ListMembers).execute(active=True)] == [
        "Ana"
    ]
