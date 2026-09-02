"""Alocação: um responsável por sprint (§6.7)."""

import pytest

from app.domain.entities.allocation import Allocation
from app.domain.errors import AmbiguousAssignee, AssigneeRequired
from app.domain.value_objects.assignee import Assignee
from tests.domain.conftest import uid


def test_alocacao_de_squad_expoe_squad_id_e_nao_member_id() -> None:
    allocation = Allocation.create(
        initiative_id=uid(1), sprint_id=uid(2), assignee=Assignee.for_squad(uid(3))
    )
    assert allocation.squad_id == uid(3)
    assert allocation.member_id is None


def test_alocacao_direta_a_um_membro_dispensa_squad_de_um_so() -> None:
    allocation = Allocation.create_from_ids(
        initiative_id=uid(1), sprint_id=uid(2), member_id=uid(4)
    )
    assert allocation.member_id == uid(4)
    assert allocation.squad_id is None


def test_sem_responsavel_e_erro() -> None:
    with pytest.raises(AssigneeRequired):
        Allocation.create_from_ids(initiative_id=uid(1), sprint_id=uid(2))


def test_com_squad_e_membro_e_erro() -> None:
    with pytest.raises(AmbiguousAssignee):
        Allocation.create_from_ids(
            initiative_id=uid(1), sprint_id=uid(2), squad_id=uid(3), member_id=uid(4)
        )
