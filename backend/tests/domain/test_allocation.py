"""Alocação: um responsável por sprint (§6.7)."""

import pytest

from app.domain.entities.allocation import Allocation
from app.domain.errors import AmbiguousAssignee, AssigneeRequired
from app.domain.value_objects.assignee import Assignee
from tests.domain.conftest import uid


def test_a_squad_allocation_exposes_squad_id_and_not_member_id() -> None:
    allocation = Allocation.create(
        initiative_id=uid(1), sprint_id=uid(2), assignee=Assignee.for_squad(uid(3))
    )
    assert allocation.squad_id == uid(3)
    assert allocation.member_id is None


def test_a_direct_member_allocation_needs_no_squad_of_one() -> None:
    allocation = Allocation.create_from_ids(
        initiative_id=uid(1), sprint_id=uid(2), member_id=uid(4)
    )
    assert allocation.member_id == uid(4)
    assert allocation.squad_id is None


def test_no_assignee_is_an_error() -> None:
    with pytest.raises(AssigneeRequired):
        Allocation.create_from_ids(initiative_id=uid(1), sprint_id=uid(2))


def test_both_squad_and_member_is_an_error() -> None:
    with pytest.raises(AmbiguousAssignee):
        Allocation.create_from_ids(
            initiative_id=uid(1), sprint_id=uid(2), squad_id=uid(3), member_id=uid(4)
        )
